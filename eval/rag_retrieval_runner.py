"""RAG 检索质量离线评估 Runner。"""

# 该脚本位于仓库根目录的 eval/ 下，需要先把 backend/ 加入导入路径。
# ruff: noqa: E402

import argparse
import json
import sys
from dataclasses import asdict, dataclass
from pathlib import Path
from statistics import mean
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
BACKEND_PATH = REPO_ROOT / "backend"
if str(BACKEND_PATH) not in sys.path:
    sys.path.insert(0, str(BACKEND_PATH))

from recommendation_core.pipeline import recommend_products
from recommendation_core.data import products
from recommendation_core.reason import template_reason
from retrieval.keyword import KeywordRetriever
from schemas.recommend import NegativeFilters
from services.retriever_factory import create_vector_retriever, select_retriever


CASES_PATH = REPO_ROOT / "eval" / "rag_retrieval_cases.jsonl"
REPORT_PATH = REPO_ROOT / "eval" / "rag_retrieval_report.md"
JSON_REPORT_PATH = REPO_ROOT / "eval" / "rag_retrieval_report.json"


@dataclass(frozen=True)
class RagEvalResult:
    """单条 RAG 检索评估结果。"""

    case_id: str
    passed: bool
    skipped: bool
    failures: list[str]
    items: list[dict[str, Any]]
    trace: dict[str, Any]
    expected_product_ids: list[str]
    expected_category: str | None
    expected_brand: str | None
    must_not_return_product_ids: list[str]
    allow_no_results: bool


class TemplateReasonService:
    """评估专用理由服务，避免离线评估调用真实 LLM。"""

    def generate(
        self,
        query: str,
        product: dict[str, Any],
        evidence: str,
        fallback_reason: str | None = None,
    ) -> str:
        return fallback_reason or template_reason(query, product, evidence)


