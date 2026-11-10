"""Blind-solve all 43 records and save unreported defect candidates."""

from __future__ import annotations

import json
import os
from pathlib import Path

from .answer_checks import compare_answers
from .checks import deterministic_checks, findings_as_dicts
from .data import group_reports, load_dataset
from .llm import GroqCalls, load_local_env


def main() -> None:
    root = Path(__file__).resolve().parents[1]
    load_local_env(root)
    questions, reports, _taxonomy = load_dataset(root / "data")
    cases = group_reports(questions, reports)
    try:
        client = GroqCalls(root, root / "data" / "llm_cache", os.getenv("GROQ_MODEL", "openai/gpt-oss-120b"))
    except RuntimeError as error:
        raise SystemExit(f"Cannot run the all-question solver scan: {error}") from error
    candidates: list[dict] = []
    cache_hits = 0

    for question_id, case in cases.items():
        question = case["question"]
        solvers = []
        for run_number in (1, 2):
            result, cached = client.solve_blindly(question, run_number)
            solvers.append(result)
            cache_hits += int(cached)
        findings = deterministic_checks(question, case["parsed"])
        comparison = compare_answers(question, solvers)
        if case["reports"]:
            continue
        structural = [finding for finding in findings if finding.code in {
            "blank_option", "duplicate_options", "option_count", "invalid_answer",
            "type_mismatch", "invalid_mathml",
        }]
        independently_confirmed_key_mismatch = (
            comparison["solvers_agree"]
            and comparison["solution_confidence"] >= 0.9
            and comparison["solvers_match_solution"]
            and not comparison["key_matches_solution"]
        )
        if structural or independently_confirmed_key_mismatch:
            candidates.append({
                "questionId": question_id,
                "candidate_type": "answer_key" if independently_confirmed_key_mismatch else structural[0].code,
                "deterministic_findings": findings_as_dicts(findings),
                "answer_comparison": comparison,
                "review_status": "candidate_only_faculty_confirmation_required",
            })
        print(f"{question_id}: solved twice; {'reported' if case['reports'] else 'unreported'}")

    destination = root / "data" / "unreported_defects.json"
    destination.write_text(json.dumps(candidates, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Scanned {len(questions)} questions with two blind solves each; cache hits: {cache_hits}.")
    print(f"Wrote {len(candidates)} unreported candidates to {destination.relative_to(root)}.")


if __name__ == "__main__":
    main()
