import importlib.util
from pathlib import Path


def _load_runner():
    runner_path = Path(__file__).resolve().parents[2] / "eval" / "context_memory_runner.py"
    spec = importlib.util.spec_from_file_location("context_memory_runner", runner_path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def test_context_eval_runner_loads_cases():
    runner = _load_runner()

    cases = runner.load_cases(
        Path(__file__).resolve().parents[2] / "eval" / "context_memory_cases.jsonl"
    )

    assert len(cases) >= 4
    assert cases[0]["id"] == "phone_budget_then_brand_exclusion"


def test_context_eval_metrics_count_pass_rate():
    runner = _load_runner()

    metrics = runner.compute_metrics(
        [
            runner.ContextMemoryEvalResult("a", True, [], {}),
            runner.ContextMemoryEvalResult("b", False, ["missing budget"], {}),
        ]
    )

    assert metrics["case_pass_rate"] == 0.5
    assert metrics["failed_count"] == 1
    assert metrics["case_count"] == 2


def test_context_eval_thresholds_fail_below_minimum():
    runner = _load_runner()

    failures = runner.assert_thresholds(
        {"case_pass_rate": 0.75, "failed_count": 1, "case_count": 4},
        min_pass_rate=1.0,
    )

    assert failures == ["case_pass_rate expected >= 1.0, got 0.75"]


def test_context_eval_report_includes_metrics_and_failures(tmp_path):
    runner = _load_runner()
    report_path = tmp_path / "context_report.md"

    runner.write_report(
        [
            runner.ContextMemoryEvalResult(
                case_id="failed-case",
                passed=False,
                failures=["missing target_category"],
                response_state={"intent": "recommend"},
            )
        ],
        report_path,
    )

    report = report_path.read_text(encoding="utf-8")
    assert "# Context Memory Eval Report" in report
    assert "case_pass_rate" in report
    assert "failed-case" in report
    assert "missing target_category" in report
