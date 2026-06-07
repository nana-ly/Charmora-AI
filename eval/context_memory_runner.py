"""上下文记忆行为的确定性离线评估 Runner。"""

# 该脚本位于仓库根目录的 eval/ 下，需要先把 backend/ 加入导入路径。
# ruff: noqa: E402

import argparse
import json
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from statistics import mean
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
BACKEND_PATH = REPO_ROOT / "backend"
if str(BACKEND_PATH) not in sys.path:
    sys.path.insert(0, str(BACKEND_PATH))

from agent.fallback_understanding import fallback_understanding
from agent.graph.runner import LangGraphAgentRunner
from agent.memory import ConversationState, InMemoryConversationStore
from agent.tools import RecommendationTool
from agent.understanding import clarify_for_context


CASES_PATH = REPO_ROOT / "eval" / "context_memory_cases.jsonl"
REPORT_PATH = REPO_ROOT / "eval" / "context_memory_report.md"


@dataclass(frozen=True)
class ContextMemoryEvalResult:
    """单条上下文记忆评估结果。"""

    case_id: str
    passed: bool
    failures: list[str]
    response_state: dict[str, Any]


class DeterministicUnderstandingService:
    """评估专用理解服务，只使用本地规则，避免真实 LLM 调用。"""

    def understand(self, *, message: str, conversation: ConversationState):
        return (
            fallback_understanding(
                message=message,
                conversation=conversation,
                reason="context_memory_eval",
            )
            or clarify_for_context(conversation)
        )


