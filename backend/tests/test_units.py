"""Unit tests for the pure-logic modules (no network)."""
from __future__ import annotations

import io
import json

import pytest
from openpyxl import load_workbook

from app.audit.hreflang import locale_from_path, validate_hreflang
from app.audit.page_checks import check_page, check_url, indexability, robots_directives
from app.audit.schema_validator import generate_template, validate_jsonld
from app.content.optimizer import analyse_content, parse_draft
from app.crawler.parser import hamming, parse_html, simhash64, tokenize
from app.crawler.robots import RobotsRules
from app.crawler.sitemaps import generate_sitemap, parse_sitemap
from app.crawler.urls import Scope, normalize_url, registrable_domain
from app.integrations.pagespeed import parse_lighthouse
from app.keywords.research import classify_intent, cluster_by_serp, cluster_keywords, expansion_queries, map_keywords
from app.reports.exports import audit_pdf, safe_cell, to_csv, to_xlsx
from app.serp.analyzer import analyse, estimate_difficulty
from app.text import count_syllables, readability, tfidf_terms


# ------------------------------------------------------------------ URLs
@pytest.mark.parametrize("raw,base,expected", [
    ("/a/../b?x=1#frag", "https://Example.com/dir/", "https://example.com/b?x=1"),
    ("HTTP://EXAMPLE.COM:80/", None, "http://example.com/"),
    ("https://example.com:443", None, "https://example.com/"),
    ("https://example.com:8443/x", None, "https://example.com:8443/x"),
    ("mailto:a@b.c", "https://example.com/", None),
    ("javascript:void(0)", "https://example.com/", None),
    ("#top", "https://example.com/", None),
    ("page two.html", "https://example.com/a/", "https://example.com/a/page%20two.html"),
])
def test_normalize_url(raw, base, expected):
    assert normalize_url(raw, base) == expected


def test_scope_and_registrable_domain():
    scope = Scope("https://www.example.co.uk/")
    assert scope.contains("https://example.co.uk/x")
    assert not scope.contains("https://blog.example.co.uk/")
    assert Scope("https://example.co.uk/", include_subdomains=True).contains("https://blog.example.co.uk/")
    assert not Scope("https://example.co.uk/", include_subdomains=True).contains("https://other.co.uk/")
    assert registrable_domain("a.b.example.co.uk") == "example.co.uk"


# ------------------------------------------------------------------ robots.txt
ROBOTS = """
User-agent: *
Disallow: /private/
Allow: /private/public-page
Disallow: /*.pdf$
Disallow: /search
Crawl-delay: 2

User-agent: UltimateSEOToolkit
Disallow: /only-us/

Sitemap: https://example.com/sitemap.xml
nonsense line
"""


def test_robots_rules():
    r = RobotsRules(ROBOTS)
    assert not r.allowed("https://example.com/private/x")
    assert r.allowed("https://example.com/private/public-page")  # longest match wins
    assert not r.allowed("https://example.com/files/doc.pdf")
    assert r.allowed("https://example.com/files/doc.pdf?download=1")  # $ anchors the end
    assert not r.allowed("https://example.com/search?q=x")
    assert r.sitemaps == ["https://example.com/sitemap.xml"]
    assert r.crawl_delay("*") == 2
    assert any("nonsense" in e or "field: value" in e for e in r.errors)
    # the most specific user-agent group replaces the wildcard group
    assert not r.allowed("https://example.com/only-us/x", "UltimateSEOToolkit/0.1")
    assert r.allowed("https://example.com/private/x", "UltimateSEOToolkit/0.1")


def test_robots_status_semantics():
    assert RobotsRules("", 404).allowed("https://example.com/x")
    assert not RobotsRules("", 503).allowed("https://example.com/x")
    assert RobotsRules("User-agent: *\nDisallow: /", 200).blocks_everything()
    assert RobotsRules("User-agent: *\nDisallow:", 200).allowed("https://example.com/x")


# ------------------------------------------------------------------ sitemaps
def test_parse_sitemap_urlset_and_errors():
    xml = b"""<?xml version="1.0"?><urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
      <url><loc>https://example.com/a</loc><lastmod>2024-05-01</lastmod></url>
      <url><loc>https://example.com/b</loc><lastmod>01/05/2024</lastmod></url><url></url></urlset>"""
    kind, entries, errors, _ = parse_sitemap(xml, "https://example.com/sitemap.xml")
    assert kind == "urlset" and [e["loc"] for e in entries] == ["https://example.com/a", "https://example.com/b"]
    assert any("lastmod" in e for e in errors) and any("<loc>" in e for e in errors)


