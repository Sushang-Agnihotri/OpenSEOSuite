"""PageSpeed Insights API client, Lighthouse report parsing and optional local Lighthouse runs."""
from __future__ import annotations

import asyncio
import json
import logging
import os
import shutil
from urllib.parse import urlsplit

import httpx

from ..config import get_settings
from ..security.ssrf import resolve_and_check, validate_url

PSI_ENDPOINT = "https://www.googleapis.com/pagespeedonline/v5/runPagespeed"
CATEGORIES = ("performance", "accessibility", "best-practices", "seo")
LAB_METRICS = {
    "first-contentful-paint": "FCP", "largest-contentful-paint": "LCP", "cumulative-layout-shift": "CLS",
    "total-blocking-time": "TBT", "speed-index": "Speed Index", "interactive": "TTI",
    "server-response-time": "TTFB (document)",
}
FIELD_METRICS = {
    "LARGEST_CONTENTFUL_PAINT_MS": "LCP", "INTERACTION_TO_NEXT_PAINT": "INP", "CUMULATIVE_LAYOUT_SHIFT_SCORE": "CLS",
    "FIRST_CONTENTFUL_PAINT_MS": "FCP", "EXPERIMENTAL_TIME_TO_FIRST_BYTE": "TTFB",
}
# audit id -> topic used to group recommendations in the UI
TOPICS = {
    "images": ("modern-image-formats", "uses-optimized-images", "uses-responsive-images", "offscreen-images",
               "efficient-animated-content", "unsized-images", "image-delivery-insight", "lcp-lazy-loaded", "prioritize-lcp-image"),
    "javascript": ("unused-javascript", "unminified-javascript", "bootup-time", "mainthread-work-breakdown", "legacy-javascript",
                   "duplicated-javascript", "third-party-summary", "long-tasks", "legacy-javascript-insight", "third-parties-insight"),
    "css": ("unused-css-rules", "unminified-css"),
    "render-blocking": ("render-blocking-resources", "render-blocking-insight", "font-display", "font-display-insight"),
    "caching": ("uses-long-cache-policy", "cache-insight", "uses-text-compression", "document-latency-insight"),
    "server": ("server-response-time", "redirects", "uses-rel-preconnect", "uses-http2", "modern-http-insight"),
    "layout": ("layout-shifts", "layout-shift-elements", "cls-culprits-insight", "dom-size", "dom-size-insight", "total-byte-weight"),
}
_TOPIC_OF = {aid: topic for topic, ids in TOPICS.items() for aid in ids}
IMPACT = {"LCP": "Largest Contentful Paint", "FCP": "First Contentful Paint", "TBT": "Total Blocking Time (proxy for INP)",
          "CLS": "Cumulative Layout Shift", "INP": "Interaction to Next Paint"}


def _rating(metric: str, value: float | None) -> str | None:
    limits = {"LCP": (2500, 4000), "INP": (200, 500), "CLS": (0.1, 0.25), "FCP": (1800, 3000), "TTFB": (800, 1800),
              "TBT": (200, 600), "Speed Index": (3400, 5800), "TTI": (3800, 7300), "TTFB (document)": (800, 1800)}
    if value is None or metric not in limits:
        return None
    good, poor = limits[metric]
    return "good" if value <= good else "needs improvement" if value <= poor else "poor"


def parse_lighthouse(lhr: dict, loading_experience: dict | None = None) -> dict:
    """Reduce a Lighthouse result (from PSI or the CLI) to scores, metrics and prioritised recommendations."""
    cats = lhr.get("categories", {})
    audits = lhr.get("audits", {})
    scores = {name: (round(c["score"] * 100) if c.get("score") is not None else None) for name, c in cats.items()}
    lab = {}
    for aid, label in LAB_METRICS.items():
        a = audits.get(aid)
        if a and a.get("numericValue") is not None:
            v = a["numericValue"]
            lab[label] = {"value": round(v, 3) if label == "CLS" else round(v), "unit": "" if label == "CLS" else "ms",
                          "display": a.get("displayValue"), "rating": _rating(label, v)}
    field = {}
    for key, label in FIELD_METRICS.items():
        m = (loading_experience or {}).get("metrics", {}).get(key)
        if m:
            v = m.get("percentile")
            if label == "CLS" and v is not None:
                v = v / 100
            field[label] = {"p75": v, "unit": "" if label == "CLS" else "ms", "category": (m.get("category") or "").lower().replace("_", " "),
                            "rating": _rating(label, v)}
    recs = []
    for aid, a in audits.items():
        score = a.get("score")
        if a.get("scoreDisplayMode") in ("notApplicable", "manual", "informative") and not a.get("metricSavings"):
            continue
        if score is None or score >= 0.9:
            continue
        details = a.get("details") or {}
        savings_ms = details.get("overallSavingsMs")
        savings_bytes = details.get("overallSavingsBytes")
        metric_savings = {k: v for k, v in (a.get("metricSavings") or {}).items() if v}
        if aid in LAB_METRICS or aid in ("metrics", "final-screenshot"):
            continue
        items = []
        for it in (details.get("items") or [])[:8]:
            if isinstance(it, dict):
                label = it.get("url") or (it.get("node") or {}).get("snippet") or it.get("entity") or it.get("label")
                if isinstance(label, str):
                    items.append({"item": label[:300], "wasted_bytes": it.get("wastedBytes"), "wasted_ms": it.get("wastedMs"),
                                  "total_bytes": it.get("totalBytes")})
        impact = [IMPACT.get(k, k) for k in metric_savings]
        recs.append({
            "id": aid, "title": a.get("title"), "description": (a.get("description") or "").split(" [Learn")[0],
            "topic": _TOPIC_OF.get(aid, "other"), "score": score, "display": a.get("displayValue"),
            "savings_ms": round(savings_ms) if savings_ms else None, "savings_bytes": round(savings_bytes) if savings_bytes else None,
            "metric_savings": metric_savings, "expected_impact": impact, "items": items,
        })
    recs.sort(key=lambda r: (-(r["savings_ms"] or 0) - sum(v for v in r["metric_savings"].values() if isinstance(v, int | float)),
                             r["score"] if r["score"] is not None else 1))
    category_issues = {}
    for name, c in cats.items():
        if name == "performance":
            continue
        failed = []
        for ref in c.get("auditRefs", []):
            a = audits.get(ref["id"], {})
            if a.get("score") is not None and a["score"] < 0.9 and a.get("scoreDisplayMode") == "binary":
                failed.append({"id": ref["id"], "title": a.get("title"), "description": (a.get("description") or "").split(" [Learn")[0]})
        category_issues[name] = failed
    return {
        "final_url": lhr.get("finalDisplayedUrl") or lhr.get("finalUrl") or lhr.get("requestedUrl"),
        "lighthouse_version": lhr.get("lighthouseVersion"), "fetch_time": lhr.get("fetchTime"),
        "scores": scores, "lab": lab, "field": field,
        "field_available": bool(field), "field_overall": ((loading_experience or {}).get("overall_category") or "").lower() or None,
        "recommendations": recs[:40], "category_issues": category_issues,
        "runtime_error": (lhr.get("runtimeError") or {}).get("message"),
    }


