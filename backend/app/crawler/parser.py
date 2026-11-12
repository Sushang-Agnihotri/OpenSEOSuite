"""HTML parsing: extracts every on-page SEO signal the audit needs from one document."""
from __future__ import annotations

import copy
import hashlib
import json
import re
from dataclasses import asdict, dataclass, field
from urllib.parse import urlsplit

import lxml.html
from lxml import etree

from .urls import normalize_url

_WS = re.compile(r"\s+")
_WORD = re.compile(r"[^\W_]+(?:['’-][^\W_]+)*", re.UNICODE)
_CHARSET = re.compile(rb"""<meta[^>]+charset\s*=\s*["']?\s*([\w-]+)""", re.I)
_DROP_ALWAYS = ("script", "style", "noscript", "template", "svg", "iframe", "head")
_BOILERPLATE = ("nav", "header", "footer", "aside", "form")
_INLINE = {"b", "i", "em", "strong", "span", "u", "s", "sup", "sub", "small", "mark", "code", "abbr", "font", "wbr"}
MAX_TEXT_CHARS = 60_000


@dataclass
class ParsedPage:
    title: str | None = None
    title_count: int = 0
    meta_description: str | None = None
    meta_description_count: int = 0
    meta_robots: str | None = None
    canonical: str | None = None
    canonical_count: int = 0
    canonical_raw: str | None = None
    headings: list[dict] = field(default_factory=list)  # {level, text}
    links: list[dict] = field(default_factory=list)  # {url, anchor, nofollow, kind}
    images: list[dict] = field(default_factory=list)  # {src, alt, has_dimensions, loading}
    hreflang: list[dict] = field(default_factory=list)  # {lang, href}
    og: dict[str, str] = field(default_factory=dict)
    twitter: dict[str, str] = field(default_factory=dict)
    jsonld: list = field(default_factory=list)  # parsed JSON-LD documents
    jsonld_errors: list[str] = field(default_factory=list)
    microdata_types: list[str] = field(default_factory=list)
    lang: str | None = None
    viewport: str | None = None
    charset: str | None = None
    has_doctype: bool = False
    head_count: int = 0
    body_count: int = 0
    duplicate_ids: list[str] = field(default_factory=list)
    mixed_content: list[str] = field(default_factory=list)
    insecure_forms: int = 0
    rel_next: str | None = None
    rel_prev: str | None = None
    meta_refresh: str | None = None
    base_href: str | None = None
    favicon: bool = False
    scripts: int = 0
    blocking_scripts: int = 0
    stylesheets: int = 0
    inline_script_bytes: int = 0
    inline_style_bytes: int = 0
    iframes: int = 0
    text: str = ""
    word_count: int = 0
    content_hash: str | None = None
    simhash: str | None = None
    text_ratio: float = 0.0
    parse_error: str | None = None

    def to_data(self) -> dict:
        """JSON-serialisable subset stored in ``Page.data``."""
        d = asdict(self)
        for key in ("text", "links", "title", "meta_description", "canonical", "meta_robots", "lang",
                    "word_count", "content_hash", "simhash"):
            d.pop(key, None)
        d["images"] = d["images"][:300]
        d["headings"] = d["headings"][:300]
        return d


def clean(text: str | None) -> str:
    return _WS.sub(" ", text or "").strip()


def detect_encoding(body: bytes, content_type_header: str = "") -> str:
    m = re.search(r"charset=([\w-]+)", content_type_header or "", re.I)
    if m:
        return m.group(1)
    if body[:3] == b"\xef\xbb\xbf":
        return "utf-8"
    m = _CHARSET.search(body[:4096])
    return m.group(1).decode("ascii", "replace") if m else "utf-8"


def simhash64(words: list[str]) -> str | None:
    """64-bit SimHash over word 3-shingles; similar texts yield hashes with a small Hamming distance."""
    if len(words) < 3:
        return None
    shingles = {" ".join(words[i : i + 3]) for i in range(min(len(words) - 2, 3000))}
    counts = [0] * 64
    for sh in shingles:
        h = int.from_bytes(hashlib.blake2b(sh.encode("utf-8"), digest_size=8).digest(), "big")
        for bit in range(64):
            counts[bit] += 1 if (h >> bit) & 1 else -1
    value = 0
    for bit in range(64):
        if counts[bit] > 0:
            value |= 1 << bit
    return f"{value:016x}"