def test_parse_sitemap_index_gzip_and_xxe():
    import gzip

    idx = b'<sitemapindex xmlns="http://www.sitemaps.org/schemas/sitemap/0.9"><sitemap><loc>https://example.com/s1.xml</loc></sitemap></sitemapindex>'
    kind, entries, _, _ = parse_sitemap(gzip.compress(idx), "https://example.com/sitemap.xml.gz")
    assert kind == "index" and entries[0]["loc"] == "https://example.com/s1.xml"
    xxe = b'<?xml version="1.0"?><!DOCTYPE x [<!ENTITY e SYSTEM "file:///etc/passwd">]><urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9"><url><loc>https://example.com/&e;</loc></url></urlset>'
    _, entries, _, _ = parse_sitemap(xxe, "https://example.com/sitemap.xml")
    assert all("root:" not in e["loc"] for e in entries)  # external entities are never resolved
    assert parse_sitemap(b"<html><body>not a sitemap</body></html>", "u")[0] == "unknown"


def test_generate_sitemap_escapes():
    doc = generate_sitemap([("https://example.com/?a=1&b=2", "2024-01-01")])[0]
    assert "<loc>https://example.com/?a=1&amp;b=2</loc>" in doc and "<lastmod>2024-01-01</lastmod>" in doc
    assert parse_sitemap(doc.encode(), "u")[0] == "urlset"


# ------------------------------------------------------------------ HTML parser + page checks
HTML = (b"""<!DOCTYPE html><html lang="en"><head><meta charset="utf-8"><title>  Test   page </title>
<meta name="description" content="A description."><meta name="robots" content="NOINDEX, follow">
<link rel="canonical" href="/canonical-target"><link rel="alternate" hreflang="de" href="/de/">
<meta property="og:title" content="OG"><meta name="twitter:card" content="summary">
<script type="application/ld+json">{"@context":"https://schema.org","@type":"Article","headline":"H"}</script>
<script type="application/ld+json">{broken</script>
<script src="http://insecure.example/a.js"></script></head>
<body><nav><a href="/nav">Nav</a></nav><h1>Heading one</h1><h3>Skipped</h3>
<p>Hello world, this is the main text. """ + b"It has enough words to count as real content. " * 6 + b"""</p><img src="http://insecure.example/i.png"><img src="/ok.png" alt="ok" width="1" height="1">
<a href="/internal" rel="nofollow">Internal</a><a href="https://other.example/x">External</a><a href="mailto:x@y.z">mail</a>
<form action="http://insecure.example/post"></form><div id="dup"></div><div id="dup"></div></body></html>""")


def test_parse_html_extracts_signals():
    p = parse_html(HTML, "https://example.com/page")
    assert p.title == "Test page" and p.meta_description == "A description."
    assert p.meta_robots == "noindex, follow" and p.canonical == "https://example.com/canonical-target"
    assert p.hreflang == [{"lang": "de", "href": "https://example.com/de/"}]
    assert p.og["og:title"] == "OG" and p.twitter["twitter:card"] == "summary"
    assert [h["level"] for h in p.headings] == [1, 3]
    assert {link["url"] for link in p.links} == {"https://example.com/nav", "https://example.com/internal", "https://other.example/x"}
    assert next(link for link in p.links if link["url"].endswith("/internal"))["nofollow"]
    assert p.images[0]["alt"] is None and p.images[1]["has_dimensions"]
    assert len(p.jsonld) == 1 and len(p.jsonld_errors) == 1
    assert len(p.mixed_content) == 2 and p.insecure_forms == 1
    assert p.duplicate_ids == ["dup"] and p.has_doctype and p.lang == "en"
    assert "Nav" not in p.text and "main text" in p.text  # boilerplate is excluded from the main text
    assert "Internal External" in p.text  # adjacent inline links stay separate words


