"""End-to-end API tests: crawl the flawed fixture website and verify every planted problem is detected,
then exercise the remaining modules through the HTTP API."""
from __future__ import annotations

import io
import json
import time

import pytest
from openpyxl import load_workbook

from tests.conftest import wait_for_job

# rule id -> fixture paths that must be flagged
EXPECTED = {
    "title_missing": ["/missing-title"], "description_missing": ["/no-description"], "h1_missing": ["/no-h1"],
    "h1_multiple": ["/multi-h1"], "heading_skipped": ["/skipped-heading"], "thin_content": ["/thin"],
    "title_duplicate": ["/dup-a", "/dup-b"], "description_duplicate": ["/dup-a", "/dup-b"], "h1_duplicate": ["/dup-a", "/dup-b"],
    "duplicate_content": ["/dup-a", "/dup-b"], "near_duplicate_content": ["/near-a", "/near-b"],
    "broken_internal_link": ["/broken-links", "/"], "broken_external_link": ["/broken-links"], "link_to_redirect": ["/broken-links"],
    "http_4xx": ["/does-not-exist"], "http_5xx": ["/server-error"],
    "redirect_chain": ["/redirect-1"], "redirect_loop": ["/loop-a", "/loop-b"], "redirect_temporary": ["/temp-redirect", "/redirect-2"],
    "noindex": ["/noindex"], "canonicalised": ["/canonicalised"], "canonical_broken": ["/canonical-broken"],
    "pagination_canonical": ["/blog/page/2"], "blocked_by_robots": ["/blocked/secret"],
    "img_alt_missing": ["/images"], "img_no_dimensions": ["/images"], "broken_image": ["/images"], "img_large": ["/images"],
    "schema_invalid_json": ["/invalid-schema"], "schema_missing_required": ["/schema-missing"], "schema_structure": ["/schema-missing"],
    "hreflang_invalid": ["/hreflang-en"], "hreflang_no_return": ["/hreflang-en"], "hreflang_no_x_default": ["/hreflang-en"],
    "orphan_page": ["/orphan"], "deep_page": ["/deep/5", "/deep/6"], "slow_response": ["/slow"],
    "sitemap_non_indexable": ["/noindex", "/redirect-1", "/does-not-exist"],
    "url_uppercase": ["/Upper_Case_URL?a=1&b=2&c=3"], "url_underscores": ["/Upper_Case_URL?a=1&b=2&c=3"], "url_many_params": ["/Upper_Case_URL?a=1&b=2&c=3"],
    "viewport_missing": ["/no-viewport"], "doctype_missing": ["/no-viewport"], "lang_missing": ["/no-viewport"],
    "nofollow_internal": ["/nofollow-links"], "empty_anchor": ["/nofollow-links"], "not_https": ["/about"],
}
SITE_RULES = ["robots_syntax", "sitemap_invalid"]
# pages that are healthy with respect to a rule and must NOT be flagged (false-positive guard)
NOT_EXPECTED = {
    "title_missing": ["/about", "/"], "thin_content": ["/about", "/noindex"], "duplicate_content": ["/about"], "h1_missing": ["/about"],
    "schema_invalid_json": ["/good-schema", "/"], "schema_missing_required": ["/good-schema", "/"], "schema_structure": ["/"],
    "orphan_page": ["/about", "/deep/6"], "broken_internal_link": ["/about"], "canonical_broken": ["/canonicalised"],
    "img_alt_missing": ["/about"], "viewport_missing": ["/about"], "title_missing ": [],
}


def _urls(client, auth, crawl_id, rule):
    r = client.get(f"/api/crawls/{crawl_id}/issues/{rule}", headers=auth, params={"per_page": 500})
    assert r.status_code == 200, r.text
    return {i["url"] for i in r.json()["items"]}


@pytest.mark.parametrize("rule", sorted(EXPECTED))
def test_planted_problem_is_detected(client, auth, crawled, rule):
    found = _urls(client, auth, crawled["crawl_id"], rule)
    for path in EXPECTED[rule]:
        assert crawled["base"] + path in found, f"{rule} should flag {path}; flagged: {sorted(u.replace(crawled['base'], '') for u in found)}"


