"""Code-level safety checks for every proposed automated repair."""

from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass, field
import re
from typing import Any

from bs4 import BeautifulSoup

from .parser import parse_question
from .markup import mathml_is_valid


@dataclass
class GuardResult:
    accepted: bool
    route: str
    applied_question: dict[str, Any]
    outcomes: list[dict[str, str]] = field(default_factory=list)


def _target(question: dict[str, Any], field_name: str) -> tuple[dict, str]:
    if field_name == "questionType":
        return question, field_name
    if field_name == "answer":
        kind = question.get("questionType")
        return question.get(kind) or {}, field_name
    kind = question.get("questionType")
    if field_name in {"question", "solution"}:
        return question.get(kind) or {}, field_name
    raise ValueError(f"Unsupported edit field: {field_name}")


def _mathml_valid(markup: str) -> bool:
    return mathml_is_valid(markup)


def _symbols(value: str) -> list[str]:
    return re.findall(r"\d+(?:\.\d+)?|[^\w\s<>/]+", value)


def _valid_answer_shape(question_type: str, answer: Any) -> bool:
    if question_type == "scq":
        return isinstance(answer, str) and answer in "ABCD"
    if question_type == "mcq":
        return isinstance(answer, list) and bool(answer) and all(isinstance(item, str) and item in "ABCD" for item in answer)
    if question_type == "integerQuestion":
        return re.fullmatch(r"-?\d+(?:\.\d+)?", str(answer or "")) is not None
    return False


def _reject(outcomes: list[dict[str, str]], code: str, detail: str, current: dict) -> GuardResult:
    outcomes.append({"guard": code, "status": "failed", "detail": detail})
    return GuardResult(False, "faculty_review", current, outcomes)


