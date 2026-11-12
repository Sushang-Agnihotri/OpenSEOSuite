"""robots.txt parsing and matching following RFC 9309 (wildcards, ``$`` anchors, longest match wins)."""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from urllib.parse import urlsplit


@dataclass
class _Group:
    agents: list[str] = field(default_factory=list)
    rules: list[tuple[bool, str, re.Pattern]] = field(default_factory=list)  # (allow, pattern, regex)
    crawl_delay: float | None = None


def _compile(pattern: str) -> re.Pattern:
    anchored = pattern.endswith("$")
    if anchored:
        pattern = pattern[:-1]
    regex = "".join(".*" if ch == "*" else re.escape(ch) for ch in pattern)
    return re.compile(regex + ("$" if anchored else ""))


class RobotsRules:
    def __init__(self, text: str = "", status: int | None = 200) -> None:
        self.status = status
        self.sitemaps: list[str] = []
        self.groups: list[_Group] = []
        self.errors: list[str] = []
        self.present = bool(text.strip()) and status == 200
        # RFC 9309: 4xx => no restrictions; 5xx/unreachable => assume complete disallow.
        self.disallow_all = status is not None and status >= 500
        if self.present:
            self._parse(text)

    def _parse(self, text: str) -> None:
        group: _Group | None = None
        expecting_agents = False
        for n, raw in enumerate(text.splitlines()[:5000], 1):
            line = raw.split("#", 1)[0].strip()
            if not line:
                continue
            if ":" not in line:
                self.errors.append(f"Line {n}: not a 'field: value' pair")
                continue
            key, value = (x.strip() for x in line.split(":", 1))
            key = key.lower()
            if key == "user-agent":
                if group is None or not expecting_agents:
                    group = _Group()
                    self.groups.append(group)
                group.agents.append(value.lower())
                expecting_agents = True
                continue
            if key == "sitemap":
                if value:
                    self.sitemaps.append(value)
                continue
            expecting_agents = False
            if key in ("allow", "disallow"):
                if group is None:
                    self.errors.append(f"Line {n}: rule appears before any User-agent line")
                    continue
                if value:
                    if not value.startswith(("/", "*")):
                        self.errors.append(f"Line {n}: path '{value}' should start with '/'")
                        value = "/" + value
                    group.rules.append((key == "allow", value, _compile(value)))
            elif key == "crawl-delay":
                try:
                    if group:
                        group.crawl_delay = float(value)
                except ValueError:
                    self.errors.append(f"Line {n}: invalid crawl-delay '{value}'")
            elif key not in ("host", "clean-param", "request-rate", "visit-time", "noindex"):
                self.errors.append(f"Line {n}: unknown directive '{key}'")

    def _group_for(self, user_agent: str) -> list[_Group]:
        ua = user_agent.lower()
        best: list[_Group] = []
        best_len = -1
        for g in self.groups:
            for a in g.agents:
                if a != "*" and a in ua and len(a) > best_len:
                    best, best_len = [g], len(a)
                elif a != "*" and a in ua and len(a) == best_len:
                    best.append(g)
        if best:
            return best
        return [g for g in self.groups if "*" in g.agents]

    def allowed(self, url: str, user_agent: str = "*") -> bool:
        if self.disallow_all:
            return False
        if not self.present:
            return True
        p = urlsplit(url)
        path = (p.path or "/") + (f"?{p.query}" if p.query else "")
        if path == "/robots.txt":
            return True
        verdict, length = True, -1
        for g in self._group_for(user_agent):
            for allow, pattern, regex in g.rules:
                if regex.match(path):
                    plen = len(pattern)
                    if plen > length or (plen == length and allow):
                        verdict, length = allow, plen
        return verdict

    def crawl_delay(self, user_agent: str = "*") -> float | None:
        delays = [g.crawl_delay for g in self._group_for(user_agent) if g.crawl_delay is not None]
        return max(delays) if delays else None

    def blocks_everything(self, user_agent: str = "*") -> bool:
        return not self.allowed("https://x/", user_agent)