@pytest.mark.parametrize("rule", sorted(k for k, v in NOT_EXPECTED.items() if v))
def test_no_false_positive(client, auth, crawled, rule):
    found = _urls(client, auth, crawled["crawl_id"], rule)
    for path in NOT_EXPECTED[rule]:
        assert crawled["base"] + path not in found, f"{rule} wrongly flags {path}"


def test_crawl_summary_and_scoring(client, auth, crawled):
    c = client.get(f"/api/crawls/{crawled['crawl_id']}", headers=auth).json()
    s = c["stats"]
    assert c["status"] == "completed" and 0 < c["score"] < 100
    assert s["status_classes"]["3xx"] == 5 and s["status_classes"]["4xx"] >= 2 and s["status_classes"]["5xx"] == 1 and s["status_classes"]["blocked"] == 1
    assert s["redirects"] == {"total": 5, "chains": 3, "loops": 2}
    assert s["links"]["broken_internal"] >= 3 and s["links"]["broken_external"] == 2
    assert s["sitemap"]["url_count"] == 6 and s["site_checks"]["robots"]["present"]
    assert s["issues_by_severity"]["critical"] > 0 and s["schema"]["types"]["Organization"] >= 1
    summary = client.get(f"/api/crawls/{crawled['crawl_id']}/issues", headers=auth).json()
    ids = {g["id"] for g in summary["groups"]}
    assert set(SITE_RULES) <= ids
    sev = [g["severity"] for g in summary["groups"]]
    assert sev == sorted(sev, key=["critical", "high", "medium", "low"].index)  # ordered by priority
    assert all(g["description"] and g["fix"] for g in summary["groups"])
    assert sum(summary["by_severity"].values()) == sum(g["count"] for g in summary["groups"])


def test_issue_severity_categorisation(client):
    rules = {r["id"]: r for r in client.get("/api/rules").json()}
    assert len(rules) > 85
    assert rules["http_5xx"]["severity"] == "critical" and rules["broken_internal_link"]["severity"] == "critical"
    assert rules["title_missing"]["severity"] == "high" and rules["thin_content"]["severity"] == "medium" and rules["title_too_long"]["severity"] == "low"
    assert {r["severity"] for r in rules.values()} == {"critical", "high", "medium", "low"}


def test_pages_listing_filters_and_detail(client, auth, crawled):
    cid, base = crawled["crawl_id"], crawled["base"]
    all_pages = client.get(f"/api/crawls/{cid}/pages", headers=auth, params={"per_page": 500}).json()
    assert all_pages["total"] == len(all_pages["items"]) > 40
    by_url = {p["url"]: p for p in all_pages["items"]}
    assert by_url[base + "/"]["depth"] == 0 and by_url[base + "/deep/6"]["depth"] == 6 and by_url[base + "/orphan"]["depth"] is None
    assert by_url[base + "/about"]["inlinks"] >= 2 and by_url[base + "/"]["pagerank"] > by_url[base + "/deep/6"]["pagerank"]
    assert by_url[base + "/noindex"]["indexability_reason"] == "noindex" and not by_url[base + "/canonicalised"]["indexable"]
    assert by_url[base + "/file.pdf"]["is_html"] is False and by_url[base + "/file.pdf"]["content_type"] == "application/pdf"
    assert by_url[base + "/about"]["score"] > by_url[base + "/broken-links"]["score"]
    r3 = client.get(f"/api/crawls/{cid}/pages", headers=auth, params={"status": "3xx"}).json()
    assert r3["total"] == 5 and all(300 <= p["status_code"] < 400 for p in r3["items"])
    assert client.get(f"/api/crawls/{cid}/pages", headers=auth, params={"q": "deep", "kind": "html"}).json()["total"] == 6
    assert client.get(f"/api/crawls/{cid}/pages", headers=auth, params={"rule": "thin_content"}).json()["total"] >= 1
    paged = client.get(f"/api/crawls/{cid}/pages", headers=auth, params={"per_page": 10, "page": 2, "sort": "words", "order": "desc"}).json()
    assert len(paged["items"]) == 10
    detail = client.get(f"/api/crawls/{cid}/pages/{by_url[base + '/broken-links']['id']}", headers=auth).json()
    assert {i["id"] for i in detail["issues"]} >= {"broken_internal_link", "broken_external_link"}
    assert any(o["status"] == 404 for o in detail["outlinks"]) and any(i["url"] == base + "/" for i in detail["inlinks"])
    assert detail["data"]["headings"][0] == {"level": 1, "text": "Broken links"}
    assert client.get(f"/api/crawls/{cid}/pages/999999", headers=auth).status_code == 404