def test_check_page_rules():
    p = parse_html(HTML, "https://example.com/page")
    directives = robots_directives(p.meta_robots, None)
    ok, reason = indexability(200, True, directives, p.canonical, "https://example.com/page")
    assert (ok, reason) == (False, "noindex")
    ids = {r for r, _ in check_page("https://example.com/page", p, status=200, headers={}, size=len(HTML), elapsed_ms=2000,
                                    indexable=ok, directives=directives)}
    assert {"noindex", "mixed_content", "insecure_form", "canonicalised", "schema_invalid_json", "img_alt_missing",
            "viewport_missing", "duplicate_ids", "slow_response", "hreflang_no_self", "hreflang_no_x_default"} <= ids
    assert "title_missing" not in ids  # content rules are skipped for non-indexable pages


def test_indexability_and_directives():
    assert robots_directives("none", None) >= {"noindex", "nofollow"}
    assert "noindex" in robots_directives(None, "googlebot: noindex")
    assert indexability(200, True, set(), "https://e.com/b", "https://e.com/a") == (False, "canonicalised")
    assert indexability(301, False, set(), None, "u") == (False, "redirect")
    assert indexability(200, True, set(), None, "u") == (True, None)


def test_check_url():
    ids = {r for r, _ in check_url("https://example.com/Some_Path//x?a=1&b=2&c=3")}
    assert ids == {"url_uppercase", "url_underscores", "url_many_params", "url_double_slash"}


def test_simhash_similarity():
    a = tokenize(" ".join(f"word{i}" for i in range(400)))
    b = a[:-1] + ["different"]
    c = tokenize(" ".join(f"other{i}" for i in range(400)))
    assert hamming(simhash64(a), simhash64(b)) <= 3
    assert hamming(simhash64(a), simhash64(c)) > 10


# ------------------------------------------------------------------ hreflang / schema
@pytest.mark.parametrize("value,valid", [("en", True), ("en-GB", True), ("x-default", True), ("zh-Hant-TW", True), ("es-419", True),
                                         ("en-UK", False), ("en_US", False), ("english", False), ("xx", False)])
def test_validate_hreflang(value, valid):
    assert (validate_hreflang(value) is None) == valid


def test_locale_from_path():
    assert locale_from_path("/de/produkte") == "de" and locale_from_path("/en-gb/") == "en-gb" and locale_from_path("/products/") is None


def test_schema_validation():
    good = {"@context": "https://schema.org", "@type": "Product", "name": "X", "offers": {"@type": "Offer", "price": "1", "priceCurrency": "USD"}}
    assert validate_jsonld([good])["errors"] == 0
    bad = {"@context": "https://schema.org", "@type": "Product", "offers": {"@type": "Offer", "price": "1"}}
    res = validate_jsonld([bad])
    msgs = " | ".join(f["message"] for f in res["findings"])
    assert "Product: missing required name" in msgs and "Offer: missing required priceCurrency" in msgs
    assert validate_jsonld([{"@type": "Person", "name": "N"}])["errors"] == 1  # missing @context
    assert validate_jsonld(["not an object"])["errors"] == 1
    assert validate_jsonld([{"@context": "https://schema.org", "@type": "Restaurant", "name": "R"}])["errors"] == 1  # subtype of LocalBusiness needs address


def test_schema_templates_validate():
    for t in ("Organization", "Product", "Article", "FAQPage", "LocalBusiness", "Event", "BreadcrumbList", "WebSite", "Person", "Service", "BlogPosting", "WebPage"):
        doc = generate_template(t, {"name": "Example", "headline": "Example"})
        assert doc["@context"] == "https://schema.org" and doc["@type"] == t
    with pytest.raises(KeyError):
        generate_template("Nope")


# ------------------------------------------------------------------ text / keywords / content / serp
def test_readability():
    assert count_syllables("readability") == 5 and count_syllables("the") == 1
    easy = readability("The cat sat on the mat. The dog ran to the park. We like to play.")
    hard = readability("Notwithstanding considerable methodological heterogeneity, interdisciplinary epistemological frameworks necessitate comprehensive reconceptualisation.")
    assert easy["flesch_reading_ease"] > 80 > 20 > hard["flesch_reading_ease"]


@pytest.mark.parametrize("kw,intent", [("buy running shoes online", "transactional"), ("best crm software", "commercial"),
                                       ("how to tie a tie", "informational"), ("facebook login", "navigational"),
                                       ("pizza near me", "local"), ("humic acid", "informational")])
def test_intent(kw, intent):
    assert classify_intent(kw)["intent"] == intent


