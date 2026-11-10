"""Strict checks for MathML fragments embedded in forgiving HTML records."""

from __future__ import annotations

import html
import re

from lxml import etree


def mathml_is_valid(markup: str) -> bool:
    """Validate original MathML XML before BeautifulSoup can auto-repair it."""
    fragments = re.findall(r"<math\b[^>]*>.*?</math\s*>", markup or "", re.IGNORECASE | re.DOTALL)
    for fragment in fragments:
        try:
            etree.fromstring(html.unescape(fragment).encode("utf-8"))
        except etree.XMLSyntaxError:
            return False
    return True
