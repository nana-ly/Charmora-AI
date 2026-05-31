"""Shopping Agent 架构用例的确定性可执行评估."""

# 该脚本位于仓库根目录的 eval/ 下，需要先把 backend/ 加入导入路径。
# ruff: noqa: E402

import argparse
import json
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
BACKEND_PATH = REPO_ROOT / "backend"
if str(BACKEND_PATH) not in sys.path:
    sys.path.insert(0, str(BACKEND_PATH))

from agent.fallback_understanding import fallback_understanding
from agent.graph.runner import LangGraphAgentRunner
from agent.memory import ConversationState, InMemoryConversationStore
from agent.tools import RecommendationTool
from agent.understanding import UserIntent, UserUnderstanding, clarify_for_context
from schemas.product import ProductCard


CASES_PATH = REPO_ROOT / "eval" / "shopping_agent_architecture_cases.jsonl"
REPORT_PATH = REPO_ROOT / "eval" / "report.md"


@dataclass(frozen=True)
class EvalResult:
    """单条评估用例的执行结果。"""

    case_id: str
    passed: bool
    failures: list[str]
    response_state: dict[str, Any]


class DeterministicUnderstandingService:
    """评估专用理解服务，只使用本地规则，避免依赖真实 LLM。"""

    def understand(self, *, message: str, conversation: ConversationState):
        explain_understanding = _explain_understanding(message, conversation)
        if explain_understanding is not None:
            return explain_understanding
        return (
            fallback_understanding(
                message=message,
                conversation=conversation,
                reason="eval",
            )
            or clarify_for_context(conversation)
        )


