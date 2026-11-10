from pathlib import Path

from engine.llm import ClaudeCalls


def test_blind_solver_receives_only_question_and_type(tmp_path: Path):
    calls = ClaudeCalls.__new__(ClaudeCalls)
    calls.prompts = Path(__file__).resolve().parents[1] / "prompts"
    seen = []
    calls._tool_call = lambda operation, system, payload, schema: (seen.append((operation, payload)) or ({"answer": "A"}, False))
    q = {
        "questionType": "scq",
        "scq": {"question": "<h3>Compute this (A) one (B) two (C) three (D) four</h3>", "answer": "B", "solution": "secret solution", "comment": "student claim"},
    }
    calls.solve_blindly(q, 1)
    calls.solve_blindly(q, 2)
    assert [item[0] for item in seen] == ["blind_solver_run_1", "blind_solver_run_2"]
    assert all(set(payload) == {"question_type", "question"} for _, payload in seen)
    assert all("secret solution" not in str(payload) and "student claim" not in str(payload) for _, payload in seen)
