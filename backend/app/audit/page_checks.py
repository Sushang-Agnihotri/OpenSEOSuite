"""Checks that need only a single page (run while crawling)."""
from __future__ import annotations

import re
from urllib.parse import parse_qsl, urlsplit

from ..crawler.parser import ParsedPage
from .hreflang import language_of, validate_hreflang
from .schema_validator import validate_jsonld

TITLE_MAX, TITLE_MIN = 60, 15
DESC_MAX, DESC_MIN = 160, 50
THIN_WORDS = 200
SLOW_MS = 1500
LARGE_HTML = 1_000_000
_PAGINATED = re.compile(r"(?:[?&](?:page|paged|p|pg)=([2-9]|\d{2,}))|(?:/page/([2-9]|\d{2,})/?$)", re.I)

Finding = tuple[str, dict]


def robots_directives(meta_robots: str | None, x_robots: str | None) -> set[str]:
    out: set[str] = set()
    for raw in (meta_robots, x_robots):
        for part in (raw or "").lower().replace(";", ",").split(","):
            part = part.strip()
            if ":" in part and not part.startswith(("max-", "unavailable_after")):
                part = part.split(":", 1)[1].strip()  # "googlebot: noindex"
            if part:
                out.add(part)
    if "none" in out:
        out |= {"noindex", "nofollow"}
    return out


def indexability(status: int | None, is_html: bool, directives: set[str], canonical: str | None, url: str,
                 blocked: bool = False) -> tuple[bool, str | None]:
    if blocked:
        return False, "blocked by robots.txt"
    if status is None:
        return False, "fetch error"
    if 300 <= status < 400:
        return False, "redirect"
    if 400 <= status < 500:
        return False, "client error"
    if status >= 500:
        return False, "server error"
    if not is_html:
        return False, "non-HTML"
    if "noindex" in directives:
        return False, "noindex"
    if canonical and canonical != url:
        return False, "canonicalised"
    return True, None


def is_paginated(url: str) -> bool:
    return bool(_PAGINATED.search(url))


def check_url(url: str) -> list[Finding]:
    out: list[Finding] = []
    p = urlsplit(url)
    if len(url) > 115:
        out.append(("url_too_long", {"length": len(url)}))
    if any(c.isupper() for c in p.path):
        out.append(("url_uppercase", {}))
    if "_" in p.path:
        out.append(("url_underscores", {}))
    if len(parse_qsl(p.query, keep_blank_values=True)) >= 3:
        out.append(("url_many_params", {"params": len(parse_qsl(p.query, keep_blank_values=True))}))
    if "%" in p.path or not p.path.isascii():
        out.append(("url_non_ascii", {}))
    if "//" in p.path:
        out.append(("url_double_slash", {}))
    return out