def load_cases(path: Path = CASES_PATH) -> list[dict[str, Any]]:
    """读取 JSONL 评估用例。"""
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
    """返回固定商品集，并按负反馈过滤，保证评估稳定可复现。"""
    filters = _filters_from_query(query)
    if filters["max_price"] == 100 and "旗舰" in query:
        items: list[dict[str, Any]] = []
    elif filters["category"] == "美妆护肤":
        items = [
            _product("skin_a", "Eval Skin A", "华为", 199, "保湿", "适合干皮保湿"),
            _product("skin_b", "Eval Skin B", "小米", 299, "敏感肌", "温和修护"),
        ]
    else:
        items = [
            _product("phone_a", "Eval Phone A", "华为", 2999, "拍照", "拍照表现稳定"),
            _product("phone_b", "Eval Phone B", "苹果", 3999, "游戏", "游戏性能稳定"),
            _product("phone_c", "Eval Phone C", "小米", 1999, "续航", "续航更稳"),
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

    return {
        "query": query,
        "filters": filters,
        "items": items[:top_k],
    }


def run_case(case: dict[str, Any]) -> EvalResult:
    """执行单条多轮用例并返回校验结果。"""
    store = InMemoryConversationStore()
    session_id = f"eval-{case['id']}"
    state = store.get_or_create(session_id)
    _hydrate_initial_state(state, case.get("initial_state", {}))
    store.save(state)
    previous_successful_ids = [item.product_id for item in state.last_successful_items]

    recommendation_calls = 0

    def counted_recommendation(
        query: str,
        top_k: int = 3,
        negative_filters=None,
    ) -> dict[str, Any]:
        nonlocal recommendation_calls
        recommendation_calls += 1
        return deterministic_recommendation(
            query,
            top_k=top_k,
            negative_filters=negative_filters,
        )

    runner = LangGraphAgentRunner(
        store=store,
        recommendation_tool=RecommendationTool(recommend_func=counted_recommendation),
        understanding_service=DeterministicUnderstandingService(),
    )

    response = None
    for message in case["messages"]:
        response = runner.run(session_id, message)

    assert response is not None
    final_state = store.get_or_create(session_id)
    failures = _check_case(
        case=case,
        state=response.state,
        conversation=final_state,
        recommendation_calls=recommendation_calls,
        previous_successful_ids=previous_successful_ids,
    )
    return EvalResult(
        case_id=case["id"],
        passed=not failures,
        failures=failures,
        response_state=response.state,
    )


def run_all_cases(cases_path: Path = CASES_PATH) -> list[EvalResult]:
    """执行全部评估用例。"""
    return [run_case(case) for case in load_cases(cases_path)]


def write_report(results: list[EvalResult], path: Path = REPORT_PATH) -> None:
    """输出 Markdown 评估报告。"""
    total = len(results)
    passed = sum(1 for result in results if result.passed)
    lines = [
        "# Shopping Agent Eval Report",
        "",
        f"- total: {total}",
        f"- passed: {passed}",
        f"- failed: {total - passed}",
        "",
        "| case | status | failures |",
        "| --- | --- | --- |",
    ]
    for result in results:
        status = "pass" if result.passed else "fail"
        failures = "<br>".join(result.failures) if result.failures else ""
        lines.append(f"| {result.case_id} | {status} | {failures} |")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _check_case(
    *,
    case: dict[str, Any],
    state: dict[str, Any],
    conversation: ConversationState,
    recommendation_calls: int,
    previous_successful_ids: list[str],
) -> list[str]:
    failures: list[str] = []
    for expected_key, state_key in (
        ("expected_intent", "intent"),
        ("expected_action", "action"),
        ("expected_result_status", "result_status"),
        ("expected_pending_restore_category", "pending_restore_category"),
    ):
        _check_equal(failures, state_key, case.get(expected_key), state.get(state_key))

    preferences = state.get("preferences", {})
    _check_equal(
        failures,
        "category",
        case.get("expected_category"),
        preferences.get("category"),
    )
    _check_equal(
        failures,
        "target_category",
        case.get("expected_target_category"),
        preferences.get("target_category"),
    )
    _check_equal(
        failures,
        "canonical_target_key",
        case.get("expected_canonical_target_key"),
        preferences.get("canonical_target_key"),
    )

    for constraint in case.get("must_include_constraints", []):
        _check_must_include_constraint(failures, constraint, state, conversation)
    for constraint in case.get("must_exclude_constraints", []):
        _check_must_exclude_constraint(
            failures,
            constraint,
            state,
            recommendation_calls,
        )

    if case.get("expected_keeps_last_successful_items") is True:
        current_ids = [item.product_id for item in conversation.last_successful_items]
        if not current_ids:
            failures.append("last_successful_items should not be empty")
        if previous_successful_ids and not set(previous_successful_ids) & set(current_ids):
            failures.append("last_successful_items did not keep previous context")

    return failures


def _check_must_include_constraint(
    failures: list[str],
    constraint: str,
    state: dict[str, Any],
    conversation: ConversationState,
) -> None:
    preferences = state.get("preferences", {})
    if match := re.fullmatch(r"max_price<=(\d+)", constraint):
        expected = int(match.group(1))
        actual = preferences.get("max_price") or preferences.get("budget")
        query_text = " ".join(
            item
            for item in [
                conversation.purchase_need,
                conversation.last_query,
                conversation.last_no_results_need,
            ]
            if isinstance(item, str)
        )
        if actual != expected and f"{expected}" not in query_text:
            failures.append(f"{constraint}: got {actual!r}")
        return
    if constraint == "price_direction=lower":
        if preferences.get("price_direction") != "lower":
            failures.append("price_direction should be lower")
        return
    if constraint == "avoid_current_price_band=true":
        if preferences.get("avoid_current_price_band") is not True:
            failures.append("avoid_current_price_band should be true")
        return
    if constraint == "compare_item_indexes=[1,2]":
        if state.get("intent") != "compare" or state.get("action") != "compare":
            failures.append("compare intent/action missing")
        return

    query_text = " ".join(
        item
        for item in [conversation.purchase_need, conversation.last_query]
        if isinstance(item, str)
    )
    if constraint and constraint not in query_text:
        failures.append(f"constraint {constraint!r} missing from query context")


def _check_must_exclude_constraint(
    failures: list[str],
    constraint: str,
    state: dict[str, Any],
    recommendation_calls: int,
) -> None:
    if constraint == "recommendation_not_called":
        if recommendation_calls != 0:
            failures.append(f"recommendation called {recommendation_calls} times")
        return
    if match := re.fullmatch(r"excluded_product_ids includes (.+)", constraint):
        product_id = match.group(1)
        if product_id not in state.get("excluded_product_ids", []):
            failures.append(f"excluded_product_ids missing {product_id}")
        return
    if match := re.fullmatch(r"excluded_brands includes (.+)", constraint):
        brand = match.group(1)
        if brand not in state.get("excluded_brands", []):
            failures.append(f"excluded_brands missing {brand}")


def _check_equal(
    failures: list[str],
    label: str,
    expected: Any,
    actual: Any,
) -> None:
    if expected != actual:
        failures.append(f"{label}: expected {expected!r}, got {actual!r}")


def _hydrate_initial_state(
    state: ConversationState,
    initial_state: dict[str, Any],
) -> None:
    state.purchase_need = initial_state.get("purchase_need")
    preferences = initial_state.get("preferences")
    if isinstance(preferences, dict):
        state.preferences = dict(preferences)

    last_items = initial_state.get("last_items")
    if isinstance(last_items, list):
        state.last_items = _products_from_case(last_items)

    last_successful_items = initial_state.get("last_successful_items")
    if isinstance(last_successful_items, list):
        state.last_successful_items = _products_from_case(last_successful_items)
    elif state.last_items:
        state.last_successful_items = list(state.last_items)


def _products_from_case(items: list[dict[str, Any]]) -> list[ProductCard]:
    return [
        ProductCard(
            product_id=item.get("product_id", f"eval_{index}"),
            title=item.get("title", f"Eval Product {index}"),
            brand=item.get("brand", "EvalBrand"),
            price=item.get("price", 1000),
            reason=item.get("reason", "initial eval item"),
            evidence=item.get("evidence", "initial eval evidence"),
        )
        for index, item in enumerate(items, start=1)
    ]


def _filters_from_query(query: str) -> dict[str, Any]:
    max_price = None
    if match := re.search(r"(\d{2,6})\s*(?:元)?\s*(?:以内|以下|不超过)", query):
        max_price = int(match.group(1))

    category = "美妆护肤" if any(term in query for term in ("护肤", "干皮")) else "数码电子"
    keywords = [
        keyword
        for keyword in ("手机", "拍照", "游戏", "护肤", "干皮", "旗舰")
        if keyword in query
    ]
    return {
        "category": category,
        "max_price": max_price,
        "brand": None,
        "keywords": keywords,
    }


def _explain_understanding(
    message: str,
    conversation: ConversationState,
) -> UserUnderstanding | None:
    if not conversation.last_items:
        return None
    if not any(term in message for term in ("为什么", "理由", "解释")):
        return None

    target_item_index = 1
    if match := re.search(r"第\s*([一二两三四五六七八九1-9])\s*[个款台件]?", message):
        target_item_index = _parse_index_token(match.group(1)) or 1

    return UserUnderstanding(
        intent=UserIntent.EXPLAIN,
        confidence=0.8,
        target_item_index=target_item_index,
    )


def _parse_index_token(token: str) -> int | None:
    return {
        "一": 1,
        "1": 1,
        "二": 2,
        "两": 2,
        "2": 2,
        "三": 3,
        "3": 3,
        "四": 4,
        "4": 4,
        "五": 5,
        "5": 5,
        "六": 6,
        "6": 6,
        "七": 7,
        "7": 7,
        "八": 8,
        "8": 8,
        "九": 9,
        "9": 9,
    }.get(token)


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
        "reason": reason,
        "evidence": evidence,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", choices=["deterministic"], default="deterministic")
    parser.add_argument("--cases", type=Path, default=CASES_PATH)
    parser.add_argument("--report", type=Path, default=REPORT_PATH)
    args = parser.parse_args()

    results = run_all_cases(args.cases)
    write_report(results, args.report)
    return 0 if all(result.passed for result in results) else 1


if __name__ == "__main__":
    raise SystemExit(main())
