"""Load the supplied JSON and attach reports to their question records."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .parser import ParsedQuestion, parse_question


def read_json(path: Path) -> Any:
    with path.open(encoding="utf-8") as source:
        return json.load(source)


def load_dataset(data_dir: Path) -> tuple[list[dict], list[dict], dict]:
    """Read the three assignment inputs without modifying them."""
    questions = read_json(data_dir / "questions.json")
    reports = read_json(data_dir / "reports.json")
    taxonomy = read_json(data_dir / "taxonomy.json")
    return questions, reports, taxonomy


def group_reports(questions: list[dict], reports: list[dict]) -> dict[str, dict[str, Any]]:
    """Return one case per question, with its parsed content and all reports."""
    cases: dict[str, dict[str, Any]] = {}
    for question in questions:
        case_id = question.get("_id")
        if case_id:
            cases[case_id] = {
                "question": question,
                "parsed": parse_question(question),
                "reports": [],
            }
    for report in reports:
        case = cases.get(report.get("questionId"))
        if case is not None:
            case["reports"].append(report)
    return cases


def format_summary(cases: dict[str, dict[str, Any]], reports: list[dict]) -> str:
    """Print concise, inspectable output for the foundation phase."""
    reported = [case for case in cases.values() if case["reports"]]
    option_counts: dict[int, int] = {}
    type_counts: dict[str, int] = {}
    math_count = 0
    for case in cases.values():
        parsed: ParsedQuestion = case["parsed"]
        option_counts[len(parsed.options)] = option_counts.get(len(parsed.options), 0) + 1
        kind = parsed.question_type
        type_counts[kind] = type_counts.get(kind, 0) + 1
        math_count += parsed.mathml_count
    multi_reported = sum(len(case["reports"]) > 1 for case in reported)
    orphan_count = sum(report["questionId"] not in cases for report in reports)
    return "\n".join([
        f"Loaded {len(cases)} questions and {len(reports)} reports.",
        f"Grouped {len(reported)} reported questions; {multi_reported} have multiple reports.",
        f"Question types: {', '.join(f'{k}={v}' for k, v in sorted(type_counts.items()))}.",
        f"Option counts: {', '.join(f'{k}={v}' for k, v in sorted(option_counts.items()))} (0 means no parsed A-D choices).",
        f"Preserved {math_count} MathML blocks across all questions.",
        f"Reports with an unknown questionId: {orphan_count}.",
    ])