def check_page(url: str, page: ParsedPage, *, status: int, headers: dict[str, str], size: int, elapsed_ms: int,
               indexable: bool, directives: set[str]) -> list[Finding]:
    """Return (rule_id, details) findings for one successfully fetched HTML page."""
    out: list[Finding] = []
    https = url.startswith("https://")

    if elapsed_ms > SLOW_MS:
        out.append(("slow_response", {"ttfb_ms": elapsed_ms}))
    if size > LARGE_HTML:
        out.append(("html_too_large", {"bytes": size}))
    if not https:
        out.append(("not_https", {}))
    if page.mixed_content:
        out.append(("mixed_content", {"resources": page.mixed_content[:20]}))
    if page.insecure_forms:
        out.append(("insecure_form", {"forms": page.insecure_forms}))
    if page.meta_refresh and "url=" in page.meta_refresh.lower():
        out.append(("meta_refresh", {"content": page.meta_refresh}))
    if "noindex" in directives:
        out.append(("noindex", {"meta_robots": page.meta_robots, "x_robots_tag": headers.get("x-robots-tag")}))

    # Canonical
    if page.canonical_count > 1:
        out.append(("canonical_multiple", {"count": page.canonical_count}))
    if page.canonical_count == 0:
        if "noindex" not in directives:
            out.append(("canonical_missing", {}))
    elif page.canonical is None:
        out.append(("canonical_invalid", {"href": page.canonical_raw}))
    elif page.canonical != url:
        out.append(("canonicalised", {"canonical": page.canonical}))
        if is_paginated(url):
            out.append(("pagination_canonical", {"canonical": page.canonical}))

    # The remaining content checks only matter for pages that can be indexed.
    if indexable:
        title = page.title or ""
        if not title:
            out.append(("title_missing", {}))
        else:
            if len(title) > TITLE_MAX:
                out.append(("title_too_long", {"length": len(title), "title": title}))
            elif len(title) < TITLE_MIN:
                out.append(("title_too_short", {"length": len(title), "title": title}))
        if page.title_count > 1:
            out.append(("title_multiple", {"count": page.title_count}))
        desc = page.meta_description or ""
        if not desc:
            out.append(("description_missing", {}))
        elif len(desc) > DESC_MAX:
            out.append(("description_too_long", {"length": len(desc)}))
        elif len(desc) < DESC_MIN:
            out.append(("description_too_short", {"length": len(desc)}))
        if page.meta_description_count > 1:
            out.append(("description_multiple", {"count": page.meta_description_count}))

        h1s = [h["text"] for h in page.headings if h["level"] == 1]
        if not h1s or not any(h1s):
            out.append(("h1_missing", {}))
        elif len(h1s) > 1:
            out.append(("h1_multiple", {"count": len(h1s), "h1": h1s[:5]}))
        prev = 0
        for h in page.headings:
            if prev and h["level"] > prev + 1:
                out.append(("heading_skipped", {"from": f"H{prev}", "to": f"H{h['level']}", "heading": h["text"][:120]}))
                break
            prev = h["level"]
        if page.word_count < THIN_WORDS:
            out.append(("thin_content", {"words": page.word_count}))

        if not page.og:
            out.append(("og_missing", {}))
        else:
            missing = [k for k in ("og:title", "og:description", "og:image", "og:url") if not page.og.get(k)]
            if missing:
                out.append(("og_incomplete", {"missing": missing}))
        if not page.twitter.get("twitter:card") and not page.og:
            out.append(("twitter_card_missing", {}))
        if not page.jsonld and not page.jsonld_errors and not page.microdata_types:
            out.append(("schema_none", {}))

    # Structured data
    for err in page.jsonld_errors:
        out.append(("schema_invalid_json", {"error": err}))
    if page.jsonld:
        result = validate_jsonld(page.jsonld)
        errors = [f for f in result["findings"] if f["level"] == "error"]
        structure = [f for f in result["findings"] if f["level"] == "structure"]
        warnings = [f for f in result["findings"] if f["level"] == "warning"]
        if errors:
            out.append(("schema_missing_required", {"problems": [f["message"] for f in errors][:15]}))
        if structure:
            out.append(("schema_structure", {"problems": [f["message"] for f in structure][:15]}))
        if warnings:
            out.append(("schema_missing_recommended", {"problems": [f["message"] for f in warnings][:15]}))

    # Images
    no_alt = [i["src"] for i in page.images if i["alt"] is None]
    if no_alt:
        out.append(("img_alt_missing", {"count": len(no_alt), "images": no_alt[:20]}))
    no_dim = [i["src"] for i in page.images if not i["has_dimensions"]]
    if no_dim:
        out.append(("img_no_dimensions", {"count": len(no_dim), "images": no_dim[:10]}))
    if page.images:
        exts = {urlsplit(i["src"]).path.rsplit(".", 1)[-1].lower() for i in page.images if "." in urlsplit(i["src"]).path}
        if exts and exts <= {"jpg", "jpeg", "png", "gif", "bmp"}:
            out.append(("img_legacy_format", {"formats": sorted(exts)}))

    # Mobile / HTML
    vp = (page.viewport or "").lower().replace(" ", "")
    if not vp:
        out.append(("viewport_missing", {}))
    elif "width=device-width" not in vp or "user-scalable=no" in vp or "maximum-scale=1" in vp.replace("1.0", "1"):
        out.append(("viewport_not_responsive", {"viewport": page.viewport}))
    if not page.has_doctype:
        out.append(("doctype_missing", {}))
    if page.head_count > 1 or page.body_count > 1:
        out.append(("html_structure", {"head_elements": page.head_count, "body_elements": page.body_count}))
    if page.duplicate_ids:
        out.append(("duplicate_ids", {"ids": page.duplicate_ids}))
    if not page.charset and "charset=" not in headers.get("content-type", "").lower():
        out.append(("charset_missing", {}))
    if page.blocking_scripts > 3:
        out.append(("render_blocking", {"scripts": page.blocking_scripts}))
    if not page.lang:
        out.append(("lang_missing", {}))

    # Links (page-local aspects)
    empty = sum(1 for link in page.links if not link["anchor"])
    if empty:
        out.append(("empty_anchor", {"count": empty}))

    # hreflang (value-level; reciprocity is checked site-wide)
    if page.hreflang:
        bad = [msg for msg in (validate_hreflang(h["lang"]) for h in page.hreflang) if msg]
        if bad:
            out.append(("hreflang_invalid", {"problems": list(dict.fromkeys(bad))[:10]}))
        by_lang: dict[str, set[str]] = {}
        for h in page.hreflang:
            by_lang.setdefault(h["lang"].lower(), set()).add(h["href"])
        conflicts = {k: sorted(v) for k, v in by_lang.items() if len(v) > 1}
        if conflicts:
            out.append(("hreflang_conflict", {"conflicts": conflicts}))
        self_entries = [h for h in page.hreflang if h["href"] == url]
        if not self_entries:
            out.append(("hreflang_no_self", {}))
        elif page.lang and language_of(self_entries[0]["lang"]) not in (None, "x", language_of(page.lang)):
            out.append(("hreflang_lang_mismatch", {"html_lang": page.lang, "hreflang": self_entries[0]["lang"]}))
        if "x-default" not in by_lang:
            out.append(("hreflang_no_x_default", {}))
    return out
