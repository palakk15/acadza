"""Adversarial proposals confirm that safety decisions live in code."""

from copy import deepcopy

from engine.guards import validate_and_apply


TAXONOMY = {
    "repairs": {
        "spelling": {"fields": ["question", "solution"], "auto": True},
        "answer_key": {"fields": ["answer", "solution"], "auto": True},
        "option_repair": {"fields": ["question"], "auto": True},
        "identical_options": {"fields": [], "auto": False},
    }
}


def question() -> dict:
    return {
        "questionType": "scq",
        "scq": {
            "question": "<h3>A speling question (A) one (B) two (C) three (D) four</h3>",
            "solution": "<h3>Answer is A.</h3>",
            "answer": "A",
        },
        "errorHistory": [],
    }


def proposal(**updates) -> dict:
    base = {
        "verdict": "defect",
        "repair": "spelling",
        "edit": {"field": "question", "find": "speling", "replace": "spelling"},
        "confidence": 0.99,
        "route": "auto_apply",
    }
    base.update(updates)
    return base


def test_applies_unique_surgical_spelling_edit_to_copy():
    original = question()
    result = validate_and_apply(original, proposal(), TAXONOMY)
    assert result.accepted
    assert result.route == "auto_apply"
    assert result.applied_question["scq"]["question"].count("spelling") == 1
    assert original["scq"]["question"].count("speling") == 1


def test_rejects_field_outside_repair_scope():
    result = validate_and_apply(question(), proposal(edit={"field": "answer", "find": "A", "replace": "B"}), TAXONOMY)
    assert not result.accepted
    assert result.outcomes[-1]["guard"] == "field_scope"


def test_rejects_find_text_that_is_absent_or_ambiguous():
    missing = validate_and_apply(question(), proposal(edit={"field": "question", "find": "absent", "replace": "x"}), TAXONOMY)
    duplicate = validate_and_apply(question(), proposal(edit={"field": "question", "find": " ", "replace": "-"}), TAXONOMY)
    assert not missing.accepted and not duplicate.accepted
    assert missing.outcomes[-1]["guard"] == "find_once"
    assert duplicate.outcomes[-1]["guard"] == "find_once"


def test_rejects_whole_field_rewrite():
    result = validate_and_apply(question(), proposal(edit={"field": "question", "find": "speling", "replace": "A completely new rewritten question with many unrelated words"}), TAXONOMY)
    assert not result.accepted
    assert result.outcomes[-1]["guard"] in {"edit_size", "diff_ratio"}


def test_non_auto_repair_cannot_route_to_auto_apply():
    bad = proposal(repair="identical_options", edit=None)
    result = validate_and_apply(question(), bad, TAXONOMY)
    assert result.route == "faculty_review"
    assert any(item["guard"] == "repair_auto_policy" and item["status"] == "failed" for item in result.outcomes)


def test_answer_change_without_solver_agreement_is_review_only():
    bad = proposal(repair="answer_key", edit=None, new_answer="B")
    result = validate_and_apply(question(), bad, TAXONOMY, solver_answers=["B", "A"])
    assert result.applied_question["scq"]["answer"] == "B"
    assert result.route == "faculty_review"
    assert any(item["guard"] == "solver_agreement" and item["status"] == "failed" for item in result.outcomes)


def test_answer_change_requires_two_solver_runs():
    result = validate_and_apply(question(), proposal(repair="answer_key", edit=None, new_answer="B"), TAXONOMY, solver_answers=["B"])
    assert not result.accepted
    assert result.outcomes[-1]["guard"] == "solver_agreement"


def test_answer_change_also_requires_solution_agreement():
    bad = proposal(repair="answer_key", edit=None, new_answer="B")
    result = validate_and_apply(question(), bad, TAXONOMY, solver_answers=["B", "B", "A"])
    assert result.route == "faculty_review"
    assert any(item["guard"] == "solver_agreement" and item["status"] == "failed" for item in result.outcomes)


def test_answer_change_rejects_value_invalid_for_question_type():
    result = validate_and_apply(question(), proposal(repair="answer_key", edit=None, new_answer="E"), TAXONOMY, solver_answers=["E", "E", "E"])
    assert not result.accepted
    assert result.outcomes[-1]["guard"] == "answer_shape"


def test_low_confidence_auto_proposal_is_downgraded():
    result = validate_and_apply(question(), proposal(confidence=0.72), TAXONOMY)
    assert result.route == "faculty_review"
    assert any(item["guard"] == "confidence_threshold" and item["status"] == "failed" for item in result.outcomes)


def test_option_repair_must_keep_stem_identical():
    bad = proposal(repair="option_repair", edit={"field": "question", "find": "A speling", "replace": "A rewritten"})
    result = validate_and_apply(question(), bad, TAXONOMY)
    assert not result.accepted
    assert result.outcomes[-1]["guard"] == "option_stem_unchanged"


def test_spelling_repair_cannot_change_numbers_or_symbols():
    q = question()
    q["scq"]["question"] = "<h3>A 3.2 m question (A) one (B) two (C) three (D) four</h3>"
    bad = proposal(edit={"field": "question", "find": "3.2", "replace": "4.2"})
    result = validate_and_apply(q, bad, TAXONOMY)
    assert not result.accepted
    assert result.outcomes[-1]["guard"] == "spelling_symbols_unchanged"


def test_malformed_mathml_edit_is_rejected():
    q = question()
    q["scq"]["solution"] = "<math><mfrac><mn>1</mn><mn>2</mn></mfrac></math>"
    bad = proposal(edit={"field": "solution", "find": "</mfrac>", "replace": ""})
    result = validate_and_apply(q, bad, TAXONOMY)
    assert not result.accepted
    assert result.outcomes[-1]["guard"] == "html_mathml_valid"