def validate_and_apply(
    question: dict[str, Any],
    proposal: dict[str, Any],
    taxonomy: dict[str, Any],
    solver_answers: list[Any] | None = None,
    confidence_threshold: float = 0.95,
    max_diff_ratio: float = 0.35,
) -> GuardResult:
    """Validate a suggestion, apply it to a copy, and downgrade unsafe auto routes."""
    current = deepcopy(question)
    outcomes: list[dict[str, str]] = []
    repair_name = proposal.get("repair")
    repair = taxonomy.get("repairs", {}).get(repair_name)
    if not repair:
        return _reject(outcomes, "known_repair", "Repair is not present in the taxonomy.", current)
    edit = proposal.get("edit")
    new_answer = proposal.get("new_answer")

    if new_answer is not None:
        if "answer" not in repair.get("fields", []):
            return _reject(outcomes, "field_scope", "This repair cannot change the answer field.", current)
        kind = current.get("questionType")
        if not _valid_answer_shape(kind, new_answer):
            return _reject(outcomes, "answer_shape", "Proposed answer does not match the question type.", current)
        payload = current.get(kind) or {}
        payload["answer"] = new_answer
        outcomes.append({"guard": "field_scope", "status": "passed", "detail": "answer"})
        edit = None

    if edit:
        field_name = edit.get("field")
        if field_name not in repair.get("fields", []):
            return _reject(outcomes, "field_scope", "Edit field is outside this repair's allowed fields.", current)
        try:
            target, key = _target(current, field_name)
        except ValueError as error:
            return _reject(outcomes, "field_supported", str(error), current)
        original = target.get(key)
        find = edit.get("find")
        replacement = edit.get("replace")
        if not isinstance(original, str) or not isinstance(find, str) or not find:
            return _reject(outcomes, "find_once", "Text edits require non-empty find text and a string target.", current)
        occurrences = original.count(find)
        if occurrences != 1:
            return _reject(outcomes, "find_once", f"Find text occurs {occurrences} times; exactly one is required.", current)
        changed = original.replace(find, replacement, 1)
        if field_name == "answer" and not _valid_answer_shape(current.get("questionType", ""), changed):
            return _reject(outcomes, "answer_shape", "Edited answer does not match the question type.", current)
        if len(changed) > max(200, len(original) * 1.35) or len(changed) > 1200:
            return _reject(outcomes, "edit_size", "Proposed replacement is too large for a surgical edit.", current)
        ratio = (len(find) + len(replacement)) / max(1, len(original))
        if ratio > max_diff_ratio:
            return _reject(outcomes, "diff_ratio", "Proposed edit changes too much of the target field.", current)
        outcomes.append({"guard": "field_scope", "status": "passed", "detail": field_name})
        outcomes.append({"guard": "find_once", "status": "passed", "detail": "Unique target found."})
        target[key] = changed

        if field_name in {"question", "solution"}:
            if not _mathml_valid(original) or not _mathml_valid(changed):
                return _reject(outcomes, "html_mathml_valid", "Original or edited HTML/MathML did not parse safely.", current)
            if len(BeautifulSoup(original, "lxml").find_all("math")) != len(BeautifulSoup(changed, "lxml").find_all("math")):
                return _reject(outcomes, "mathml_preserved", "Edit changed the number of MathML expressions.", current)
            outcomes.append({"guard": "html_mathml_valid", "status": "passed", "detail": "All MathML fragments parse."})
            outcomes.append({"guard": "outside_edit_unchanged", "status": "passed", "detail": "Only the unique requested substring changed."})
        if repair_name == "option_repair" and field_name == "question":
            before_stem = parse_question(question).stem
            after_stem = parse_question(current).stem
            if before_stem != after_stem:
                return _reject(outcomes, "option_stem_unchanged", "An option repair changed the question stem.", current)
            outcomes.append({"guard": "option_stem_unchanged", "status": "passed", "detail": "Question stem is unchanged."})
        if repair_name == "spelling":
            if _symbols(original) != _symbols(changed):
                return _reject(outcomes, "spelling_symbols_unchanged", "Spelling edit changed a number or symbol.", current)
            outcomes.append({"guard": "spelling_symbols_unchanged", "status": "passed", "detail": "Numbers and symbols are unchanged."})
    elif new_answer is None:
        outcomes.append({"guard": "field_scope", "status": "passed", "detail": "No text edit proposed."})

    if new_answer is not None or (edit and edit.get("field") == "answer"):
        if not (solver_answers and len(solver_answers) >= 2):
            return _reject(outcomes, "solver_agreement", "Answer-key changes require at least two independent solver outputs.", current)
        candidate = new_answer
        if candidate is None:
            candidate = proposal["edit"].get("replace")
        if len(solver_answers) < 3 or any(answer != candidate for answer in solver_answers):
            outcomes.append({"guard": "solver_agreement", "status": "failed", "detail": "Solvers do not unanimously support the proposed answer."})
            route = "faculty_review"
        else:
            outcomes.append({"guard": "solver_agreement", "status": "passed", "detail": "Two or more solvers agree with the proposed answer."})
            route = proposal.get("route", "faculty_review")
    else:
        route = proposal.get("route", "faculty_review")

    if not repair.get("auto", False) and route == "auto_apply":
        outcomes.append({"guard": "repair_auto_policy", "status": "failed", "detail": "This repair always requires faculty approval."})
        route = "faculty_review"
    else:
        outcomes.append({"guard": "repair_auto_policy", "status": "passed", "detail": "Repair auto policy respected."})
    confidence = float(proposal.get("confidence", 0))
    if confidence < confidence_threshold and route == "auto_apply":
        outcomes.append({"guard": "confidence_threshold", "status": "failed", "detail": f"Confidence {confidence:.2f} is below {confidence_threshold:.2f}."})
        route = "faculty_review"
    else:
        outcomes.append({"guard": "confidence_threshold", "status": "passed", "detail": f"Confidence threshold {confidence_threshold:.2f} respected."})

    accepted = all(item["status"] == "passed" for item in outcomes)
    return GuardResult(accepted, route, current, outcomes)