def hamming(a: str, b: str) -> int:
    return bin(int(a, 16) ^ int(b, 16)).count("1")


def tokenize(text: str) -> list[str]:
    return [w.lower() for w in _WORD.findall(text)]


def _visible_text(doc, drop: tuple[str, ...]) -> str:
    tree = copy.deepcopy(doc)
    etree.strip_elements(tree, *drop, with_tail=False)
    for el in tree.iter():
        # every element except inline text formatting separates words ("<a>One</a><a>Two</a>" is two words)
        if isinstance(el.tag, str) and el.tag not in _INLINE:
            el.tail = " " + (el.tail or "")
    body = tree.find(".//body")
    return clean((body if body is not None else tree).text_content())


def _flatten_jsonld(doc) -> list[dict]:
    out: list[dict] = []
    if isinstance(doc, list):
        for d in doc:
            out.extend(_flatten_jsonld(d))
    elif isinstance(doc, dict):
        if "@graph" in doc and isinstance(doc["@graph"], list):
            for d in doc["@graph"]:
                if isinstance(d, dict) and "@context" not in d and "@context" in doc:
                    d = {"@context": doc["@context"], **d}  # children inherit the wrapper's context
                out.extend(_flatten_jsonld(d))
        else:
            out.append(doc)
    return out