def test_links_redirects_duplicates(client, auth, crawled):
    cid, base = crawled["crawl_id"], crawled["base"]
    broken = client.get(f"/api/crawls/{cid}/links", headers=auth, params={"kind": "broken", "per_page": 200}).json()
    targets = {i["target_url"] for i in broken["items"]}
    assert base + "/does-not-exist" in targets and base + "/server-error" in targets and any("ext-404" in t for t in targets)
    red = {r["url"]: r for r in client.get(f"/api/crawls/{cid}/redirects", headers=auth).json()["items"]}
    assert red[base + "/redirect-1"]["hops"] == 2 and red[base + "/redirect-1"]["final_status"] == 200 and red[base + "/loop-a"]["loop"]
    dup = client.get(f"/api/crawls/{cid}/duplicates", headers=auth).json()
    assert [base + "/dup-a", base + "/dup-b"] in [g["urls"] for g in dup["duplicate_content"]]
    assert [base + "/near-a", base + "/near-b"] in [g["urls"] for g in dup["near_duplicate_content"]]


def test_architecture_and_graph(client, auth, crawled):
    cid, base = crawled["crawl_id"], crawled["base"]
    il = client.get(f"/api/crawls/{cid}/internal-links", headers=auth).json()
    assert il["top_pages"][0]["url"] in (base + "/", base + "/about")
    assert base + "/orphan" in {p["url"] for p in il["orphans"]} and il["anchors"] and il["inlink_distribution"]
    graph = client.get(f"/api/crawls/{cid}/graph", headers=auth).json()
    ids = {n["id"] for n in graph["nodes"]}
    assert graph["edges"] and all(e["source"] in ids and e["target"] in ids for e in graph["edges"])
    opp = client.get(f"/api/crawls/{cid}/link-opportunities", headers=auth).json()
    assert "items" in opp and "method" in opp


def test_sitemap_schema_hreflang_local(client, auth, crawled):
    cid, base = crawled["crawl_id"], crawled["base"]
    sm = client.get(f"/api/crawls/{cid}/sitemaps", headers=auth).json()
    assert sm["files"][0]["kind"] == "urlset" and any("lastmod" in e for e in sm["files"][0]["errors"])
    assert {r["url"] for r in sm["non_indexable_in_sitemap"]} >= {base + "/noindex", base + "/redirect-1", base + "/does-not-exist"}
    assert base + "/thin" in {r["url"] for r in sm["indexable_missing_from_sitemap"]}
    xml = client.get(f"/api/crawls/{cid}/sitemap.xml", headers=auth)
    assert xml.status_code == 200 and f"<loc>{base}/about</loc>" in xml.text and "/noindex" not in xml.text and "/redirect-1" not in xml.text
    sc = client.get(f"/api/crawls/{cid}/schema", headers=auth).json()
    assert sc["types"]["FAQPage"] == 1 and sc["pages_with_errors"] >= 2
    bad = next(p for p in sc["pages"] if p["url"] == base + "/schema-missing")
    assert bad["errors"] >= 2 and any("Product" in m for m in bad["problems"])
    hl = client.get(f"/api/crawls/{cid}/hreflang", headers=auth).json()
    assert hl["pages_with_hreflang"] == 1 and "en-uk" in hl["hreflang_values"] and {i["id"] for i in hl["issues"]} >= {"hreflang_invalid", "hreflang_no_return"}
    local = client.get(f"/api/crawls/{cid}/local", headers=auth).json()
    assert local["has_local_schema"] is False and "nap" in local