def test_clustering_and_expansion():
    kws = ["seo audit tool", "seo audit tools", "free seo audit tool", "keyword research guide", "keyword research guides", "banana bread"]
    clusters = cluster_keywords(kws)
    as_sets = [set(c["keywords"]) for c in clusters]
    assert {"seo audit tool", "seo audit tools", "free seo audit tool"} in as_sets
    assert {"keyword research guide", "keyword research guides"} in as_sets
    assert len(expansion_queries("seo", "deep")) > len(expansion_queries("seo", "basic")) > 10
    serp = cluster_by_serp({"a": ["1", "2", "3", "4"], "b": ["1", "2", "3", "9"], "c": ["7", "8"]})
    assert {tuple(sorted(c["keywords"])) for c in serp} == {("a", "b"), ("c",)}


def test_keyword_mapping_and_cannibalisation():
    pages = [
        {"url": "https://e.com/seo-audit", "title": "SEO Audit Tool", "h1": "SEO audit tool", "meta_description": "", "text": "run an seo audit tool"},
        {"url": "https://e.com/seo-audit-2", "title": "Free SEO Audit Tool", "h1": "SEO audit tool", "meta_description": "", "text": "seo audit tool free"},
        {"url": "https://e.com/about", "title": "About us", "h1": "About", "meta_description": "", "text": "company history"},
    ]
    seo, missing = map_keywords(["seo audit tool", "quantum physics"], pages)
    assert seo["status"] == "cannibalisation risk" and seo["best_page"]["url"].startswith("https://e.com/seo-audit")
    assert missing["status"] == "no matching page" and missing["best_page"] is None


def test_content_optimizer():
    draft = "# Humic acid fertilizer guide\n\nHumic acid fertilizer improves soil. " + "It helps roots absorb nutrients well. " * 60 + \
            "\n\n## Benefits of humic acid fertilizer\n\nMore text. [Read more](/soil)\n\n![chart](c.png)"
    comp = [{"url": f"https://c{i}.com", "text": "humic acid fertilizer application rates dosage per acre soil organic matter " * 80,
             "headings": [{"level": 2, "text": "Application rates"}, {"level": 2, "text": "How does humic acid work?"}], "word_count": 900} for i in range(3)]
    res = analyse_content(draft, "humic acid fertilizer", title="Humic Acid Fertilizer: Complete Guide", competitors=comp)
    checks = {c["id"]: c["status"] for c in res["checks"]}
    assert checks["kw_title"] == "pass" and checks["h1"] == "pass" and checks["kw_h1"] == "pass" and checks["kw_intro"] == "pass"
    assert 0 < res["score"] <= 100 and res["target_word_count"] == 900
    assert any(t["term"] == "application rates" and t["status"] == "missing" for t in res["semantic_terms"])
    assert "How does humic acid work?" in res["faq_suggestions"]
    weak = analyse_content("Short text without the phrase.", "humic acid fertilizer")
    assert weak["score"] < res["score"]
    assert parse_draft("<h1>T</h1><p>Body <a href='https://x.com'>x</a></p>")["format"] == "html"


def test_serp_analysis_and_difficulty():
    results = [{"position": 1, "url": "https://en.wikipedia.org/wiki/SEO", "title": "SEO audit - Wikipedia", "snippet": ""},
               {"position": 2, "url": "https://small.example/", "title": "Home", "snippet": ""},
               {"position": 3, "url": "https://blog.example/seo-audit-guide", "title": "SEO audit guide", "snippet": ""}]
    pages = {r["url"]: {"status": 200, "title": r["title"], "word_count": 1500, "text": "technical seo audit checklist crawl budget " * 50,
                        "headings": [{"level": 2, "text": "Crawl budget"}, {"level": 2, "text": "What is an SEO audit?"}], "schema_types": ["Article"]} for r in results}
    pages["https://mine.example/"] = {"status": 200, "title": "Mine", "word_count": 200, "text": "hello", "headings": [], "schema_types": []}
    out = analyse("seo audit", results, pages, ["FAQ"], "https://mine.example/")
    assert out["summary"]["pages_analysed"] == 3 and out["summary"]["median_word_count"] == 1500
    assert any(t["term"] == "crawl budget" for t in out["content_gaps"]["missing_terms"])
    assert "Article" in out["content_gaps"]["missing_schema_types"] and "What is an SEO audit?" in out["questions"]
    d = estimate_difficulty("seo audit", results, pages)
    assert d["status"] == "estimated" and 0 < d["score"] <= 100 and d["inputs"]["authority_domains"] == 1
    assert estimate_difficulty("x", [], {})["status"] == "unavailable"
    assert tfidf_terms(["alpha beta", "alpha gamma", "alpha delta"])[0]["term"] == "alpha"


