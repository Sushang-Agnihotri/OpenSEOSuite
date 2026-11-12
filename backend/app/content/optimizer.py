"""Content optimisation: scores a draft against on-page best practice and (optionally) competing pages."""
from __future__ import annotations

import re

from ..audit.schema_validator import recommend_types
from ..crawler.parser import parse_html
from ..keywords.research import classify_intent
from ..text import content_tokens, is_question, readability, stem, tfidf_terms, tokens

_MD_HEADING = re.compile(r"^(#{1,6})\s+(.+?)\s*#*$")
_MD_LINK = re.compile(r"\[([^\]]+)\]\((https?://[^)\s]+|/[^)\s]*)\)")
_MD_IMAGE = re.compile(r"!\[([^\]]*)\]\(([^)\s]+)\)")


def parse_draft(content: str, url: str = "https://draft.invalid/") -> dict:
    """Accept HTML, Markdown or plain text and return {text, headings, links, images, title, meta_description}."""
    if re.search(r"<(?:p|h[1-6]|div|html|body|article|ul|a)\b", content, re.I):
        p = parse_html(content.encode("utf-8"), url, "text/html; charset=utf-8")
        return {"text": p.text, "headings": p.headings, "links": [{"url": lk["url"], "anchor": lk["anchor"]} for lk in p.links],
                "images": [{"alt": i["alt"]} for i in p.images], "title": p.title, "meta_description": p.meta_description,
                "format": "html"}
    headings, body_lines = [], []
    for line in content.splitlines():
        m = _MD_HEADING.match(line.strip())
        if m:
            headings.append({"level": len(m.group(1)), "text": m.group(2).strip()})
        else:
            body_lines.append(line)
    body = "\n".join(body_lines)
    images = [{"alt": alt or None} for alt, _ in _MD_IMAGE.findall(body)]
    body = _MD_IMAGE.sub(" ", body)
    links = [{"url": href, "anchor": anchor} for anchor, href in _MD_LINK.findall(body)]
    text = _MD_LINK.sub(r"\1", body)
    text = re.sub(r"[*_`>]+", " ", text)
    full = " ".join(h["text"] + "." for h in headings) + " " + text
    return {"text": re.sub(r"[ \t]+", " ", full).strip(), "headings": headings, "links": links, "images": images,
            "title": None, "meta_description": None, "format": "markdown" if headings else "text"}


def _contains(haystack: str, keyword: str) -> bool:
    kw = [stem(t) for t in content_tokens(keyword)] or [stem(t) for t in tokens(keyword)]
    have = {stem(t) for t in tokens(haystack or "")}
    return bool(kw) and all(t in have for t in kw)


def _check(cid: str, label: str, status: str, detail: str, fix: str = "", weight: int = 5) -> dict:
    return {"id": cid, "label": label, "status": status, "detail": detail, "recommendation": fix if status != "pass" else "", "weight": weight}