async def run_psi(url: str, strategy: str = "mobile", api_key: str = "") -> dict:
    """Call the PageSpeed Insights v5 API. Works without a key at a low anonymous quota."""
    validate_url(url, allow_private=False)  # PSI can only test public URLs
    params: list[tuple[str, str]] = [("url", url), ("strategy", strategy)]
    params += [("category", c) for c in CATEGORIES]
    if api_key:
        params.append(("key", api_key))
    async with httpx.AsyncClient(timeout=120) as client:
        r = await client.get(PSI_ENDPOINT, params=params)
    if r.status_code != 200:
        try:
            msg = r.json().get("error", {}).get("message", r.text[:300])
        except ValueError:
            msg = r.text[:300]
        hint = " Add a free API key in Settings to raise the quota." if r.status_code == 429 and not api_key else ""
        raise RuntimeError(f"PageSpeed Insights API error {r.status_code}: {msg}{hint}")
    data = r.json()
    out = parse_lighthouse(data.get("lighthouseResult", {}), data.get("loadingExperience"))
    out["origin_field"] = parse_lighthouse({}, data.get("originLoadingExperience"))["field"]
    out["source"] = "psi_api"
    out["strategy"] = strategy
    return out


log = logging.getLogger("seo.pagespeed")
_lighthouse_slot = asyncio.Semaphore(1)


def lighthouse_path() -> str | None:
    return shutil.which("lighthouse")


async def run_local_lighthouse(url: str, strategy: str = "mobile", timeout_s: int = 180) -> dict:
    """Run the Lighthouse CLI if installed (``npm i -g lighthouse``; needs Chrome). Lab data only."""
    exe = lighthouse_path()
    if not exe:
        raise RuntimeError("Lighthouse CLI not found. Install Node.js and run: npm install -g lighthouse")
    s = get_settings()
    validate_url(url, s.allow_private_networks)
    parts = urlsplit(url)
    await resolve_and_check(parts.hostname or "", parts.port or (443 if parts.scheme == "https" else 80), s.allow_private_networks)
    # Chrome refuses to start as root without --no-sandbox (containers); everywhere else keep its sandbox on.
    flags = "--headless=new" + (" --no-sandbox" if hasattr(os, "geteuid") and os.geteuid() == 0 else "")
    args = [exe, url, "--output=json", "--quiet", f"--chrome-flags={flags}",
            "--only-categories=performance,accessibility,best-practices,seo"]
    if strategy == "desktop":
        args.append("--preset=desktop")
    async with _lighthouse_slot:  # a full Chrome per run: never more than one at a time
        proc = await asyncio.create_subprocess_exec(*args, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE)
        try:
            stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=timeout_s)
        except TimeoutError:
            proc.kill()
            raise RuntimeError("Local Lighthouse run timed out") from None
    if proc.returncode != 0 or not stdout.strip():
        log.warning("lighthouse failed: %s", stderr.decode("utf-8", "replace")[-400:])
        raise RuntimeError("Lighthouse failed. See the server log for details.")
    report = json.loads(stdout)
    # Chrome follows redirects on its own: refuse results from a page that ended up somewhere non-public.
    final = report.get("finalDisplayedUrl") or report.get("finalUrl") or url
    validate_url(final, s.allow_private_networks)
    fparts = urlsplit(final)
    await resolve_and_check(fparts.hostname or "", fparts.port or (443 if fparts.scheme == "https" else 80), s.allow_private_networks)
    out = parse_lighthouse(report)
    out["source"] = "local_lighthouse"
    out["strategy"] = strategy
    return out
