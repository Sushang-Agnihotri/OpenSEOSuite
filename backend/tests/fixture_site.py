"""A deliberately flawed website used to verify that the crawler and audit detect known SEO problems.

Run standalone for manual testing:  ``python -m tests.fixture_site 8765``
(the app must run with ``SEO_ALLOW_PRIVATE_NETWORKS=true`` to crawl it).
"""
from __future__ import annotations

import asyncio
import sys

from starlette.applications import Starlette
from starlette.requests import Request
from starlette.responses import HTMLResponse, PlainTextResponse, RedirectResponse, Response
from starlette.routing import Route

LOREM = (
    "Search engine optimisation rewards pages that answer a question completely and load quickly. "
    "This paragraph exists so that the fixture pages have enough words to avoid the thin content rule. "
    "It talks about crawling, indexing, rendering, canonical tags, structured data, internal links, "
    "sitemaps, redirects, page speed, accessibility, mobile friendliness and helpful content. "
)
GOOD_HEAD = (
    '<meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">'
    '<link rel="icon" href="/favicon.ico">'
)


def words(topic: str, n: int = 6) -> str:
    return "".join(f"<p>{topic} section {i}. {LOREM}</p>" for i in range(n))


def page(title: str | None, body: str, *, desc: str | None = "auto", head: str = "", canonical: str | None = "self",
         lang: str | None = "en", base_head: str = GOOD_HEAD, doctype: bool = True, path: str = "/", og: bool = True) -> str:
    parts = [base_head]
    if title is not None:
        parts.append(f"<title>{title}</title>")
    if desc == "auto":
        desc = f"{title} - a fixture page used by the automated test-suite to verify audit rules work."
    if desc:
        parts.append(f'<meta name="description" content="{desc}">')
    if canonical == "self":
        parts.append(f'<link rel="canonical" href="{path}">')
    elif canonical:
        parts.append(f'<link rel="canonical" href="{canonical}">')
    if og and title:
        parts.append(f'<meta property="og:title" content="{title}"><meta property="og:description" content="x">'
                     f'<meta property="og:image" content="/img/ok.png"><meta property="og:url" content="{path}">'
                     '<meta name="twitter:card" content="summary">')
    parts.append(head)
    lang_attr = f' lang="{lang}"' if lang else ""
    return f"{'<!DOCTYPE html>' if doctype else ''}<html{lang_attr}><head>{''.join(parts)}</head><body>{body}</body></html>"


NAV_LINKS = [
    "/about", "/missing-title", "/no-description", "/dup-a", "/dup-b", "/near-a", "/near-b", "/thin", "/multi-h1",
    "/no-h1", "/broken-links", "/redirect-1", "/loop-a", "/temp-redirect", "/noindex", "/canonicalised",
    "/canonical-broken", "/images", "/invalid-schema", "/schema-missing", "/hreflang-en", "/slow", "/js-page",
    "/blocked/secret", "/deep/1", "/Upper_Case_URL?a=1&b=2&c=3", "/no-viewport", "/blog/page/2", "/nofollow-links",
    "/good-schema", "/server-error", "/skipped-heading", "/file.pdf",
]

ORG_SCHEMA = (
    '<script type="application/ld+json">{"@context":"https://schema.org","@graph":['
    '{"@type":"Organization","name":"Fixture Co","url":"http://fixture.test/","logo":"http://fixture.test/logo.png",'
    '"sameAs":["https://example.org/fixture"],"contactPoint":{"@type":"ContactPoint","telephone":"+1-555-0100"}},'
    '{"@type":"WebSite","name":"Fixture","url":"http://fixture.test/","publisher":{"@type":"Organization","name":"Fixture Co"},'
    '"potentialAction":{"@type":"SearchAction","target":"http://fixture.test/?q={q}"}}]}</script>'
)


def html(content: str, status: int = 200, headers: dict | None = None) -> HTMLResponse:
    return HTMLResponse(content, status_code=status, headers=headers)


async def home(request: Request):
    nav = "".join(f'<li><a href="{u}">Link to {u.strip("/").split("?")[0] or "home"}</a></li>' for u in NAV_LINKS)
    body = f"<h1>Fixture home page</h1><nav><ul>{nav}</ul></nav>{words('Home')}"
    return html(page("Fixture Home - Test Website for SEO Audits", body, head=ORG_SCHEMA, path="/"))


