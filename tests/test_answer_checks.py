from engine.answer_checks import compare_answers, solution_final_answer


def test_extracts_explicit_option_from_solution():
    q = {"questionType": "scq", "scq": {"answer": "B", "solution": "<h3>The correct answer is (B).</h3>"}}
    assert solution_final_answer(q)["answer"] == "B"
    compared = compare_answers(q, [{"answer": "B"}, {"answer": "B"}])
    assert compared["key_matches_solution"]
    assert compared["solvers_match_solution"]


def test_uncertain_integer_solution_is_not_treated_as_proof():
    q = {"questionType": "integerQuestion", "integerQuestion": {"answer": "3113", "solution": "<p>Total area = 311.299 = 311.3</p>"}}
    comparison = compare_answers(q, [{"answer": "3113"}, {"answer": "3113"}])
    assert comparison["solution_final"] == "311.3"
    assert comparison["solution_confidence"] < 0.9
    assert not comparison["solvers_match_solution"]
