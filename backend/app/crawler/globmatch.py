"""Linear-time wildcard matching used for robots.txt rules and crawl include/exclude patterns.

Regular expressions built from untrusted input (a site's robots.txt, a user's pattern) can be made to
backtrack catastrophically and freeze the single-process server. This matcher supports only literal
text and ``*`` (any run of characters), with optional anchors, and never backtracks: it greedily takes the
leftmost occurrence of each literal piece, which is optimal for this pattern language.
"""
from __future__ import annotations

MAX_PATTERN_LENGTH = 1000


def _match(parts: list[str], text: str, start: bool, end: bool) -> bool:
    first = parts[0]
    if start:
        if not text.startswith(first):
            return False
        pos = len(first)
    else:
        i = text.find(first)
        if i < 0:
            return False
        pos = i + len(first)
    if len(parts) == 1:
        if end:
            return text == first if start else text.endswith(first)
        return True
    for mid in parts[1:-1]:
        if mid:
            i = text.find(mid, pos)
            if i < 0:
                return False
            pos = i + len(mid)
    last = parts[-1]
    if not last:
        return True
    if end:
        return text.endswith(last) and len(text) - len(last) >= pos
    return text.find(last, pos) >= 0


def robots_match(pattern: str, path: str) -> bool:
    """RFC 9309 rule matching: prefix match from the start of the path, ``*`` wildcard, trailing ``$`` anchor."""
    pattern = pattern[:MAX_PATTERN_LENGTH]
    end = pattern.endswith("$")
    if end:
        pattern = pattern[:-1]
    return _match(pattern.split("*"), path, start=True, end=end)


def pattern_search(pattern: str, text: str) -> bool:
    """Crawl filter semantics: the text contains ``pattern``; ``*`` is a wildcard, ``^`` / ``$`` anchor the ends."""
    pattern = pattern[:MAX_PATTERN_LENGTH]
    start = pattern.startswith("^")
    end = pattern.endswith("$") and len(pattern) > start
    core = pattern[1 if start else 0: len(pattern) - 1 if end else len(pattern)]
    return _match(core.split("*"), text, start=start, end=end)
