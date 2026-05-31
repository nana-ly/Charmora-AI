import json
from pathlib import Path


REQUIRED_FIELDS = {
    "id",
    "messages",
    "initial_state",
    "expected_intent",
    "expected_action",
    "expected_category",
    "expected_target_category",
    "expected_canonical_target_key",
    "must_include_constraints",
    "must_exclude_constraints",
    "expected_result_status",
    "expected_pending_restore_category",
    "expected_keeps_last_successful_items",
}


def test_shopping_agent_architecture_eval_cases_have_required_fields():
    cases_path = (
        Path(__file__).resolve().parents[2]
        / "eval"
        / "shopping_agent_architecture_cases.jsonl"
    )
    lines = cases_path.read_text(encoding="utf-8").splitlines()

    assert len(lines) >= 8

    seen_ids = set()
    for line in lines:
        case = json.loads(line)
        assert REQUIRED_FIELDS <= case.keys()
        assert case["id"] not in seen_ids
        seen_ids.add(case["id"])
        assert isinstance(case["messages"], list)
        assert case["messages"]
        assert all(isinstance(message, str) and message for message in case["messages"])
        assert isinstance(case["initial_state"], dict)
        assert isinstance(case["must_include_constraints"], list)
        assert isinstance(case["must_exclude_constraints"], list)
        assert isinstance(case["expected_keeps_last_successful_items"], bool)


def _load_eval_runner():
    import importlib.util

    runner_path = (
        Path(__file__).resolve().parents[2] / "eval" / "shopping_agent_runner.py"
    )
    spec = importlib.util.spec_from_file_location("shopping_agent_runner", runner_path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def test_eval_runner_loads_architecture_cases():
    module = _load_eval_runner()

    cases = module.load_cases(
        Path(__file__).resolve().parents[2]
        / "eval"
        / "shopping_agent_architecture_cases.jsonl"
    )

    assert len(cases) >= 9
    assert cases[0]["id"] == "recommend_phone_budget"


def test_eval_cases_include_compare_baseline():
    cases_path = (
        Path(__file__).resolve().parents[2]
        / "eval"
        / "shopping_agent_architecture_cases.jsonl"
    )
    cases = [
        json.loads(line)
        for line in cases_path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]

    compare_case = next(case for case in cases if case["id"] == "compare_first_two_phone_items")

    assert compare_case["expected_intent"] == "compare"
    assert compare_case["expected_action"] == "compare"
    assert compare_case["initial_state"]["last_items"][0]["product_id"] == "phone_a"
    assert compare_case["must_include_constraints"] == ["compare_item_indexes=[1,2]"]
    assert compare_case["must_exclude_constraints"] == ["recommendation_not_called"]


def test_eval_runner_executes_one_case():
    module = _load_eval_runner()

    case = module.load_cases(
        Path(__file__).resolve().parents[2]
        / "eval"
        / "shopping_agent_architecture_cases.jsonl"
    )[0]
    result = module.run_case(case)

    assert result.case_id == case["id"]
    assert isinstance(result.passed, bool)
    assert "intent" in result.response_state


def test_eval_runner_writes_report(tmp_path):
    module = _load_eval_runner()

    results = [
        module.EvalResult(
            case_id="case-1",
            passed=True,
            failures=[],
            response_state={"intent": "recommend"},
        )
    ]
    report_path = tmp_path / "report.md"
    module.write_report(results, report_path)

    report_text = report_path.read_text(encoding="utf-8")
    assert "# Shopping Agent Eval Report" in report_text
    assert "case-1" in report_text