def test_exports(client, auth, crawled):
    cid = crawled["crawl_id"]
    csv_r = client.get(f"/api/crawls/{cid}/export", headers=auth, params={"dataset": "issues", "format": "csv"})
    assert csv_r.status_code == 200 and "attachment" in csv_r.headers["content-disposition"] and "Broken internal links" in csv_r.text
    pages_csv = client.get(f"/api/crawls/{cid}/export", headers=auth, params={"dataset": "pages"}).text
    assert pages_csv.count("\n") > 40 and "status_code" in pages_csv.splitlines()[0]
    x = client.get(f"/api/crawls/{cid}/export", headers=auth, params={"dataset": "all", "format": "xlsx"})
    wb = load_workbook(io.BytesIO(x.content))
    assert wb.sheetnames == ["Summary", "Issues", "Pages", "Broken links", "Redirects"] and wb["Pages"].max_row > 40 and wb["Redirects"].max_row == 6
    j = json.loads(client.get(f"/api/crawls/{cid}/export", headers=auth, params={"dataset": "links", "format": "json"}).content)
    assert j["crawl"]["id"] == cid and len(j["links"]) > 50
    pdf = client.get(f"/api/crawls/{cid}/report.pdf", headers=auth)
    assert pdf.status_code == 200 and pdf.content[:5] == b"%PDF-" and len(pdf.content) > 5000
    assert client.get(f"/api/crawls/{cid}/export", headers=auth, params={"dataset": "nope"}).status_code == 400


def test_site_overview_and_dashboard(client, auth, crawled):
    ov = client.get(f"/api/sites/{crawled['site']['id']}/overview", headers=auth).json()
    assert ov["latest"]["id"] == crawled["crawl_id"] and len(ov["history"]) >= 1
    dash = client.get("/api/dashboard", headers=auth).json()
    assert any(s["id"] == crawled["site"]["id"] and s["last_crawl"] for s in dash["sites"])


def test_keywords_flow(client, auth, crawled):
    sid = crawled["site"]["id"]
    r = client.post(f"/api/sites/{sid}/keywords", headers=auth, json={"keywords": ["fixture website purpose", "Fixture Website Purpose", "duplicated heading", "quantum chromodynamics"]})
    assert r.status_code == 201 and r.json()["added"] == 3
    items = client.get(f"/api/sites/{sid}/keywords", headers=auth).json()["items"]
    assert all(i["search_volume"] is None and i["volume_status"] == "unavailable" for i in items)  # never fabricated
    planner = "Keyword\tAvg. monthly searches\tCompetition\nfixture website purpose\t1,300\tLow\nnew imported term\t90\tHigh\n".encode("utf-16")
    imp = client.post(f"/api/sites/{sid}/keywords/import", headers=auth, files={"file": ("planner.csv", planner, "text/csv")}).json()
    assert imp == {"added": 1, "updated": 1}
    items = {i["keyword"]: i for i in client.get(f"/api/sites/{sid}/keywords", headers=auth).json()["items"]}
    assert items["fixture website purpose"]["search_volume"] == 1300 and items["fixture website purpose"]["volume_status"] == "imported"
    mapping = {m["keyword"]: m for m in client.get(f"/api/sites/{sid}/keywords/mapping", headers=auth).json()["items"]}
    assert mapping["fixture website purpose"]["best_page"]["url"].endswith("/about")
    assert mapping["duplicated heading"]["status"] == "cannibalisation risk" and mapping["quantum chromodynamics"]["status"] == "no matching page"
    assert client.post("/api/keywords/cluster", headers=auth, json={"keywords": ["red shoes", "red shoe", "blue hat"]}).json()["clusters"][0]["size"] == 2
    assert client.get(f"/api/sites/{sid}/keywords/export", headers=auth, params={"format": "xlsx"}).content[:2] == b"PK"