def load_cases(path: Path = CASES_PATH) -> list[dict[str, Any]]:
    """读取 JSONL 评估样本。"""
    return [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def run_case(
    case: dict[str, Any],
    *,
    retriever_mode: str = "configured",
    top_k: int | None = None,
) -> RagEvalResult:
    """执行单条 RAG 检索样本。"""
    selected_mode = _select_mode(case, retriever_mode)
    selected_top_k = top_k or int(case.get("top_k") or 3)
    try:
        retriever = _build_retriever(selected_mode)
    except Exception as exc:
        if selected_mode == "vector":
            return _skipped_result(case, f"vector retriever not ready: {exc}")
        raise

    response = recommend_products(
        case["query"],
        top_k=selected_top_k,
        retriever=retriever,
        reason_service=TemplateReasonService(),
        negative_filters=NegativeFilters(**case["negative_filters"]),
        include_trace=True,
    )
    items = [_enrich_eval_item(dict(item)) for item in response["items"]]
    trace = dict(response.get("trace") or {})
    failures = _check_case(case, items)
    return RagEvalResult(
        case_id=case["id"],
        passed=not failures,
        skipped=False,
        failures=failures,
        items=items,
        trace=trace,
        expected_product_ids=list(case.get("expected_product_ids") or []),
        expected_category=case.get("expected_category"),
        expected_brand=case.get("expected_brand"),
        must_not_return_product_ids=list(case.get("must_not_return_product_ids") or []),
        allow_no_results=bool(case.get("allow_no_results")),
    )


def run_all_cases(
    cases_path: Path = CASES_PATH,
    *,
    retriever_mode: str = "configured",
    top_k: int | None = None,
) -> list[RagEvalResult]:
    """执行全部样本。"""
    return [
        run_case(case, retriever_mode=retriever_mode, top_k=top_k)
        for case in load_cases(cases_path)
    ]


def compute_metrics(results: list[RagEvalResult]) -> dict[str, float | int]:
    """计算核心检索评估指标。"""
    active_results = [result for result in results if not result.skipped]
    if not active_results:
        return {
            "case_pass_rate": 0.0,
            "hit@k": 0.0,
            "recall@k": 0.0,
            "category_hit_rate": 0.0,
            "brand_hit_rate": 0.0,
            "no_results_rate": 0.0,
            "unexpected_no_results_count": 0,
            "negative_exclusion_hit_rate": 0.0,
            "candidate_count_avg": 0.0,
            "retrieved_count_avg": 0.0,
            "final_count_avg": 0.0,
        }

    expected_results = [
        result for result in active_results if result.expected_product_ids
    ]
    category_results = [
        result for result in active_results if result.expected_category
    ]
    brand_results = [result for result in active_results if result.expected_brand]
    exclusion_results = [
        result for result in active_results if result.must_not_return_product_ids
    ]
    no_result_count = sum(1 for result in active_results if not result.items)

    return {
        "case_pass_rate": _ratio(
            sum(1 for result in active_results if result.passed),
            len(active_results),
        ),
        "hit@k": _ratio(
            sum(1 for result in expected_results if _hit_expected(result)),
            len(expected_results),
        ),
        "recall@k": mean(
            [_recall_expected(result) for result in expected_results]
        )
        if expected_results
        else 0.0,
        "category_hit_rate": _ratio(
            sum(1 for result in category_results if _hit_category(result)),
            len(category_results),
        ),
        "brand_hit_rate": _ratio(
            sum(1 for result in brand_results if _hit_brand(result)),
            len(brand_results),
        ),
        "no_results_rate": _ratio(no_result_count, len(active_results)),
        "unexpected_no_results_count": sum(
            1
            for result in active_results
            if not result.items and not result.allow_no_results
        ),
        "negative_exclusion_hit_rate": _ratio(
            sum(1 for result in exclusion_results if _excluded_items_absent(result)),
            len(exclusion_results),
        ),
        "candidate_count_avg": _avg_trace_count(active_results, "structured_candidate_count"),
        "retrieved_count_avg": _avg_trace_count(active_results, "retrieved_count"),
        "final_count_avg": _avg_trace_count(active_results, "final_count"),
    }


def write_report(
    results: list[RagEvalResult],
    path: Path = REPORT_PATH,
) -> None:
    """输出 Markdown 报告，失败样本只展示脱敏 trace 摘要。"""
    metrics = compute_metrics(results)
    lines = [
        "# RAG Retrieval Eval Report",
        "",
        "## Metrics",
        "",
        "| metric | value |",
        "| --- | ---: |",
    ]
    for key, value in metrics.items():
        lines.append(f"| {key} | {value} |")

    lines.extend(["", "## Failed Cases", "", "| case | failures | items |", "| --- | --- | --- |"])
    failed_results = [result for result in results if not result.passed and not result.skipped]
    if not failed_results:
        lines.append("| - | - | - |")
    for result in failed_results:
        failures = "<br>".join(result.failures)
        items = "<br>".join(_summarize_item(item) for item in _trace_items(result))
        lines.append(f"| {result.case_id} | {failures} | {items} |")

    skipped = [result for result in results if result.skipped]
    if skipped:
        lines.extend(["", "## Skipped", "", "| case | reason |", "| --- | --- |"])
        for result in skipped:
            lines.append(f"| {result.case_id} | {'; '.join(result.failures)} |")

    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def write_json_report(
    results: list[RagEvalResult],
    path: Path = JSON_REPORT_PATH,
) -> None:
    """输出机器可读报告，便于后续 CI 或发布脚本读取。"""
    payload = {
        "metrics": compute_metrics(results),
        "results": [asdict(result) for result in results],
    }
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _select_mode(case: dict[str, Any], override: str) -> str:
    if override != "configured":
        return override
    case_mode = str(case.get("retriever_mode") or "configured")
    if case_mode == "configured":
        return "configured"
    return case_mode


def _build_retriever(mode: str):
    if mode == "keyword":
        return KeywordRetriever()
    if mode == "vector":
        return create_vector_retriever()
    if mode == "configured":
        return select_retriever()
    raise ValueError("retriever mode 仅支持 keyword、vector 或 configured")


def _check_case(case: dict[str, Any], items: list[dict[str, Any]]) -> list[str]:
    failures: list[str] = []
    returned_ids = {item.get("product_id") for item in items}
    expected_ids = set(case.get("expected_product_ids") or [])
    must_not_return = set(case.get("must_not_return_product_ids") or [])
    allow_no_results = bool(case.get("allow_no_results"))

    if not items and not allow_no_results:
        failures.append("unexpected no results")
    if expected_ids and not (returned_ids & expected_ids):
        failures.append("expected product not returned")
    if not items and allow_no_results:
        return failures
    if returned_ids & must_not_return:
        failures.append("must_not_return_product_ids returned")

    expected_category = case.get("expected_category")
    if expected_category and not any(item.get("category") == expected_category for item in items):
        failures.append("expected category not returned")

    expected_brand = case.get("expected_brand")
    if expected_brand and not any(_brand_matches(item.get("brand"), expected_brand) for item in items):
        failures.append("expected brand not returned")
    return failures


def _skipped_result(case: dict[str, Any], reason: str) -> RagEvalResult:
    return RagEvalResult(
        case_id=case["id"],
        passed=False,
        skipped=True,
        failures=[reason],
        items=[],
        trace={},
        expected_product_ids=list(case.get("expected_product_ids") or []),
        expected_category=case.get("expected_category"),
        expected_brand=case.get("expected_brand"),
        must_not_return_product_ids=list(case.get("must_not_return_product_ids") or []),
        allow_no_results=bool(case.get("allow_no_results")),
    )


def _hit_expected(result: RagEvalResult) -> bool:
    returned_ids = {item.get("product_id") for item in result.items}
    return bool(returned_ids & set(result.expected_product_ids))


def _recall_expected(result: RagEvalResult) -> float:
    returned_ids = {item.get("product_id") for item in result.items}
    expected_ids = set(result.expected_product_ids)
    return _ratio(len(returned_ids & expected_ids), len(expected_ids))


def _hit_category(result: RagEvalResult) -> bool:
    return any(item.get("category") == result.expected_category for item in result.items)


def _hit_brand(result: RagEvalResult) -> bool:
    return any(_brand_matches(item.get("brand"), result.expected_brand) for item in result.items)


def _excluded_items_absent(result: RagEvalResult) -> bool:
    returned_ids = {item.get("product_id") for item in result.items}
    return not (returned_ids & set(result.must_not_return_product_ids))


def _avg_trace_count(results: list[RagEvalResult], key: str) -> float:
    return mean([float(result.trace.get(key, 0)) for result in results])


def _ratio(numerator: int, denominator: int) -> float:
    if denominator == 0:
        return 0.0
    return round(numerator / denominator, 4)


def _brand_matches(actual: Any, expected: Any) -> bool:
    if not actual or not expected:
        return False
    return str(expected) in str(actual)


def _trace_items(result: RagEvalResult) -> list[dict[str, Any]]:
    trace_items = result.trace.get("items") if result.trace else None
    if isinstance(trace_items, list) and trace_items:
        return trace_items
    return result.items


def _summarize_item(item: dict[str, Any]) -> str:
    return " / ".join(
        str(item.get(key, ""))
        for key in ("product_id", "title", "brand", "rank", "score", "source")
    )


def _enrich_eval_item(item: dict[str, Any]) -> dict[str, Any]:
    """从商品源补齐评估字段，不改变线上推荐响应结构。"""
    product = _PRODUCT_BY_ID.get(str(item.get("product_id")), {})
    for key in ("category", "sub_category"):
        if key not in item and key in product:
            item[key] = product[key]
    return item


_PRODUCT_BY_ID = {str(product.get("product_id")): product for product in products}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--cases", type=Path, default=CASES_PATH)
    parser.add_argument(
        "--retriever-mode",
        choices=["keyword", "vector", "configured"],
        default="keyword",
    )
    parser.add_argument("--top-k", type=int, default=None)
    parser.add_argument("--report", type=Path, default=REPORT_PATH)
    parser.add_argument("--json-output", type=Path, default=JSON_REPORT_PATH)
    args = parser.parse_args()

    results = run_all_cases(
        args.cases,
        retriever_mode=args.retriever_mode,
        top_k=args.top_k,
    )
    write_report(results, args.report)
    write_json_report(results, args.json_output)
    # 第一版 eval 是观察型 release check：失败样本写入报告，不用退出码做强门禁。
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