def simple(title, h1, topic, **kw):
    async def handler(request: Request):
        body = (f"<h1>{h1}</h1>" if h1 else "") + words(topic) + '<p><a href="/">Home</a></p>'
        return html(page(title, body, path=request.url.path, **kw))
    return handler


async def dup(request: Request):
    body = "<h1>Duplicated heading</h1>" + words("Duplicate") + '<p><a href="/">Home</a></p>'
    return html(page("Exactly the same title on two pages", body, desc="The same description is used on two different pages of this site.", path=request.url.path))


async def near(request: Request):
    tail = "alpha" if request.url.path.endswith("a") else "omega"
    unique = " ".join(f"token{i} concept{i * 7} idea{i * 13}" for i in range(260))
    body = f"<h1>Near duplicate article</h1><p>{unique}</p><p>{tail}</p>"
    return html(page(f"Near duplicate page variant {tail} for tests", body, path=request.url.path))


async def thin(request: Request):
    return html(page("Thin page with very little content", "<h1>Thin</h1><p>Only a few words here.</p>", path="/thin"))


async def multi_h1(request: Request):
    return html(page("Page with multiple H1 headings in it", "<h1>First</h1><h1>Second</h1>" + words("Multi"), path="/multi-h1"))


async def skipped(request: Request):
    return html(page("Page whose heading outline skips levels", "<h1>Top</h1><h4>Jumped to h4</h4>" + words("Skip"), path="/skipped-heading"))


async def broken_links(request: Request):
    port = request.url.port
    body = ("<h1>Broken links</h1>" + words("Broken") +
            '<a href="/does-not-exist">dead internal</a> <a href="/server-error">erroring internal</a> '
            f'<a href="http://localhost:{port}/ext-404">dead external</a> '
            '<a href="http://localhost:1/unreachable">unreachable external</a> '
            f'<a href="http://localhost:{port}/ext-ok">working external</a> <a href="/redirect-1">redirecting</a>')
    return html(page("Page containing several broken links", body, path="/broken-links"))


async def noindex(request: Request):
    return html(page("Noindex page listed in the sitemap", "<h1>Noindex</h1>" + words("Noindex"),
                     head='<meta name="robots" content="noindex, follow">', path="/noindex"))


async def images(request: Request):
    body = ("<h1>Images</h1>" + words("Images") +
            '<img src="/img/ok.png" alt="fine" width="10" height="10"><img src="/img/no-alt.png" width="10" height="10">'
            '<img src="/img/missing.png" alt="broken"><img src="/img/large.jpg" alt="large">')
    return html(page("Page with image problems to detect", body, path="/images"))


async def invalid_schema(request: Request):
    head = '<script type="application/ld+json">{"@context": "https://schema.org", "@type": "Article", "headline": }</script>'
    return html(page("Page with malformed JSON-LD markup", "<h1>Invalid schema</h1>" + words("Schema"), head=head, path="/invalid-schema"))


async def schema_missing(request: Request):
    head = ('<script type="application/ld+json">{"@context":"https://schema.org","@type":"Product","description":"No name"}</script>'
            '<script type="application/ld+json">{"@type":"Event","name":"No context"}</script>')
    return html(page("Product page with incomplete schema", "<h1>Schema missing</h1>" + words("Product"), head=head, path="/schema-missing"))


async def good_schema(request: Request):
    head = ('<script type="application/ld+json">{"@context":"https://schema.org","@type":"FAQPage","mainEntity":['
            '{"@type":"Question","name":"What is this?","acceptedAnswer":{"@type":"Answer","text":"A fixture."}}]}</script>')
    return html(page("Page with valid FAQ structured data", "<h1>Good schema</h1>" + words("FAQ"), head=head, path="/good-schema"))


async def hreflang_en(request: Request):
    head = ('<link rel="alternate" hreflang="en" href="/hreflang-en"><link rel="alternate" hreflang="de" href="/hreflang-de">'
            '<link rel="alternate" hreflang="en-UK" href="/hreflang-uk">')
    return html(page("English page with hreflang annotations", "<h1>English</h1>" + words("English") + '<a href="/hreflang-de">de</a>', head=head, path="/hreflang-en"))