def test_schema_and_content_tools(client, auth, crawled):
    v = client.post("/api/schema/validate", headers=auth, json={"jsonld": '{"@context":"https://schema.org","@type":"Event","name":"X"}'}).json()
    assert not v["valid"] and any("startDate" in f["message"] for f in v["findings"])
    assert client.post("/api/schema/validate", headers=auth, json={"jsonld": "{oops"}).json()["parse_errors"]
    by_url = client.post("/api/schema/validate", headers=auth, json={"url": crawled["base"] + "/good-schema"}).json()
    assert by_url["valid"] and by_url["all_types"] == ["FAQPage", "Question", "Answer"]
    g = client.post("/api/schema/generate", headers=auth, json={"type": "Organization", "values": {"name": "Acme </script>", "url": "https://acme.test"}}).json()
    assert g["jsonld"]["name"] == "Acme </script>" and "</script>\n</script>" not in g["html"] and g["html"].count("</script>") == 1
    c = client.post("/api/content/analyze", headers=auth, json={
        "content": "# About the fixture website\n\nThe fixture website exists for tests. " + "More helpful words here. " * 80,
        "keyword": "fixture website", "title": "About the fixture website", "site_id": crawled["site"]["id"],
        "competitor_urls": [crawled["base"] + "/about", crawled["base"] + "/thin"]}).json()
    assert 0 < c["score"] <= 100 and c["competitors_used"] == 2 and {x["id"] for x in c["checks"]} >= {"kw_title", "readability", "length"}
    f = client.post("/api/content/fetch", headers=auth, json={"url": crawled["base"] + "/about"}).json()
    assert f["title"].startswith("About the fixture") and f["word_count"] > 200
    manual = client.post("/api/serp/analyze", headers=auth, json={"keyword": "fixture", "urls": [crawled["base"] + "/about", crawled["base"] + "/thin"],
                                                                 "my_url": crawled["base"] + "/thin"}).json()
    assert manual["source"]["provider"] == "manual" and manual["results"][0]["fetched"] and manual["difficulty"]["status"] == "estimated"
    assert client.post("/api/serp/analyze", headers=auth, json={"keyword": "x"}).status_code == 400  # no provider configured


def test_backlinks_flow(client, auth, crawled):
    sid, base = crawled["site"]["id"], crawled["base"]
    port = base.rsplit(":", 1)[1]
    csv_data = ("Source URL,Target URL,Anchor,Rel\n"
                f"http://localhost:{port}/linker,{base}/about,old anchor,\n"
                f"http://localhost:{port}/ext-ok,{base}/does-not-exist,dead target,nofollow\n"
                f"http://localhost:{port}/ext-404,{base}/,gone,follow\n").encode()
    imp = client.post(f"/api/sites/{sid}/backlinks/import", headers=auth, files={"file": ("links.csv", csv_data, "text/csv")}).json()
    assert imp["added"] == 3
    assert client.post(f"/api/sites/{sid}/backlinks/import", headers=auth, files={"file": ("links.csv", csv_data, "text/csv")}).json()["added"] == 0
    job = wait_for_job(client, auth, client.post(f"/api/sites/{sid}/backlinks/verify", headers=auth).json()["job_id"])
    assert job["status"] == "completed" and job["result"]["live"] == 1 and job["result"]["lost"] == 1 and job["result"]["source_error"] == 1
    rows = {b["source_url"].rsplit("/", 1)[1]: b for b in client.get(f"/api/sites/{sid}/backlinks", headers=auth).json()["items"]}
    assert rows["linker"]["status"] == "live" and rows["linker"]["nofollow"] is True and rows["linker"]["anchor"] == "about the fixture"
    s = client.get(f"/api/sites/{sid}/backlinks/summary", headers=auth).json()
    assert s["total"] == 3 and s["referring_domains"] == 1 and "not a complete picture" in s["coverage_note"]
    assert s["broken_targets"][0]["url"] == base + "/does-not-exist" and s["opportunities"][0]["type"] == "reclaim"
    assert "linker" in client.get(f"/api/sites/{sid}/backlinks/export", headers=auth).text
    assert client.post(f"/api/sites/{sid}/backlinks/import", headers=auth, files={"file": ("x.csv", b"foo,bar\n1,2\n", "text/csv")}).status_code == 400


