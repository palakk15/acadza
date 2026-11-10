"""Run deterministic checks, two blind solves, grouped triage, and guards."""

from __future__ import annotations

import json
import os
from pathlib import Path

from .checks import deterministic_checks, findings_as_dicts
from .answer_checks import compare_answers
from .comments import inspect_comment
from .data import group_reports, load_dataset
from .guards import validate_and_apply
from .llm import ClaudeCalls, load_local_env


def main() -> None:
    root = Path(__file__).resolve().parents[1]
    load_local_env(root)
    questions, reports, taxonomy = load_dataset(root / "data")
    cases = group_reports(questions, reports)
    model = os.getenv("ANTHROPIC_MODEL", "claude-haiku-4-5-20251001")
    try:
        client = ClaudeCalls(root, root / "data" / "llm_cache", model)
    except RuntimeError as error:
        raise SystemExit(f"Cannot run the LLM pipeline: {error}") from error
    results: list[dict] = []
    internal_cases: list[dict] = []

    for question_id, case in cases.items():
        group = case["reports"]
        if not group:
            continue
        question = case["question"]
        findings = findings_as_dicts(deterministic_checks(question, case["parsed"]))
        flags = [{"report_id": report["reportId"], **inspect_comment(report.get("comment", "")).__dict__} for report in group]

        # Run two separately cached solver calls. This deliberately receives only
        # question text and type; key, solution, and reports are excluded.
        solver_results = [client.solve_blindly(question, run_number=index)[0] for index in (1, 2)]
        answer_comparison = compare_answers(question, solver_results)
        safe_reports = [{key: report[key] for key in ("reportId", "questionId", "source", "reportedAt", "comment")} for report in group]
        proposal, triage_cached = client.triage(question, findings + [{"code": "answer_comparison", **answer_comparison}], solver_results, safe_reports, taxonomy, flags)
        solver_answers = list(answer_comparison["solver_answers"])
        # The answer-key guard treats the stored solution's explicit final answer
        # as a third independent vote. Missing or weak extraction forces review.
        solver_answers.append(answer_comparison["solution_final"] if answer_comparison["solution_confidence"] >= 0.9 else None)
        guard_result = None
        route = proposal.route
        if proposal.verdict == "defect":
            if not proposal.repair:
                route = "faculty_review"
            else:
                guard_result = validate_and_apply(
                    question,
                    proposal.model_dump(),
                    taxonomy,
                    solver_answers=solver_answers,
                )
                route = guard_result.route
                if proposal.edit is None and proposal.new_answer is None:
                    route = "faculty_review"
        elif proposal.verdict in {"no_error", "already_fixed", "not_actionable"}:
            route = "no_change"
        else:
            # App, display, language, or taxonomy exceptions must not be
            # silently auto-routed as content edits. Keep them reviewable.
            route = "faculty_review" if proposal.route == "auto_apply" else proposal.route

        replies = {item.report_id: item.text for item in proposal.student_replies}
        expected_ids = {report["reportId"] for report in group}
        if set(replies) != expected_ids:
            raise ValueError(f"Triage replies do not match reports for question {question_id}.")

        for report in group:
            proposed_edit = proposal.edit.model_dump() if proposal.edit else None
            if proposed_edit is None and proposal.new_answer is not None:
                old_answer = (question.get(question.get("questionType")) or {}).get("answer")
                proposed_edit = {
                    "field": "answer",
                    "find": json.dumps(old_answer, ensure_ascii=False),
                    "replace": json.dumps(proposal.new_answer, ensure_ascii=False),
                }
            results.append({
                "reportId": report["reportId"],
                "questionId": question_id,
                "verdict": proposal.verdict,
                "repair": proposal.repair,
                "edit": proposed_edit,
                "route": route,
                "confidence": proposal.confidence,
                "evidence": proposal.evidence,
                "student_reply": replies[report["reportId"]],
            })
        internal_cases.append({
            "questionId": question_id,
            "question": question,
            "parsed": {
                "stem": case["parsed"].stem,
                "options": case["parsed"].options,
                "question_type": case["parsed"].question_type,
            },
            "reports": safe_reports,
            "comment_flags": flags,
            "deterministic_findings": findings,
            "solver_results": solver_results,
            "answer_comparison": answer_comparison,
            "proposal": proposal.model_dump(),
            "guard_outcomes": guard_result.outcomes if guard_result else [],
            "route": route,
            "triage_cache_hit": triage_cached,
        })
        print(f"{question_id}: {len(group)} report(s), {proposal.verdict}, {route}")

    results.sort(key=lambda item: item["reportId"])
    (root / "results.json").write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8")
    (root / "data" / "internal_cases.json").write_text(json.dumps(internal_cases, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Wrote real model-backed results for {len(results)} reports using {model}.")


if __name__ == "__main__":
    main()