async def hreflang_de(request: Request):
    return html(page("Deutsche Seite ohne Rueckverweis hreflang", "<h1>Deutsch</h1>" + words("Deutsch"), lang="de", path="/hreflang-de"))


async def slow(request: Request):
    await asyncio.sleep(1.8)
    return html(page("A slow page that takes two seconds", "<h1>Slow</h1>" + words("Slow"), path="/slow"))


async def js_page(request: Request):
    script = ("<script>document.addEventListener('DOMContentLoaded',function(){var d=document.getElementById('app');"
              "var t='';for(var i=0;i<60;i++){t+='<p>Rendered by JavaScript paragraph '+i+' with several extra words inside.</p>';}"
              "d.innerHTML='<h1>Rendered heading</h1>'+t+'<a href=\"/js-only-link\">js link</a>';});</script>")
    return html(page("JavaScript rendered page for the crawler", f'<div id="app"></div>{script}', path="/js-page"))


def deep(n: int):
    async def handler(request: Request):
        nxt = f'<a href="/deep/{n + 1}">deeper</a>' if n < 6 else ""
        return html(page(f"Deep page level {n} in a long chain", f"<h1>Deep {n}</h1>" + words(f"Deep{n}") + nxt, path=f"/deep/{n}"))
    return handler


async def no_viewport(request: Request):
    return html(page("Page without viewport and without doctype", "<h1>No viewport</h1>" + words("Viewport"),
                     base_head="", doctype=False, lang=None, path="/no-viewport", og=False))


async def paginated(request: Request):
    return html(page("Blog archive page two of the listing", "<h1>Blog page 2</h1>" + words("Blog"), canonical="/about", path="/blog/page/2"))


async def nofollow_links(request: Request):
    body = "<h1>Nofollow</h1>" + words("Nofollow") + '<a href="/about" rel="nofollow">about</a><a href="/thin"></a>'
    return html(page("Page with nofollow internal links inside", body, path="/nofollow-links"))


async def robots(request: Request):
    return PlainTextResponse(f"User-agent: *\nDisallow: /blocked/\nAllow: /blocked/public\nThis line is wrong\n\nSitemap: http://127.0.0.1:{request.url.port}/sitemap.xml\n")


async def sitemap(request: Request):
    base = f"http://127.0.0.1:{request.url.port}"
    locs = ["/", "/about", "/noindex", "/orphan", "/redirect-1", "/does-not-exist"]
    items = "".join(f"<url><loc>{base}{u}</loc><lastmod>{'2024-13-45' if u == '/about' else '2025-06-01'}</lastmod></url>" for u in locs)
    return Response(f'<?xml version="1.0" encoding="UTF-8"?><urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">{items}</urlset>',
                    media_type="application/xml")


async def image(request: Request):
    name = request.path_params["name"]
    if name == "missing.png":
        return Response(status_code=404)
    size = 400_000 if name == "large.jpg" else 200
    return Response(b"\x89PNG" + b"0" * size, media_type="image/jpeg" if name.endswith("jpg") else "image/png")


def redirect(to: str, code: int):
    async def handler(request: Request):
        return RedirectResponse(to, status_code=code)
    return handler


async def not_found(request: Request, exc=None):
    return html("<html><head><title>Not found</title></head><body><h1>404</h1></body></html>", 404)


async def server_error(request: Request):
    return html("<h1>500</h1>", 500)


async def pdf(request: Request):
    return Response(b"%PDF-1.4 fixture", media_type="application/pdf")


STATE = {"version": 1}


async def mutable(request: Request):
    v = STATE["version"]
    return html(page(f"Mutable page title version {v} for monitors", f"<h1>Mutable v{v}</h1>" + words("Mutable"), path="/mutable"))


async def bump(request: Request):
    STATE["version"] += 1
    return PlainTextResponse(str(STATE["version"]))


async def linker(request: Request):
    """A page on another host (localhost) that links to the fixture site: used for backlink verification."""
    port = request.url.port
    body = (f'<h1>Linker</h1><a href="http://127.0.0.1:{port}/about" rel="nofollow">about the fixture</a>'
            f'<a href="http://127.0.0.1:{port}/">home link</a>')
    return html(page("External page linking to the fixture", body, path="/linker"))


