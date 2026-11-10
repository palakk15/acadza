"""Parse production question HTML while retaining inline MathML markup."""

from __future__ import annotations

from dataclasses import dataclass
import re
from typing import Any

from bs4 import BeautifulSoup, NavigableString, Tag


@dataclass
class ParsedQuestion:
    """Readable question text plus any answer choices found in its HTML."""

    stem: str
    options: dict[str, str]
    question_type: str
    mathml_count: int


MATH_TAGS = {
    "math", "mi", "mn", "mo", "mrow", "mfrac", "msup", "msub",
    "mover", "munder", "munderover", "mtext", "mspace", "mstyle",
    "mtable", "mtr", "mtd", "msqrt", "mfenced", "semantics",
    "annotation", "mroot", "mpadded", "menclose", "mphantom",
}


def _readable(node: Tag | NavigableString) -> str:
    """Turn layout HTML into text, but serialize each MathML subtree intact."""
    if isinstance(node, NavigableString):
        return str(node)
    if node.name == "math":
        return str(node)
    children = "".join(_readable(child) for child in node.children)
    if node.name in {"br", "p", "div", "h1", "h2", "h3", "li"}:
        return f" {children} "
    return children


def clean_question_html(markup: str) -> tuple[str, int]:
    """Remove layout HTML, preserve MathML, and return readable text."""
    soup = BeautifulSoup(markup or "", "lxml")
    mathml_count = len(soup.find_all("math"))
    text = _readable(soup)
    text = re.sub(r"[\t\r\n ]+", " ", text).strip()
    return text, mathml_count


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