def analyse_content(content: str, keyword: str, *, title: str | None = None, meta_description: str | None = None,
                    url: str | None = None, secondary_keywords: list[str] | None = None,
                    competitors: list[dict] | None = None, site_pages: list[dict] | None = None,
                    question_keywords: list[str] | None = None) -> dict:
    """Return score, checks, readability, term suggestions, FAQ ideas, schema and internal-link suggestions.

    ``competitors``: [{url, text, headings, word_count}] of ranking pages (optional, from the SERP module).
    ``site_pages``: [{url, title, h1}] of the user's crawled pages (optional, for internal-link ideas).
    """
    draft = parse_draft(content, url or "https://draft.invalid/")
    title = title or draft["title"]
    meta_description = meta_description or draft["meta_description"]
    text, headings = draft["text"], draft["headings"]
    words = tokens(text)
    n_words = len(words)
    kw_phrase = " ".join(tokens(keyword))
    body_joined = " ".join(words)
    occurrences = body_joined.count(kw_phrase) if kw_phrase else 0
    density = round(100 * occurrences * max(len(kw_phrase.split()), 1) / n_words, 2) if n_words else 0.0
    read = readability(text)
    intent = classify_intent(keyword)
    h1s = [h["text"] for h in headings if h["level"] == 1]
    subheads = [h["text"] for h in headings if h["level"] in (2, 3)]
    comp = [c for c in (competitors or []) if c.get("text")]
    comp_counts = sorted(c.get("word_count") or len(tokens(c["text"])) for c in comp)
    target_words = comp_counts[len(comp_counts) // 2] if comp_counts else None

    checks: list[dict] = []
    # --- keyword placement
    if title is not None:
        checks.append(_check("kw_title", "Keyword in title", "pass" if _contains(title, keyword) else "fail",
                             f"Title: “{title}”", "Include the target keyword (or a close variant) near the start of the title.", 10))
        tl = len(title)
        checks.append(_check("title_length", "Title length", "pass" if 30 <= tl <= 60 else "warn", f"{tl} characters",
                             "Aim for roughly 30-60 characters so the title is not truncated.", 4))
    else:
        checks.append(_check("kw_title", "Keyword in title", "warn", "No title provided", "Add a title to evaluate it.", 10))
    if meta_description:
        dl = len(meta_description)
        checks.append(_check("kw_description", "Keyword in meta description", "pass" if _contains(meta_description, keyword) else "warn",
                             f"{dl} characters", "Mention the keyword naturally in the meta description.", 4))
        checks.append(_check("description_length", "Meta description length", "pass" if 70 <= dl <= 160 else "warn",
                             f"{dl} characters", "Aim for roughly 70-160 characters.", 3))
    else:
        checks.append(_check("kw_description", "Meta description", "warn", "No meta description provided", "Write a 70-160 character summary containing the keyword.", 4))
    checks.append(_check("h1", "Single H1 heading", "pass" if len(h1s) == 1 else "fail" if not h1s else "warn",
                         f"{len(h1s)} H1 heading(s)", "Use exactly one H1 that states the topic.", 6))
    if h1s:
        checks.append(_check("kw_h1", "Keyword in H1", "pass" if any(_contains(h, keyword) for h in h1s) else "warn",
                             f"H1: “{h1s[0]}”", "Work the keyword into the H1.", 6))
    first = " ".join(words[:100])
    checks.append(_check("kw_intro", "Keyword in the first 100 words", "pass" if _contains(first, keyword) else "warn",
                         "Checked the opening of the body text", "Mention the topic early so readers and search engines see relevance immediately.", 6))
    checks.append(_check("kw_subheadings", "Keyword in a subheading", "pass" if any(_contains(h, keyword) for h in subheads) else "warn",
                         f"{len(subheads)} H2/H3 subheading(s)", "Use the keyword or a variant in at least one H2/H3.", 4))
    if url:
        checks.append(_check("kw_url", "Keyword in URL", "pass" if _contains(url.replace("-", " ").replace("/", " "), keyword) else "warn",
                             url, "Use a short, descriptive slug containing the keyword.", 3))
    if n_words:
        status = "pass" if 0 < density <= 2.5 else "warn" if density == 0 else "fail"
        checks.append(_check("kw_density", "Keyword usage", status, f"Exact phrase used {occurrences} time(s) ({density}% of words)",
                             "Use the phrase a few times naturally." if density == 0 else "The phrase is repeated too often; rewrite some mentions with variants.", 6))
    for sk in (secondary_keywords or [])[:15]:
        checks.append(_check(f"secondary:{sk}", f"Secondary keyword: {sk}", "pass" if _contains(text, sk) else "warn",
                             "Present in the text" if _contains(text, sk) else "Not found in the text", f"Cover “{sk}” where relevant.", 2))

    # --- depth and structure
    if target_words:
        ratio = n_words / target_words if target_words else 1
        checks.append(_check("length", "Content length vs ranking pages", "pass" if ratio >= 0.8 else "warn" if ratio >= 0.5 else "fail",
                             f"{n_words} words; median of analysed competitors is {target_words}",
                             f"Competing pages are longer. Consider expanding towards ~{target_words} words if the topic warrants it.", 10))
    else:
        checks.append(_check("length", "Content length", "pass" if n_words >= 300 else "warn" if n_words >= 150 else "fail",
                             f"{n_words} words", "Pages under ~300 words rarely cover a topic fully. Add substance, not filler.", 10))
    checks.append(_check("subheadings", "Uses subheadings", "pass" if len(subheads) >= max(2, n_words // 400) else "warn",
                         f"{len(subheads)} subheading(s) for {n_words} words", "Break the text up with descriptive H2/H3 headings roughly every 300 words.", 5))
    prev, skipped = 0, False
    for h in headings:
        if prev and h["level"] > prev + 1:
            skipped = True
        prev = h["level"]
    checks.append(_check("heading_order", "Heading hierarchy", "warn" if skipped else "pass",
                         "A heading level is skipped" if skipped else "Levels are sequential", "Do not jump from H2 to H4.", 2))
    imgs = draft["images"]
    if imgs:
        missing = sum(1 for i in imgs if not i["alt"])
        checks.append(_check("img_alt", "Image alt text", "pass" if not missing else "warn", f"{missing} of {len(imgs)} image(s) lack alt text",
                             "Describe each meaningful image in its alt attribute.", 3))
    elif n_words >= 600:
        checks.append(_check("images", "Images", "warn", "No images found", "Add at least one relevant image, chart or diagram.", 2))
    internal = [lk for lk in draft["links"] if lk["url"].startswith("/") or (url and lk["url"].split("/")[2:3] == url.split("/")[2:3])]
    external = [lk for lk in draft["links"] if lk not in internal]
    checks.append(_check("internal_links", "Internal links", "pass" if internal else "warn", f"{len(internal)} internal link(s)",
                         "Link to related pages on your site with descriptive anchor text.", 4))
    checks.append(_check("external_links", "External references", "pass" if external else "warn", f"{len(external)} external link(s)",
                         "Cite a trustworthy source where it supports a claim.", 2))

    # --- readability
    if read["flesch_reading_ease"] is not None:
        ease = read["flesch_reading_ease"]
        checks.append(_check("readability", "Readability (Flesch)", "pass" if ease >= 50 else "warn" if ease >= 30 else "fail",
                             f"Reading ease {ease} ({read['label']}), grade {read['flesch_kincaid_grade']}. English-calibrated formula.",
                             "Shorten sentences and prefer common words.", 6))
        checks.append(_check("sentence_length", "Sentence length", "pass" if read["long_sentence_share"] <= 0.25 else "warn",
                             f"{round(read['long_sentence_share'] * 100)}% of sentences exceed 25 words", "Split long sentences.", 3))

    # --- intent match
    q_heads = sum(1 for h in headings if is_question(h["text"]))
    if intent["intent"] == "informational":
        ok = bool(subheads) and n_words >= 300
        checks.append(_check("intent", "Matches informational intent", "pass" if ok else "warn",
                             "Informational queries expect an explanatory, well-structured answer",
                             "Answer the question directly near the top, then elaborate with structured sections.", 6))
    elif intent["intent"] in ("transactional", "commercial"):
        cues = sum(1 for w in ("price", "pricing", "buy", "order", "compare", "review", "features", "benefits", "quote", "contact") if w in words)
        checks.append(_check("intent", f"Matches {intent['intent']} intent", "pass" if cues >= 2 else "warn",
                             f"{cues} commercial cue word(s) found (price, features, compare, order ...)",
                             "Cover what buyers look for: options, pricing, comparisons, proof and a clear call to action.", 6))

    # --- competitor-derived suggestions
    semantic, coverage = [], None
    if comp:
        my_terms = set(content_tokens(text)) | {" ".join(g) for g in zip(words, words[1:], strict=False)}
        for t in tfidf_terms([c["text"] for c in comp], limit=60):
            if t["term"] in kw_phrase:
                continue
            used = body_joined.count(t["term"])
            semantic.append({**t, "used": used, "status": "present" if used else "missing"})
        heading_docs = [" . ".join(h["text"] for h in c.get("headings", []) if h.get("level") in (2, 3)) for c in comp]
        topics = tfidf_terms(heading_docs, limit=20)
        covered = [t for t in topics if t["term"] in my_terms or t["term"] in body_joined]
        coverage = {"topics": [{**t, "covered": t in covered} for t in topics],
                    "covered_share": round(len(covered) / len(topics), 2) if topics else None}
        if topics:
            share = coverage["covered_share"]
            checks.append(_check("topic_coverage", "Topic coverage vs ranking pages", "pass" if share >= 0.6 else "warn" if share >= 0.35 else "fail",
                                 f"Covers {len(covered)} of {len(topics)} topics that competing pages use in their subheadings",
                                 "Add sections for the missing topics listed under Topic coverage.", 10))
        missing_terms = [s for s in semantic if s["status"] == "missing" and s["share"] >= 0.5]
        if semantic:
            checks.append(_check("semantic_terms", "Related terms used by ranking pages", "pass" if len(missing_terms) <= 5 else "warn",
                                 f"{len(missing_terms)} term(s) used by at least half of the competitors are absent",
                                 "Work the missing related terms in where they fit naturally.", 6))

    # --- FAQ, schema, internal links
    faq = list(dict.fromkeys(
        [q for q in (question_keywords or []) if not _contains(text, q)][:10]
        + [h["text"] for c in comp for h in c.get("headings", []) if is_question(h.get("text", "")) and 15 < len(h["text"]) < 140][:10]
    ))[:12]
    schema = recommend_types({"url": url or "", "depth": 1, "types": [], "question_headings": q_heads})
    if not any(s["type"] in ("BlogPosting", "Product", "Service") for s in schema) and intent["intent"] == "informational":
        schema.append({"type": "Article", "reason": "Informational content benefits from Article/BlogPosting markup"})
    link_ideas = []
    for p in (site_pages or [])[:3000]:
        if url and p["url"] == url:
            continue
        label = p.get("h1") or p.get("title") or ""
        key = [stem(t) for t in content_tokens(label)][:4]
        if len(key) >= 2 and all(k in {stem(w) for w in words} for k in key) and not any(lk["url"] == p["url"] for lk in draft["links"]):
            link_ideas.append({"url": p["url"], "title": p.get("title"), "reason": f"Draft mentions “{' '.join(content_tokens(label)[:4])}”"})
    link_ideas = link_ideas[:10]

    total = sum(c["weight"] for c in checks)
    earned = sum(c["weight"] * (1.0 if c["status"] == "pass" else 0.5 if c["status"] == "warn" else 0.0) for c in checks)
    return {
        "score": round(100 * earned / total) if total else 0,
        "keyword": keyword, "intent": intent, "word_count": n_words, "target_word_count": target_words,
        "keyword_occurrences": occurrences, "keyword_density": density, "readability": read,
        "headings": headings[:100], "checks": checks, "semantic_terms": semantic, "topic_coverage": coverage,
        "faq_suggestions": faq, "schema_recommendations": schema, "internal_link_suggestions": link_ideas,
        "format": draft["format"], "competitors_used": len(comp),
        "notes": ["Scores are heuristics based on on-page best practice; they do not predict rankings."]
                 + ([] if comp else ["No competitor pages supplied: term and topic suggestions need SERP data or pasted competitor URLs."]),
    }