def test_gsc_csv_import_and_insights(client, auth, crawled):
    sid = crawled["site"]["id"]
    assert client.get(f"/api/sites/{sid}/gsc/performance", headers=auth).json() == {"has_data": False}
    from datetime import date, timedelta
    today = date(2025, 6, 30)
    lines = ["Date,Query,Page,Clicks,Impressions,Position"]
    for d in range(56):
        day = today - timedelta(days=d)
        recent = d < 28
        lines.append(f"{day},seo audit tool,https://e.com/audit,{2 if recent else 10},{100},{8.0 if recent else 3.0}")
        lines.append(f"{day},striking keyword,https://e.com/a,1,200,7.0")
        lines.append(f"{day},striking keyword,https://e.com/b,0,150,9.0")
        if recent:
            lines.append(f"{day},brand new query,https://e.com/new,1,30,5.0")
    r = client.post(f"/api/sites/{sid}/gsc/import", headers=auth, files={"file": ("gsc.csv", "\n".join(lines).encode(), "text/csv")}).json()
    assert r["rows"] == 56 * 3 + 28 and r["has_dates"]
    perf = client.get(f"/api/sites/{sid}/gsc/performance", headers=auth).json()
    assert perf["has_data"] and len(perf["series"]) == 28 and perf["totals"]["clicks"] == 28 * 4 and perf["previous"]["clicks"] == 28 * 11
    assert perf["queries"][0]["key"] in ("seo audit tool", "striking keyword")
    ins = client.get(f"/api/sites/{sid}/gsc/insights", headers=auth).json()
    assert ins["declining_queries"][0]["key"] == "seo audit tool" and ins["declining_queries"][0]["click_change"] == -224
    assert any(q["key"] == "brand new query" for q in ins["new_queries"])
    assert any(o["key"] == "striking keyword" and o["type"] == "striking distance" and "Estimate" in o["basis"] for o in ins["opportunities"])
    assert ins["cannibalisation"][0]["query"] == "striking keyword" and len(ins["cannibalisation"][0]["pages"]) == 2
    assert client.post(f"/api/sites/{sid}/gsc/import", headers=auth, files={"file": ("bad.csv", b"a,b\n1,2\n", "text/csv")}).status_code == 400
    assert client.get("/api/gsc/status", headers=auth).json()["connected"] is False
    assert client.get("/api/gsc/auth-url", headers=auth).status_code == 400  # no OAuth client configured


def test_monitors_and_alerts(client, auth, crawled):
    sid, base = crawled["site"]["id"], crawled["base"]
    up = client.post(f"/api/sites/{sid}/monitors", headers=auth, json={"kind": "uptime", "config": {"urls": [base + "/about", base + "/server-error"]}}).json()
    job = wait_for_job(client, auth, client.post(f"/api/monitors/{up['id']}/run", headers=auth).json()["job_id"])
    assert job["status"] == "completed" and job["result"]["alerts"] == 1 and job["result"]["status"] == "problem"
    meta = client.post(f"/api/sites/{sid}/monitors", headers=auth, json={"kind": "metadata", "config": {"urls": [base + "/mutable"]}}).json()
    first = wait_for_job(client, auth, client.post(f"/api/monitors/{meta['id']}/run", headers=auth).json()["job_id"])
    assert first["result"]["alerts"] == 0  # first run only records the baseline
    import httpx
    httpx.get(base + "/_bump")
    second = wait_for_job(client, auth, client.post(f"/api/monitors/{meta['id']}/run", headers=auth).json()["job_id"])
    assert second["result"]["alerts"] == 3  # title, description and H1 changed
    sm = client.post(f"/api/sites/{sid}/monitors", headers=auth, json={"kind": "sitemap"}).json()
    assert wait_for_job(client, auth, client.post(f"/api/monitors/{sm['id']}/run", headers=auth).json()["job_id"])["status"] == "completed"
    alerts = client.get("/api/alerts", headers=auth, params={"site_id": sid}).json()
    titles = [a["title"] for a in alerts["items"]]
    assert "Page is down" in titles and any("title changed" in t for t in titles) and alerts["unread"] == 4
    assert client.post("/api/alerts/read", headers=auth, json={}).json()["updated"] == 4
    mons = {m["kind"]: m for m in client.get(f"/api/sites/{sid}/monitors", headers=auth).json()}
    assert mons["uptime"]["last_status"] == "problem" and mons["sitemap"]["summary"]["urls"] == 6 and mons["metadata"]["next_run"]
    assert client.patch(f"/api/monitors/{up['id']}", headers=auth, json={"enabled": False}).json()["enabled"] is False
    assert client.delete(f"/api/monitors/{sm['id']}", headers=auth).status_code == 204
    assert client.post(f"/api/sites/{sid}/monitors", headers=auth, json={"kind": "nope"}).status_code == 422
    assert "Page is down" in client.get("/api/alerts/export", headers=auth).text