BIG_N = 700


async def big(request: Request):
    i = int(request.path_params["i"])
    if i >= BIG_N:
        return await not_found(request)
    nxt = [j for j in (2 * i + 1, 2 * i + 2, i + 1) if j < BIG_N]
    links = "".join(f'<a href="/big/{j}">Big page {j}</a> ' for j in nxt)
    body = f"<h1>Big page {i}</h1><p>{' '.join(f'w{i}x{k}' for k in range(250))}</p>{links}"
    return html(page(f"Big generated page number {i} for load tests", body, path=f"/big/{i}"))


routes = [
    Route("/", home),
    Route("/mutable", mutable), Route("/_bump", bump), Route("/linker", linker), Route("/big/{i:int}", big),
    Route("/about", simple("About the fixture website and its purpose", "About us", "About")),
    Route("/missing-title", simple(None, "Missing title", "Untitled")),
    Route("/no-description", simple("A page without any meta description", "No description", "Description", desc=None)),
    Route("/dup-a", dup), Route("/dup-b", dup), Route("/near-a", near), Route("/near-b", near),
    Route("/thin", thin), Route("/multi-h1", multi_h1), Route("/skipped-heading", skipped),
    Route("/no-h1", simple("A page that has no H1 heading at all", None, "Headingless")),
    Route("/broken-links", broken_links),
    Route("/redirect-1", redirect("/redirect-2", 301)), Route("/redirect-2", redirect("/about", 302)),
    Route("/loop-a", redirect("/loop-b", 301)), Route("/loop-b", redirect("/loop-a", 301)),
    Route("/temp-redirect", redirect("/about", 302)),
    Route("/noindex", noindex),
    Route("/canonicalised", simple("Page canonicalised to the about page", "Canonicalised", "Canonical", canonical="/about")),
    Route("/canonical-broken", simple("Page whose canonical target is missing", "Canonical broken", "Broken canonical", canonical="/does-not-exist")),
    Route("/images", images), Route("/invalid-schema", invalid_schema), Route("/schema-missing", schema_missing),
    Route("/good-schema", good_schema), Route("/hreflang-en", hreflang_en), Route("/hreflang-de", hreflang_de),
    Route("/orphan", simple("Orphan page that only the sitemap knows", "Orphan", "Orphan")),
    Route("/slow", slow), Route("/js-page", js_page),
    Route("/js-only-link", simple("Page only reachable through JavaScript", "JS only", "Script")),
    Route("/blocked/secret", simple("Blocked page hidden by robots rules", "Secret", "Secret")),
    *[Route(f"/deep/{i}", deep(i)) for i in range(1, 7)],
    Route("/Upper_Case_URL", simple("Page with an untidy URL and parameters", "Untidy URL", "Untidy")),
    Route("/no-viewport", no_viewport), Route("/blog/page/2", paginated), Route("/nofollow-links", nofollow_links),
    Route("/robots.txt", robots), Route("/sitemap.xml", sitemap), Route("/img/{name}", image),
    Route("/server-error", server_error), Route("/file.pdf", pdf),
    Route("/ext-ok", simple("External ok page for link checks", "Ext", "Ext")),
    Route("/favicon.ico", pdf),
]
app = Starlette(routes=routes, exception_handlers={404: not_found})


class FixtureServer:
    """Runs the fixture site on a background thread (used by the tests)."""

    def __init__(self, port: int = 0) -> None:
        import socket
        import threading

        import uvicorn

        if port == 0:
            with socket.socket() as s:
                s.bind(("127.0.0.1", 0))
                port = s.getsockname()[1]
        self.port = port
        self.url = f"http://127.0.0.1:{port}"
        self._server = uvicorn.Server(uvicorn.Config(app, host="127.0.0.1", port=port, log_level="warning"))
        self._thread = threading.Thread(target=self._server.run, daemon=True)

    def start(self) -> FixtureServer:
        import time

        self._thread.start()
        for _ in range(100):
            if self._server.started:
                break
            time.sleep(0.05)
        return self

    def stop(self) -> None:
        self._server.should_exit = True
        self._thread.join(timeout=5)


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="127.0.0.1", port=int(sys.argv[1]) if len(sys.argv) > 1 else 8765)
