import importlib.util
from pathlib import Path


def _load_runner():
    runner_path = Path(__file__).resolve().parents[2] / "eval" / "rag_retrieval_runner.py"
    spec = importlib.util.spec_from_file_location("rag_retrieval_runner", runner_path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def test_compute_metrics_counts_hits_recall_and_exclusions():
    runner = _load_runner()
    results = [
        runner.RagEvalResult(
            case_id="hit",
            passed=True,
            skipped=False,
            failures=[],
            items=[
                {"product_id": "p_1", "category": "数码电子", "brand": "华为"},
                {"product_id": "p_2", "category": "数码电子", "brand": "小米"},
            ],
            trace={
                "structured_candidate_count": 4,
                "retrieved_count": 2,
                "final_count": 2,
            },
            expected_product_ids=["p_1", "p_3"],
            expected_category="数码电子",
            expected_brand="华为",
            must_not_return_product_ids=["p_9"],
            allow_no_results=False,
        ),
        runner.RagEvalResult(
            case_id="no-results",
            passed=True,
            skipped=False,
            failures=[],
            items=[],
            trace={
                "structured_candidate_count": 0,
                "retrieved_count": 0,
                "final_count": 0,
            },
            expected_product_ids=[],
            expected_category=None,
            expected_brand=None,
            must_not_return_product_ids=[],
            allow_no_results=True,
        ),
    ]

    metrics = runner.compute_metrics(results)

    assert metrics["case_pass_rate"] == 1.0
    assert metrics["hit@k"] == 1.0
    assert metrics["recall@k"] == 0.5
    assert metrics["category_hit_rate"] == 1.0
    assert metrics["brand_hit_rate"] == 1.0
    assert metrics["no_results_rate"] == 0.5
    assert metrics["unexpected_no_results_count"] == 0
    assert metrics["negative_exclusion_hit_rate"] == 1.0
    assert metrics["candidate_count_avg"] == 2.0
    assert metrics["retrieved_count_avg"] == 1.0
    assert metrics["final_count_avg"] == 1.0


def test_write_report_includes_metrics_and_failed_cases(tmp_path):
    runner = _load_runner()
    result = runner.RagEvalResult(
        case_id="failed-case",
        passed=False,
        skipped=False,
        failures=["missing expected product"],
        items=[
            {
                "product_id": "p_2",
                "title": "测试商品",
                "brand": "小米",
                "rank": 1,
                "score": 0.8,
                "source": "keyword",
            }
        ],
        trace={"structured_candidate_count": 1, "retrieved_count": 1, "final_count": 1},
        expected_product_ids=["p_1"],
        expected_category="数码电子",
        expected_brand=None,
        must_not_return_product_ids=[],
        allow_no_results=False,
    )

    report_path = tmp_path / "rag_report.md"
    runner.write_report([result], report_path)

    report = report_path.read_text(encoding="utf-8")
    assert "# RAG Retrieval Eval Report" in report
    assert "case_pass_rate" in report
    assert "failed-case" in report
    assert "missing expected product" in report
