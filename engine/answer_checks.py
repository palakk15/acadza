"""Conservative extraction of explicit final answers from stored solutions."""

from __future__ import annotations

import re
from typing import Any

from bs4 import BeautifulSoup


def _solution_text(markup: str) -> str:
    soup = BeautifulSoup(markup or "", "lxml")
    return re.sub(r"\s+", " ", soup.get_text(" ", strip=True)).strip()


def solution_final_answer(question: dict[str, Any]) -> dict[str, Any]:
    """Return a low-risk explicit final answer, or None when unclear.

    This is intentionally conservative. An absent extraction is uncertainty, not
    evidence that the stored key is wrong.
    """
    kind = question.get("questionType")
    content = question.get(kind) or {}
    text = _solution_text(content.get("solution", ""))
    if kind in {"scq", "mcq"}:
        # Only accept explicit answer/option language, not every incidental (A).
        patterns = [
            r"(?:correct\s+answer|answer|correct\s+option|option)\s*(?:is|:|=)?\s*\(?([A-D])\)?\b",
            r"\(([A-D])\)\s*(?:is\s+the\s+)?(?:correct|right)\s+(?:answer|option)",
        ]
        matches = [m for pattern in patterns for m in re.finditer(pattern, text, re.IGNORECASE)]
        if matches:
            match = max(matches, key=lambda item: item.start())
            answer = match.group(1).upper()
            return {"answer": [answer] if kind == "mcq" else answer, "method": "explicit answer wording", "confidence": 0.9}
        return {"answer": None, "method": "no explicit final option detected", "confidence": 0.0}
    if kind == "integerQuestion":
        equalities = list(re.finditer(r"=\s*(-?\d+(?:\.\d+)?)\b", text))
        if equalities:
            return {"answer": equalities[-1].group(1), "method": "last explicit numeric equality", "confidence": 0.55}
        return {"answer": None, "method": "no final numeric equality detected", "confidence": 0.0}
    return {"answer": None, "method": "unsupported question type", "confidence": 0.0}


def compare_answers(question: dict[str, Any], solver_results: list[dict]) -> dict[str, Any]:
    kind = question.get("questionType")
    stored = (question.get(kind) or {}).get("answer")
    solution = solution_final_answer(question)
    solver_answers = [result.get("answer") for result in solver_results]
    normalized_solvers = [item if kind == "mcq" and isinstance(item, list) else str(item).upper() if kind == "scq" and item is not None else str(item) if item is not None else None for item in solver_answers]
    normalized_stored = stored if kind == "mcq" else str(stored).upper() if kind == "scq" else str(stored)
    normalized_solution = solution["answer"]
    if kind == "integerQuestion" and normalized_solution is not None:
        try:
            if float(normalized_solution).is_integer():
                normalized_solution = str(int(float(normalized_solution)))
        except ValueError:
            pass
    return {
        "stored_key": normalized_stored,
        "solution_final": normalized_solution,
        "solution_method": solution["method"],
        "solution_confidence": solution["confidence"],
        "solver_answers": normalized_solvers,
        "solvers_agree": len(normalized_solvers) >= 2 and all(item == normalized_solvers[0] for item in normalized_solvers),
        "key_matches_solution": normalized_solution is not None and normalized_stored == normalized_solution,
        "solvers_match_solution": normalized_solution is not None and all(item == normalized_solution for item in normalized_solvers),
    }