def test_scheduled_audit_monitor_and_compare(client, auth, crawled):
    sid = crawled["site"]["id"]
    mon = client.post(f"/api/sites/{sid}/monitors", headers=auth, json={"kind": "audit", "config": {"crawl": {"max_urls": 60, "delay_ms": 0, "concurrency": 8, "exclude_patterns": ["/big/", "/slow"]}}}).json()
    assert mon["interval_hours"] >= 6
    job = wait_for_job(client, auth, client.post(f"/api/monitors/{mon['id']}/run", headers=auth).json()["job_id"])
    assert job["status"] == "completed", job
    crawls = client.get(f"/api/sites/{sid}/crawls", headers=auth).json()
    assert len(crawls) >= 2 and crawls[0]["status"] == "completed"
    cmp = client.get(f"/api/crawls/{crawls[0]['id']}/compare/{crawled['crawl_id']}", headers=auth).json()
    assert cmp["score_change"] is not None and isinstance(cmp["issues"], list) and cmp["removed_count"] >= 0
    client.delete(f"/api/monitors/{mon['id']}", headers=auth)


def test_competitor_flow(client, auth, crawled):
    sid, base = crawled["site"]["id"], crawled["base"]
    port = base.rsplit(":", 1)[1]
    comp = client.post(f"/api/sites/{sid}/competitors", headers=auth, json={"name": "Rival", "url": f"http://localhost:{port}/big/0"}).json()
    r = client.post(f"/api/sites/{sid}/competitors/{comp['id']}/crawl", headers=auth, json={"max_urls": 25})
    assert r.status_code == 202
    assert wait_for_job(client, auth, r.json()["job_id"])["status"] == "completed"
    cmp = client.get(f"/api/sites/{sid}/competitors", headers=auth).json()
    rival = cmp["competitors"][0]["profile"]
    assert cmp["site"]["profile"]["indexable_pages"] > 20 and rival["indexable_pages"] >= 20 and rival["avg_word_count"] > 200
    assert rival["keyword_overlap"]["gaps"] and any(g["term"].startswith("big") for g in rival["keyword_overlap"]["gaps"])
    assert any("not verifiable" in n for n in cmp["notes"])
    assert client.get(f"/api/sites/{sid}/competitors/report.pdf", headers=auth).content[:5] == b"%PDF-"
    assert client.get(f"/api/sites/{sid}/crawls", headers=auth).json()[0]["competitor_id"] is None  # competitor crawls stay separate
    assert client.delete(f"/api/sites/{sid}/competitors/{comp['id']}", headers=auth).status_code == 204


def test_ai_layer_is_optional(client, auth, crawled):
    st = client.get("/api/ai/status", headers=auth).json()
    assert st["provider"] == "none" and st["available"] is False and "explain_issue" in st["tasks"]
    r = client.post("/api/ai/run", headers=auth, json={"task": "prioritise_fixes", "crawl_id": crawled["crawl_id"]})
    assert r.status_code == 400 and "No AI provider" in r.json()["detail"]


