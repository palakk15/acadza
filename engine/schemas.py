"""Typed contracts shared by model output, guards, and saved case state."""

from __future__ import annotations

from typing import Literal
from pydantic import BaseModel, ConfigDict, Field


class EditProposal(BaseModel):
    model_config = ConfigDict(extra="forbid")
    field: str
    find: str
    replace: str


class StudentReply(BaseModel):
    model_config = ConfigDict(extra="forbid")
    report_id: str
    text: str


class TriageProposal(BaseModel):
    model_config = ConfigDict(extra="forbid")
    verdict: str
    repair: str | None = None
    edit: EditProposal | None = None
    new_answer: str | list[str] | None = None
    confidence: float = Field(ge=0, le=1)
    evidence: str
    student_replies: list[StudentReply]
    route: Literal["auto_apply", "faculty_review", "no_change"]
