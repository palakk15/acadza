"""Parse production question HTML while retaining inline MathML markup."""

from __future__ import annotations

from dataclasses import dataclass
from html.parser import HTMLParser
import re
from typing import Any


@dataclass
class ParsedQuestion:
    """Readable question text plus any answer choices found in its HTML."""

    stem: str
    options: dict[str, str]
    question_type: str
    mathml_count: int


class _QuestionHTML(HTMLParser):
    """Drop presentation tags but serialize MathML tags so browsers can render it."""

    MATH_TAGS = {
        "math", "mi", "mn", "mo", "mrow", "mfrac", "msup", "msub",
        "mover", "munder", "munderover", "mtext", "mspace", "mstyle",
        "mtable", "mtr", "mtd", "msqrt", "mfenced", "semantics",
        "annotation", "mroot", "mpadded", "menclose", "mphantom",
    }

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.parts: list[str] = []
        self.math_depth = 0
        self.mathml_count = 0

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag == "math":
            self.math_depth += 1
            self.mathml_count += 1
        if self.math_depth and tag in self.MATH_TAGS:
            self.parts.append(self.get_starttag_text() or f"<{tag}>")
        elif tag in {"br", "p", "div", "h1", "h2", "h3", "li"}:
            self.parts.append(" ")

    def handle_startendtag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if self.math_depth and tag in self.MATH_TAGS:
            self.parts.append(self.get_starttag_text() or f"<{tag}/>")

    def handle_endtag(self, tag: str) -> None:
        if self.math_depth and tag in self.MATH_TAGS:
            self.parts.append(f"</{tag}>")
        if tag == "math" and self.math_depth:
            self.math_depth -= 1
        elif tag in {"p", "div", "h1", "h2", "h3", "li"}:
            self.parts.append(" ")

    def handle_data(self, data: str) -> None:
        self.parts.append(data)


def clean_question_html(markup: str) -> tuple[str, int]:
    """Remove layout HTML, preserve MathML, and return readable text."""
    parser = _QuestionHTML()
    parser.feed(markup or "")
    parser.close()
    text = "".join(parser.parts)
    text = re.sub(r"[\t\r\n ]+", " ", text).strip()
    return text, parser.mathml_count


_OPTION_LABEL = re.compile(r"\(([A-D])\)\s*", re.IGNORECASE)


def split_options(text: str) -> tuple[str, dict[str, str]]:
    """Split standard (A)-(D) options when labels occur in the question HTML."""
    matches = list(_OPTION_LABEL.finditer(text))
    labels = [m.group(1).upper() for m in matches]
    if len(matches) < 2 or len(set(labels)) < 2:
        return text.strip(), {}

    stem = text[:matches[0].start()].strip()
    options: dict[str, str] = {}
    for index, match in enumerate(matches):
        end = matches[index + 1].start() if index + 1 < len(matches) else len(text)
        options[match.group(1).upper()] = text[match.end():end].strip(" \t\r\n.;")
    return stem, options


def parse_question(question: dict[str, Any]) -> ParsedQuestion:
    """Parse a production record, supporting scq, mcq, and integerQuestion."""
    question_type = str(question.get("questionType", "unknown"))
    payload = question.get(question_type) or {}
    cleaned, math_count = clean_question_html(payload.get("question", ""))
    stem, options = split_options(cleaned)
    return ParsedQuestion(stem, options, question_type, math_count)
