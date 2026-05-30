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