# ------------------------------------------------------------------ PageSpeed parsing
def test_parse_lighthouse():
    lhr = {"lighthouseVersion": "12.0", "finalUrl": "https://e.com/", "categories": {"performance": {"score": 0.42, "auditRefs": []},
           "seo": {"score": 0.9, "auditRefs": [{"id": "meta-description"}]}},
           "audits": {"largest-contentful-paint": {"numericValue": 5200, "displayValue": "5.2 s", "score": 0.1},
                      "cumulative-layout-shift": {"numericValue": 0.31, "score": 0.2},
                      "render-blocking-resources": {"score": 0.3, "title": "Eliminate render-blocking resources", "description": "Desc [Learn more](x).",
                                                    "details": {"type": "opportunity", "overallSavingsMs": 900, "items": [{"url": "https://e.com/a.css", "wastedMs": 900}]},
                                                    "metricSavings": {"LCP": 900, "FCP": 900}},
                      "uses-long-cache-policy": {"score": 0.5, "title": "Cache", "description": "d", "details": {"items": []}},
                      "meta-description": {"score": 0, "scoreDisplayMode": "binary", "title": "No meta description", "description": "d"}}}
    field = {"overall_category": "SLOW", "metrics": {"LARGEST_CONTENTFUL_PAINT_MS": {"percentile": 4100, "category": "SLOW"},
                                                     "INTERACTION_TO_NEXT_PAINT": {"percentile": 180, "category": "FAST"},
                                                     "CUMULATIVE_LAYOUT_SHIFT_SCORE": {"percentile": 12, "category": "AVERAGE"}}}
    out = parse_lighthouse(lhr, field)
    assert out["scores"] == {"performance": 42, "seo": 90}
    assert out["lab"]["LCP"]["rating"] == "poor" and out["lab"]["CLS"]["value"] == 0.31
    assert out["field"]["INP"]["rating"] == "good" and out["field"]["CLS"]["p75"] == 0.12 and out["field"]["LCP"]["rating"] == "poor"
    first = out["recommendations"][0]
    assert first["id"] == "render-blocking-resources" and first["topic"] == "render-blocking" and first["savings_ms"] == 900
    assert "Largest Contentful Paint" in first["expected_impact"] and "Learn more" not in first["description"]
    assert out["category_issues"]["seo"][0]["id"] == "meta-description"
    assert parse_lighthouse({}, None)["field_available"] is False


# ------------------------------------------------------------------ exports
def test_export_formula_injection_and_formats():
    rows = [{"url": "=HYPERLINK(\"http://evil\")", "title": "+cmd", "n": 5, "data": {"a": 1}}, {"url": "https://ok", "title": "@x", "n": -3, "data": []}]
    assert safe_cell("=1+1") == "'=1+1" and safe_cell(-3) == -3 and safe_cell("plain") == "plain"
    csv_text = to_csv(rows).decode("utf-8-sig")
    assert "'=HYPERLINK" in csv_text and "'+cmd" in csv_text and "'@x" in csv_text
    wb = load_workbook(io.BytesIO(to_xlsx({"Pages": rows, "Empty": []})))
    assert wb.sheetnames == ["Pages", "Empty"] and wb["Pages"]["A2"].value.startswith("'=") and wb["Pages"]["C3"].value == -3
    assert json.loads(wb["Pages"]["D2"].value) == {"a": 1}


def test_audit_pdf_builds():
    stats = {"issues_by_severity": {"critical": 1, "high": 2, "medium": 0, "low": 4}, "total_urls": 10, "indexable_pages": 7, "limit_reached": True}
    pdf = audit_pdf("Example <b>&", "https://example.com", {"id": 1, "finished_at": "2025-01-01", "score": 71.5, "stats": stats},
                    [{"rule_id": "http_4xx", "count": 20, "urls": [f"https://example.com/{i}?a=1&b=<x>" for i in range(15)]},
                     {"rule_id": "title_too_long", "count": 3, "urls": []}])
    assert pdf[:5] == b"%PDF-" and len(pdf) > 3000
