"""Treat report comments as untrusted data and flag junk/injection attempts."""

from __future__ import annotations

from dataclasses import dataclass
import re


@dataclass(frozen=True)
class CommentFlags:
    injection: bool
    gibberish: bool


_INJECTION = re.compile(
    r"\b(ignore|disregard|override)\b.{0,60}\b(instructions|rules|previous)\b|"
    r"\b(admin|system)\s+bot\b|\bmark\s+this\s+report\b",
    re.IGNORECASE,
)


def inspect_comment(comment: str) -> CommentFlags:
    text = (comment or "").strip()
    letters = re.sub(r"[^a-z]", "", text.lower())
    injection = bool(_INJECTION.search(text))
    # Short non-words and keyboard mashes are junk; ordinary short feedback is not.
    keyboard_mash = bool(re.fullmatch(r"(?i)(?:asdfgh|qwerty|zxcvbn|asdf|qwer|zxcv)+", text))
    gibberish = bool(text) and not injection and (len(letters) < 3 or keyboard_mash)
    return CommentFlags(injection, gibberish)


def quote_comment(comment: str) -> str:
    """Create an explicitly delimited data block for a later model prompt."""
    safe = (comment or "").replace("<<<", "‹‹‹").replace(">>>", "›››")
    return f"<<<UNTRUSTED STUDENT COMMENT>>>\n{safe}\n<<<END STUDENT COMMENT>>>"
