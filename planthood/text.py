"""Shared text-cleaning helpers used by the scraper and the extractor.

The scraper's original word-fusion bug ("theblackbeansand") came from
``BeautifulSoup.get_text(strip=True)`` with its *default empty separator*, which
concatenates adjacent inline text nodes (e.g. bolded ingredient spans) with no space.
Always extract node text with :func:`node_text` (which passes ``separator=" "``) and
run free text through :func:`normalize_whitespace`.
"""

from __future__ import annotations

import re

# Straight + curly apostrophe, so patterns match both "What's" and "What’s".
APOSTROPHE = "['’]"


def normalize_whitespace(text: str) -> str:
    """Collapse all whitespace runs to single spaces and strip ends."""
    return re.sub(r"\s+", " ", text or "").strip()


def node_text(node) -> str:
    """Extract clean text from a BeautifulSoup node without fusing inline words."""
    if node is None:
        return ""
    return normalize_whitespace(node.get_text(separator=" ", strip=True))