def test_ai_prompt_is_grounded_in_real_data(client, auth, crawled, monkeypatch):
    from app.integrations import ai
    seen = {}

    async def fake_complete(cfg, prompt, system=ai.SYSTEM_PROMPT):
        seen["prompt"], seen["system"] = prompt, system
        return "ok"

    monkeypatch.setattr(ai, "complete", fake_complete)
    r = client.post("/api/ai/run", headers=auth, json={"task": "explain_issue", "crawl_id": crawled["crawl_id"], "rule_id": "redirect_loop"})
    assert r.status_code == 200 and r.json()["output"] == "ok"
    assert "/loop-a" in seen["prompt"] and "Redirect loop" in seen["prompt"] and "Do not invent" in seen["system"]


def test_crawl_limits_cancel_and_delete(client, auth, fixture_site):
    site = client.post("/api/sites", headers=auth, json={"name": "Big", "url": fixture_site.url + "/big/0"}).json()
    r = client.post(f"/api/sites/{site['id']}/crawls", headers=auth, json={"max_urls": 30, "max_depth": 3, "delay_ms": 0, "use_sitemaps": False, "check_external_links": False})
    assert client.post(f"/api/sites/{site['id']}/crawls", headers=auth, json={}).status_code == 409  # one crawl per site at a time
    assert wait_for_job(client, auth, r.json()["job_id"])["status"] == "completed"
    c = client.get(f"/api/crawls/{r.json()['id']}", headers=auth).json()
    pages = client.get(f"/api/crawls/{c['id']}/pages", headers=auth, params={"per_page": 500}).json()["items"]
    assert c["stats"]["total_urls"] <= 30 and max(p["depth"] for p in pages if p["depth"] is not None) <= 3
    slow = client.post(f"/api/sites/{site['id']}/crawls", headers=auth, json={"max_urls": 500, "delay_ms": 400, "concurrency": 1, "use_sitemaps": False}).json()
    time.sleep(1.5)
    assert client.post(f"/api/crawls/{slow['id']}/cancel", headers=auth).json()["cancelled"] is True
    assert wait_for_job(client, auth, slow["job_id"])["status"] == "cancelled"
    assert client.get(f"/api/crawls/{slow['id']}", headers=auth).json()["status"] == "cancelled"
    assert client.delete(f"/api/crawls/{slow['id']}", headers=auth).status_code == 204
    assert client.delete(f"/api/sites/{site['id']}", headers=auth).status_code == 204
    assert client.get(f"/api/crawls/{c['id']}", headers=auth).status_code == 404  # cascade delete


def test_large_crawl_performance(client, auth, fixture_site):
    """500 pages with full analysis should finish quickly on a local machine and stay within the URL cap."""
    site = client.post("/api/sites", headers=auth, json={"name": "Perf", "url": fixture_site.url + "/big/0"}).json()
    started = time.time()
    r = client.post(f"/api/sites/{site['id']}/crawls", headers=auth, json={"max_urls": 500, "delay_ms": 0, "concurrency": 16, "use_sitemaps": False, "check_external_links": False}).json()
    assert wait_for_job(client, auth, r["job_id"], timeout=240)["status"] == "completed"
    elapsed = time.time() - started
    c = client.get(f"/api/crawls/{r['id']}", headers=auth).json()
    assert c["stats"]["total_urls"] == 500 and c["stats"]["limit_reached"] is True
    assert c["stats"]["html_pages"] == 500 and c["stats"]["duplicates"]["duplicate_content"] == 0
    rate = 500 / elapsed
    print(f"\nlarge crawl: 500 pages in {elapsed:.1f}s ({rate:.0f} pages/s)")
    assert rate > 8, f"crawl too slow: {rate:.1f} pages/s"
    client.delete(f"/api/sites/{site['id']}", headers=auth)


def test_migrations_are_current():
    """The models and the Alembic migration history must describe the same schema."""
    from alembic.autogenerate import compare_metadata
    from alembic.migration import MigrationContext

    from app.db import Base, engine
    with engine.connect() as conn:
        diff = compare_metadata(MigrationContext.configure(conn, opts={"render_as_batch": True}), Base.metadata)
    assert diff == [], diff
