"""Deterministic issue checks that do not need an LLM."""

from __future__ import annotations

from dataclasses import dataclass, asdict
import html
import re
from typing import Any

from .parser import ParsedQuestion, clean_question_html
from .markup import mathml_is_valid


@dataclass
class Finding:
    code: str
    severity: str
    detail: str


def _plain(value: str) -> str:
    return re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]*>", " ", value or ""))).strip()


def _choice_values(markup: str) -> dict[str, str]:
    clean, _ = clean_question_html(markup)
    labels = list(re.finditer(r"\(([A-D])\)\s*", clean, re.IGNORECASE))
    return {
        match.group(1).upper(): clean[match.end(): labels[index + 1].start() if index + 1 < len(labels) else len(clean)].strip()
        for index, match in enumerate(labels)
    }


def deterministic_checks(question: dict[str, Any], parsed: ParsedQuestion) -> list[Finding]:
    kind = question.get("questionType", "")
    payload = question.get(kind) or {}
    q_html = payload.get("question", "")
    sol_html = payload.get("solution", "")
    findings: list[Finding] = []

    combined_text = f"{q_html}\n{sol_html}"
    if re.search(r"\\(?:frac|sqrt|begin|mathrm)\b|&lt;/?(?:div|span|math)", combined_text):
        findings.append(Finding("markup_leak", "medium", "Possible raw LaTeX or escaped HTML in content."))
    if not mathml_is_valid(q_html) or not mathml_is_valid(sol_html):
        findings.append(Finding("invalid_mathml", "high", "A MathML fragment is not well-formed XML; repair needs careful review."))
    if re.search(r"\(\s*(?:JEE|NEET|AIEEE|AIIMS)\s+(?:Main\s+)?\d{4}\s*\)", _plain(q_html), re.I):
        findings.append(Finding("exam_reference", "low", "Question contains an exam/source tag."))
    if re.search(r"\b(?:space for rough work|sample question|asdfgh)\b", _plain(combined_text), re.I):
        findings.append(Finding("noise", "low", "Question or solution contains a likely stray text fragment."))

    expected = {"scq": 4, "mcq": 4}.get(kind)
    if expected is not None:
        choices = _choice_values(q_html)
        for label in "ABCD":
            if label in choices and not _plain(choices[label]):
                findings.append(Finding("blank_option", "high", f"Option {label} is blank."))
        normalized: dict[str, list[str]] = {}
        for label, value in choices.items():
            text = _plain(value).casefold()
            if text:
                normalized.setdefault(text, []).append(label)
        for labels in normalized.values():
            if len(labels) > 1:
                findings.append(Finding("duplicate_options", "high", f"Options {', '.join(labels)} appear identical."))
        if len(choices) != expected:
            findings.append(Finding("option_count", "high", f"Expected {expected} options; parsed {len(choices)}."))

    answer = payload.get("answer")
    if kind == "scq" and answer not in list("ABCD"):
        findings.append(Finding("invalid_answer", "high", "SCQ answer must be one of A, B, C, or D."))
    elif kind == "mcq" and (not isinstance(answer, list) or not answer or any(a not in "ABCD" for a in answer)):
        findings.append(Finding("invalid_answer", "high", "MCQ answer must be a non-empty list of A-D labels."))
    elif kind == "integerQuestion" and not re.fullmatch(r"-?\d+(?:\.\d+)?", str(answer or "")):
        findings.append(Finding("invalid_answer", "high", "Integer-question answer is not numeric."))
    if kind not in {"scq", "mcq", "integerQuestion"} or kind not in question:
        findings.append(Finding("type_mismatch", "high", "Question type and stored payload do not agree."))
    if question.get("errorHistory"):
        findings.append(Finding("already_fixed", "medium", "The record has prior error-history entries; confirm whether the issue is already fixed."))
    return findings


def findings_as_dicts(findings: list[Finding]) -> list[dict[str, str]]:
    return [asdict(item) for item in findings]
