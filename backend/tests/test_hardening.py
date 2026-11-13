"""Regression tests for the findings of the security review (denial of service, auth hardening, SSRF edges)."""
from __future__ import annotations

import re
import time

import pytest

from app.crawler.engine import CrawlConfig
from app.crawler.globmatch import pattern_search, robots_match
from app.crawler.robots import RobotsRules


# --------------------------------------------------------------------------------- wildcard matching
def _robots_regex(pattern: str) -> re.Pattern:
    """The regular expression the old implementation built; used as an oracle for benign patterns."""
    anchored = pattern.endswith("$")
    if anchored:
        pattern = pattern[:-1]
    return re.compile("".join(".*" if ch == "*" else re.escape(ch) for ch in pattern) + ("$" if anchored else ""))


ROBOTS_CASES = [
    ("/", "/anything"), ("/private", "/private/x"), ("/private", "/public"), ("/*.pdf$", "/a/b.pdf"),
    ("/*.pdf$", "/a/b.pdf?x=1"), ("/a*b*c", "/aXXbYYc"), ("/a*b*c", "/aXXcYYb"), ("/a*b*c$", "/abcX"),
    ("/*?", "/p?x=1"), ("/*?", "/p"), ("/a*", "/a"), ("/a*$", "/abc"), ("/a$", "/a"), ("/a$", "/ab"),
    ("/*a*a*a", "/aaa"), ("/*a*a*a", "/aa"), ("*", "/x"), ("/x*x$", "/x"), ("/x*x$", "/xx"),
]


@pytest.mark.parametrize(("pattern", "path"), ROBOTS_CASES)
def test_robots_match_agrees_with_regex_semantics(pattern, path):
    assert robots_match(pattern, path) == bool(_robots_regex(pattern).match(path))


def test_pattern_search_semantics():
    url = "https://example.com/blog/post?sort=asc"
    assert pattern_search("/blog/", url)
    assert pattern_search("?sort=", url)
    assert pattern_search("^https://example.com/blog", url)
    assert not pattern_search("^/blog", url)
    assert pattern_search("asc$", url)
    assert not pattern_search("post$", url)
    assert pattern_search("/blog/*sort=*", url)
    assert not pattern_search("/shop/", url)
    assert pattern_search("^https://example.com/blog/post?sort=asc$", url)


def test_hostile_robots_rules_cannot_stall_the_server():
    rules = RobotsRules("User-agent: *\nDisallow: /*a*a*a*a*a*a*a*a*b\n", 200)
    started = time.perf_counter()
    for _ in range(50):
        rules.allowed("https://example.com/" + "a" * 1500, "bot")
    assert time.perf_counter() - started < 1.0


def test_hostile_include_exclude_patterns_cannot_stall_the_server():
    cfg = CrawlConfig(exclude_patterns=["(a+)+$", "*a*a*a*a*a*a*a*a*a*b"], include_patterns=["(a|aa)+$"])
    started = time.perf_counter()
    text = "https://example.com/" + "a" * 1500 + "!"
    for p in cfg.exclude_patterns + cfg.include_patterns:
        for _ in range(50):
            pattern_search(p, text)
    assert time.perf_counter() - started < 1.0


def test_crawl_patterns_reject_control_characters_and_blanks():
    with pytest.raises(ValueError):
        CrawlConfig(exclude_patterns=["   "])
    with pytest.raises(ValueError):
        CrawlConfig(exclude_patterns=["/a\x00b"])
    with pytest.raises(ValueError):
        CrawlConfig(include_patterns=["x" * 201])