def load_cases(path: Path = CASES_PATH) -> list[dict[str, Any]]:
    """读取 JSONL 上下文评估用例。"""
    return [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def deterministic_recommendation(
    query: str,
    top_k: int = 3,
    negative_filters=None,
) -> dict[str, Any]:
    """返回固定商品集，并按负反馈过滤，保证上下文评估稳定可复现。"""
    filters = _filters_from_query(query)
    if filters["category"] == "美妆护肤":
        items = [
            _product("eval_skin_1", "Eval Skin A", "薇诺娜", 199, "保湿", "温和保湿"),
            _product("eval_skin_2", "Eval Skin B", "珀莱雅", 299, "修护", "屏障修护"),
        ]
    else:
        items = [
            _product("eval_phone_1", "Eval Phone A", "华为", 3999, "拍照", "拍照稳定"),
            _product("eval_phone_2", "Eval Phone B", "苹果", 6999, "性能", "性能稳定"),
            _product("eval_phone_3", "Eval Phone C", "小米", 2999, "续航", "续航更稳"),
        ]

    if negative_filters is not None:
        excluded_ids = set(negative_filters.excluded_product_ids)
        excluded_brands = set(negative_filters.excluded_brands)
        items = [
            item
            for item in items
            if item["product_id"] not in excluded_ids
            and item["brand"] not in excluded_brands
        ]

    selected_items = items[:top_k]
    return {
        "query": query,
        "filters": filters,
        "items": selected_items,
        "result_count": len(selected_items),
    }


def run_case(case: dict[str, Any]) -> ContextMemoryEvalResult:
    """执行单条多轮上下文记忆用例并校验最终 state。"""
    store = InMemoryConversationStore()
    runner = LangGraphAgentRunner(
        store=store,
        recommendation_tool=RecommendationTool(recommend_func=deterministic_recommendation),
        understanding_service=DeterministicUnderstandingService(),
    )
    session_id = f"context-eval-{case['id']}"
    response = None
    for message in case["messages"]:
        response = runner.run(session_id, message)

    assert response is not None
    failures = _check_expected(response.state, case["expected"])
    return ContextMemoryEvalResult(
        case_id=case["id"],
        passed=not failures,
        failures=failures,
        response_state=response.state,
    )


def run_all_cases(cases_path: Path = CASES_PATH) -> list[ContextMemoryEvalResult]:
    """执行全部上下文记忆评估用例。"""
    return [run_case(case) for case in load_cases(cases_path)]


def compute_metrics(
    results: list[ContextMemoryEvalResult],
) -> dict[str, float | int]:
    """计算上下文记忆评估指标。"""
    if not results:
        return {
            "case_pass_rate": 0.0,
            "failed_count": 0,
            "case_count": 0,
        }
    return {
        "case_pass_rate": mean([1.0 if result.passed else 0.0 for result in results]),
        "failed_count": sum(1 for result in results if not result.passed),
        "case_count": len(results),
    }


def assert_thresholds(
    metrics: dict[str, float | int],
    *,
    min_pass_rate: float = 1.0,
) -> list[str]:
    """返回未满足的阈值；CLI 用它决定是否失败退出。"""
    failures: list[str] = []
    actual_pass_rate = float(metrics.get("case_pass_rate", 0.0))
    if actual_pass_rate < min_pass_rate:
        failures.append(
            f"case_pass_rate expected >= {min_pass_rate}, got {actual_pass_rate}"
        )
    return failures


def write_report(
    results: list[ContextMemoryEvalResult],
    path: Path = REPORT_PATH,
) -> None:
    """输出 Markdown 评估报告。"""
    metrics = compute_metrics(results)
    lines = [
        "# Context Memory Eval Report",
        "",
        "## Metrics",
        "",
        "| metric | value |",
        "| --- | ---: |",
    ]
    for key, value in metrics.items():
        lines.append(f"| {key} | {value} |")

    lines.extend(["", "## Failed Cases", "", "| case | failures |", "| --- | --- |"])
    failed_results = [result for result in results if not result.passed]
    if not failed_results:
        lines.append("| - | - |")
    for result in failed_results:
        lines.append(f"| {result.case_id} | {'<br>'.join(result.failures)} |")

    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _check_expected(state: dict[str, Any], expected: dict[str, Any]) -> list[str]:
    failures: list[str] = []
    preferences = state.get("preferences", {})

    for key in (
        "target_category",
        "category",
        "canonical_target_key",
        "budget",
        "price_direction",
    ):
        if key in expected and preferences.get(key) != expected[key]:
            failures.append(
                f"{key}: expected {expected[key]!r}, got {preferences.get(key)!r}"
            )

    for brand in expected.get("excluded_brands", []):
        if brand not in state.get("excluded_brands", []):
            failures.append(f"missing excluded brand {brand}")

    if "archived_context_count_min" in expected:
        actual_count = state.get("memory", {}).get("archived_context_count", 0)
        if actual_count < expected["archived_context_count_min"]:
            failures.append(
                "archived_context_count expected >= "
                f"{expected['archived_context_count_min']}, got {actual_count}"
            )

    if "action" in expected and state.get("action") != expected["action"]:
        failures.append(f"action: expected {expected['action']!r}, got {state.get('action')!r}")

    return failures


def _filters_from_query(query: str) -> dict[str, Any]:
    max_price = None
    if match := re.search(r"(\d{3,6})\s*(?:元)?\s*(?:以内|以下|不超过)", query):
        max_price = int(match.group(1))

    category = "美妆护肤" if any(term in query for term in ("护肤", "保湿", "修护")) else "数码电子"
    keywords = [
        keyword
        for keyword in ("手机", "拍照", "性能", "续航", "护肤", "保湿", "修护")
        if keyword in query
    ]
    return {
        "category": category,
        "max_price": max_price,
        "brand": None,
        "keywords": keywords,
    }


def _product(
    product_id: str,
    title: str,
    brand: str,
    price: float,
    reason: str,
    evidence: str,
) -> dict[str, Any]:
    return {
        "product_id": product_id,
        "title": title,
        "brand": brand,
        "price": price,
        "price_range": f"¥{int(price)}",
        "reason": reason,
        "evidence": evidence,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--cases", type=Path, default=CASES_PATH)
    parser.add_argument("--report", type=Path, default=REPORT_PATH)
    parser.add_argument("--min-pass-rate", type=float, default=1.0)
    args = parser.parse_args()

    results = run_all_cases(args.cases)
    write_report(results, args.report)
    metrics = compute_metrics(results)
    print(json.dumps(metrics, ensure_ascii=False, indent=2))
    threshold_failures = assert_thresholds(
        metrics,
        min_pass_rate=args.min_pass_rate,
    )
    if threshold_failures:
        print(json.dumps({"threshold_failures": threshold_failures}, ensure_ascii=False))
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