def parse_html(body: bytes, url: str, content_type_header: str = "") -> ParsedPage:
    page = ParsedPage()
    encoding = detect_encoding(body, content_type_header)
    head_bytes = body[:2048].lstrip(b"\xef\xbb\xbf \t\r\n").lower()
    page.has_doctype = head_bytes.startswith(b"<!doctype html")
    lowered = body.lower()
    page.head_count = len(re.findall(rb"<head[\s>]", lowered))
    page.body_count = len(re.findall(rb"<body[\s>]", lowered))
    try:
        try:
            parser = lxml.html.HTMLParser(encoding=encoding)
        except LookupError:
            parser = lxml.html.HTMLParser(encoding="utf-8")
        doc = lxml.html.document_fromstring(body, parser=parser)
    except (etree.ParserError, etree.XMLSyntaxError, ValueError) as exc:
        page.parse_error = str(exc)[:200]
        return page

    base = url
    base_el = doc.find(".//base[@href]")
    if base_el is not None:
        page.base_href = base_el.get("href")
        base = normalize_url(page.base_href, url) or url
    https_page = urlsplit(url).scheme == "https"

    html_el = doc if doc.tag == "html" else doc.find(".//html")
    if html_el is not None:
        page.lang = (html_el.get("lang") or html_el.get("{http://www.w3.org/XML/1998/namespace}lang") or "").strip() or None

    titles = doc.xpath("//head//title | //body/title")
    page.title_count = len(titles)
    if titles:
        page.title = clean(titles[0].text_content()) or None

    robots_parts: list[str] = []
    for meta in doc.iter("meta"):
        name = (meta.get("name") or "").strip().lower()
        prop = (meta.get("property") or "").strip().lower()
        content = clean(meta.get("content"))
        equiv = (meta.get("http-equiv") or "").strip().lower()
        if meta.get("charset"):
            page.charset = meta.get("charset").strip().lower()
        if name == "description":
            page.meta_description_count += 1
            if page.meta_description is None:
                page.meta_description = content or None
        elif name in ("robots", "googlebot"):
            robots_parts.append(content.lower())
        elif name == "viewport":
            page.viewport = content
        elif name.startswith("twitter:"):
            page.twitter.setdefault(name, content)
        if prop.startswith("og:"):
            page.og.setdefault(prop, content)
        elif prop.startswith("twitter:"):
            page.twitter.setdefault(prop, content)
        if equiv == "refresh":
            page.meta_refresh = content
        elif equiv == "content-type" and "charset=" in content.lower() and not page.charset:
            page.charset = content.lower().split("charset=")[-1].strip()
    if robots_parts:
        page.meta_robots = ", ".join(dict.fromkeys(robots_parts))

    for link in doc.iter("link"):
        rels = (link.get("rel") or "").lower().split()
        href = link.get("href")
        if "canonical" in rels:
            page.canonical_count += 1
            if page.canonical is None:
                page.canonical_raw = href
                page.canonical = normalize_url(href or "", base)
        if "alternate" in rels and link.get("hreflang") and href:
            page.hreflang.append({"lang": link.get("hreflang").strip(), "href": normalize_url(href, base) or href})
        if "next" in rels and href:
            page.rel_next = normalize_url(href, base)
        if "prev" in rels and href:
            page.rel_prev = normalize_url(href, base)
        if "icon" in rels:
            page.favicon = True
        if "stylesheet" in rels:
            page.stylesheets += 1
            if https_page and href and href.strip().lower().startswith("http://"):
                page.mixed_content.append(href.strip())

    for h in doc.xpath("//h1|//h2|//h3|//h4|//h5|//h6"):
        page.headings.append({"level": int(h.tag[1]), "text": clean(h.text_content())[:300]})

    for a in doc.iter("a"):
        href = a.get("href")
        if href is None:
            continue
        target = normalize_url(href, base)
        if not target:
            continue
        anchor = clean(a.text_content())
        if not anchor:
            img = a.find(".//img")
            if img is not None:
                anchor = clean(img.get("alt"))
        rel = (a.get("rel") or "").lower().split()
        page.links.append({
            "url": target, "anchor": anchor[:300],
            "nofollow": "nofollow" in rel, "sponsored": "sponsored" in rel, "ugc": "ugc" in rel,
        })

    for img in doc.iter("img"):
        src = img.get("src") or img.get("data-src") or ""
        if not src or src.startswith("data:"):
            continue
        alt = img.get("alt")
        page.images.append({
            "src": normalize_url(src, base) or src[:300],
            "alt": None if alt is None else clean(alt)[:300],
            "has_dimensions": bool(img.get("width") and img.get("height")),
            "loading": img.get("loading"),
        })
        if https_page and src.strip().lower().startswith("http://"):
            page.mixed_content.append(src.strip())

    for tag in ("script", "iframe", "video", "audio", "source", "embed", "object"):
        for el in doc.iter(tag):
            src = (el.get("src") or el.get("data") or "").strip()
            if tag == "script":
                if src:
                    page.scripts += 1
                    typ = (el.get("type") or "").lower()
                    in_head = any(anc.tag == "head" for anc in el.iterancestors())
                    if in_head and el.get("async") is None and el.get("defer") is None and typ != "module":
                        page.blocking_scripts += 1
                elif (el.get("type") or "").lower() != "application/ld+json":
                    page.inline_script_bytes += len(el.text or "")
            elif tag == "iframe":
                page.iframes += 1
            if https_page and src.lower().startswith("http://"):
                page.mixed_content.append(src)
    for st in doc.iter("style"):
        page.inline_style_bytes += len(st.text or "")
    if https_page:
        for form in doc.iter("form"):
            if (form.get("action") or "").strip().lower().startswith("http://"):
                page.insecure_forms += 1
    page.mixed_content = list(dict.fromkeys(page.mixed_content))[:50]

    for sc in doc.xpath('//script[translate(@type,"ABCDEFGHIJKLMNOPQRSTUVWXYZ","abcdefghijklmnopqrstuvwxyz")="application/ld+json"]'):
        raw = (sc.text or "").strip()
        if not raw:
            page.jsonld_errors.append("Empty JSON-LD block")
            continue
        try:
            page.jsonld.extend(_flatten_jsonld(json.loads(raw)))
        except json.JSONDecodeError as exc:
            page.jsonld_errors.append(f"Invalid JSON-LD: {exc.msg} (line {exc.lineno}, column {exc.colno})")
    page.jsonld = page.jsonld[:60]
    page.microdata_types = list(dict.fromkeys(
        el.get("itemtype").strip() for el in doc.xpath("//*[@itemscope][@itemtype]")
    ))[:40]

    ids: dict[str, int] = {}
    for el in doc.xpath("//*[@id]"):
        ids[el.get("id")] = ids.get(el.get("id"), 0) + 1
    page.duplicate_ids = [i for i, n in ids.items() if n > 1 and i][:20]

    main_text = _visible_text(doc, _DROP_ALWAYS + _BOILERPLATE)
    if len(main_text) < 200:
        main_text = _visible_text(doc, _DROP_ALWAYS)
    words = tokenize(main_text)
    page.text = main_text[:MAX_TEXT_CHARS]
    page.word_count = len(words)
    if words:
        page.content_hash = hashlib.sha1(" ".join(words).encode("utf-8")).hexdigest()
        page.simhash = simhash64(words)
    page.text_ratio = round(len(main_text) / max(len(body), 1), 4)
    return page
