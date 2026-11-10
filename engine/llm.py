"""Minimal Anthropic Messages API wrapper with deterministic disk caching."""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

from anthropic import Anthropic

from .cache import DiskCache
from .comments import quote_comment
from .schemas import TriageProposal


def load_local_env(project_root: Path) -> None:
    """Read simple KEY=value entries without overriding the process environment."""
    path = project_root / ".env"
    if not path.exists():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key, value = key.strip(), value.strip().strip('"\'')
        if key and key not in os.environ:
            os.environ[key] = value


def _schema_for_triage(taxonomy: dict[str, Any]) -> dict[str, Any]:
    return {
        "type": "object",
        "additionalProperties": False,
        "required": ["verdict", "repair", "edit", "new_answer", "confidence", "evidence", "student_replies", "route"],
        "properties": {
            "verdict": {"type": "string", "enum": list(taxonomy["verdicts"])},
            "repair": {"anyOf": [
                {"type": "string", "enum": list(taxonomy["repairs"])},
                {"type": "null"},
            ]},
            "edit": {"anyOf": [
                {"type": "object", "additionalProperties": False, "required": ["field", "find", "replace"], "properties": {
                    "field": {"type": "string"}, "find": {"type": "string"}, "replace": {"type": "string"}
                }},
                {"type": "null"},
            ]},
            "new_answer": {"anyOf": [
                {"type": "string"}, {"type": "array", "items": {"type": "string"}}, {"type": "null"}
            ]},
            "confidence": {"type": "number", "minimum": 0, "maximum": 1},
            "evidence": {"type": "string"},
            "student_replies": {"type": "array", "items": {
                "type": "object", "additionalProperties": False, "required": ["report_id", "text"],
                "properties": {"report_id": {"type": "string"}, "text": {"type": "string"}}
            }},
            "route": {"type": "string", "enum": ["auto_apply", "faculty_review", "no_change"]},
        },
    }


class ClaudeCalls:
    def __init__(self, project_root: Path, cache_dir: Path, model: str) -> None:
        load_local_env(project_root)
        import os
        if not os.getenv("ANTHROPIC_API_KEY"):
            raise RuntimeError("ANTHROPIC_API_KEY is missing. Set it in .env or the process environment; no LLM calls were made.")
        self.client = Anthropic()
        self.cache = DiskCache(cache_dir)
        self.model = model
        self.prompts = project_root / "prompts"

    def _tool_call(self, operation: str, system: str, user_payload: Any, schema: dict[str, Any]) -> tuple[dict, bool]:
        request = {"model": self.model, "operation": operation, "system": system, "input": user_payload, "schema": schema}

        def call() -> dict:
            response = self.client.messages.create(
                model=self.model,
                max_tokens=1300,
                system=system,
                messages=[{"role": "user", "content": json.dumps(user_payload, ensure_ascii=False)}],
                tools=[{"name": "submit_result", "description": "Return the requested structured result.", "input_schema": schema}],
                tool_choice={"type": "tool", "name": "submit_result"},
            )
            for block in response.content:
                if block.type == "tool_use":
                    return block.input
            raise RuntimeError("Claude returned no structured tool result.")

        return self.cache.get_or_create(request, call)

    def solve_blindly(self, question: dict[str, Any], run_number: int = 1) -> tuple[dict, bool]:
        system = (self.prompts / "solver_v1.md").read_text(encoding="utf-8")
        payload = {
            "question_type": question.get("questionType"),
            "question": (question.get(question.get("questionType")) or {}).get("question", ""),
        }
        schema = {"type": "object", "additionalProperties": False, "required": ["answer", "reasoning", "ambiguous"], "properties": {
            "answer": {"anyOf": [{"type": "string"}, {"type": "array", "items": {"type": "string"}}]},
            "reasoning": {"type": "string"}, "ambiguous": {"type": "boolean"},
        }}
        return self._tool_call(f"blind_solver_run_{run_number}", system, payload, schema)

    def triage(self, question: dict[str, Any], findings: list[dict], solvers: list[dict], reports: list[dict], taxonomy: dict, comment_flags: list[dict] | None = None) -> tuple[TriageProposal, bool]:
        system = (self.prompts / "triage_v1.md").read_text(encoding="utf-8")
        kind = question.get("questionType")
        content = question.get(kind) or {}
        comments = [{"report_id": r["reportId"], "comment": quote_comment(r.get("comment", ""))} for r in reports]
        payload = {
            "question_type": kind,
            "question": content.get("question", ""),
            "stored_solution": content.get("solution", ""),
            "stored_answer": content.get("answer"),
            "deterministic_findings": findings,
            "blind_solver_results": solvers,
            "comments": comments,
            "comment_flags": comment_flags or [],
            "allowed_verdicts": taxonomy["verdicts"],
            "allowed_repairs": taxonomy["repairs"],
        }
        raw, cached = self._tool_call("grouped_triage", system, payload, _schema_for_triage(taxonomy))
        parsed = TriageProposal.model_validate(raw)
        if parsed.verdict not in taxonomy["verdicts"] or (parsed.repair and parsed.repair not in taxonomy["repairs"]):
            raise ValueError("Model output used a verdict or repair outside the taxonomy.")
        return parsed, cached
