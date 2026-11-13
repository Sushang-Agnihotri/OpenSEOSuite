"""Build the README visuals from the real screenshots in docs/screenshots/.

    backend/.venv/Scripts/python scripts/make_visuals.py        (Windows)
    backend/.venv/bin/python scripts/make_visuals.py            (macOS/Linux)

Needs Playwright with Chromium (``pip install -e "backend[render]" && playwright install chromium``), Pillow, and the frontend's
``node_modules`` (the feature icons are the same Lucide icons the app uses). Outputs go to docs/assets/:

    hero.png              screenshots in browser frames on a gradient
    social-preview.png    1280x640 image for GitHub's "Social preview" setting
    tour.gif              animated walk through the main screens
    features-light.svg / features-dark.svg   grid of the 15 modules
    data-labels.svg       the measured / imported / estimated / unavailable legend
"""
from __future__ import annotations

import html
import re
import sys
import tempfile
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont
from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parent.parent
SHOTS = ROOT / "docs" / "screenshots"
OUT = ROOT / "docs" / "assets"
ICONS = ROOT / "frontend" / "node_modules" / "lucide-react" / "dist" / "esm" / "icons"


# ------------------------------------------------------------------------------------------------ helpers
def uri(p: Path) -> str:
    return p.resolve().as_uri()


def render_html(body: str, width: int, height: int, out: Path, scale: float = 1.0) -> None:
    page_html = f"""<!doctype html><meta charset="utf-8"><style>
    *{{box-sizing:border-box}} body{{margin:0;width:{width}px;height:{height}px;overflow:hidden;position:relative;
    font-family:"Segoe UI","Helvetica Neue",Arial,sans-serif;color:#fff}}
    .win{{position:absolute;border-radius:14px;overflow:hidden;background:#0d1117;
    box-shadow:0 34px 90px rgba(0,0,0,.55),0 0 0 1px rgba(255,255,255,.14)}}
    .bar{{height:34px;background:#1c2232;display:flex;align-items:center;gap:7px;padding:0 14px}}
    .bar i{{width:11px;height:11px;border-radius:50%;display:block}}
    .bar i:nth-child(1){{background:#ff5f57}} .bar i:nth-child(2){{background:#febc2e}} .bar i:nth-child(3){{background:#28c840}}
    .bar span{{margin-left:14px;font-size:12px;color:#9aa6c4;background:#11151f;border-radius:6px;padding:4px 14px}}
    .win img{{display:block;width:100%}}
    </style>{body}"""
    with tempfile.TemporaryDirectory() as tmp:
        f = Path(tmp) / "page.html"
        f.write_text(page_html, encoding="utf-8")
        with sync_playwright() as p:
            browser = p.chromium.launch()
            page = browser.new_page(viewport={"width": width, "height": height}, device_scale_factor=scale)
            page.goto(f.as_uri())
            page.wait_for_load_state("networkidle")
            page.screenshot(path=str(out))
            browser.close()


def window(img: Path, left: int, top: int, width: int, url: str) -> str:
    return (f'<div class="win" style="left:{left}px;top:{top}px;width:{width}px"><div class="bar"><i></i><i></i><i></i>'
            f'<span>{html.escape(url)}</span></div><img src="{uri(img)}"></div>')


BG = ("background:linear-gradient(135deg,#0b1020 0%,#17265a 55%,#0d4a46 100%);")
GLOWS = ('<div style="position:absolute;width:900px;height:900px;left:-250px;top:-300px;border-radius:50%;'
         'background:radial-gradient(circle,rgba(59,108,246,.35),transparent 65%)"></div>'
         '<div style="position:absolute;width:900px;height:900px;right:-300px;bottom:-420px;border-radius:50%;'
         'background:radial-gradient(circle,rgba(34,197,94,.28),transparent 65%)"></div>')


def optimise_png(path: Path, colors: int = 256) -> None:
    img = Image.open(path).convert("RGB").quantize(colors=colors, method=Image.Quantize.MEDIANCUT, dither=Image.Dither.NONE)
    img.save(path, optimize=True)


# ------------------------------------------------------------------------------------------------ hero + social
def hero() -> None:
    body = (f'<div style="position:absolute;inset:0;{BG}"></div>{GLOWS}'
            '<div style="position:absolute;left:78px;top:72px;font-size:50px;font-weight:700;letter-spacing:-.5px;line-height:1.1">'
            'Crawl. Audit. Research.<br>Monitor.</div>'
            '<div style="position:absolute;left:80px;top:196px;font-size:23px;color:#a9b9f0">One self-hosted app. No paid APIs. '
            'No invented numbers.</div>'
            + window(SHOTS / "site-audit-dark.png", 700, 60, 860, "localhost:8000/audit")
            + window(SHOTS / "dashboard.png", 70, 300, 860, "localhost:8000/"))
    out = OUT / "hero.png"
    render_html(body, 1600, 900, out)
    optimise_png(out)


def social() -> None:
    chips = "".join(
        f'<span style="display:inline-block;margin:0 10px 10px 0;padding:8px 16px;border-radius:999px;font-size:21px;'
        f'background:rgba(255,255,255,.12);border:1px solid rgba(255,255,255,.18)">{c}</span>'
        for c in ("Crawler", "95 audit rules", "Keywords", "Link graph", "Monitoring"))
    body = (f'<div style="position:absolute;inset:0;{BG}"></div>{GLOWS}'
            '<div style="position:absolute;left:70px;top:120px;font-size:92px;font-weight:800;letter-spacing:-2px">OpenSEOSuite</div>'
            '<div style="position:absolute;left:74px;top:250px;font-size:36px;color:#c4d0ff;width:600px;line-height:1.25">'
            'Self-hosted, open-source SEO platform</div>'
            f'<div style="position:absolute;left:74px;top:372px;width:600px">{chips}</div>'
            '<div style="position:absolute;left:74px;bottom:56px;font-size:23px;color:#8fa0d6">MIT licence · no paid APIs · '
            'your data stays with you</div>'
            + window(SHOTS / "dashboard.png", 720, 140, 800, "localhost:8000"))
    out = OUT / "social-preview.png"
    render_html(body, 1280, 640, out)
    optimise_png(out)
    print("social preview", round(out.stat().st_size / 1024), "KB (GitHub limit: 1 MB)")


# ------------------------------------------------------------------------------------------------ animated tour
def _font(size: int) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    for name in ("segoeuib.ttf", "seguisb.ttf", "arialbd.ttf", "DejaVuSans-Bold.ttf", "Helvetica.ttc"):
        try:
            return ImageFont.truetype(name, size)
        except OSError:
            continue
    return ImageFont.load_default()


TOUR = [
    ("dashboard.png", "Dashboard", "Score, crawl history and HTTP status at a glance"),
    ("site-audit-dark.png", "Site audit", "95 rules, prioritised, with a transparent score"),
    ("issue-detail.png", "Issue detail", "Why it matters, how to fix it, every affected URL"),
    ("internal-links-dark.png", "Internal linking", "Link distribution, click depth, orphan pages and link opportunities"),
    ("keywords.png", "Keyword research", "Live autocomplete, clusters and questions - never invented volumes"),
    ("monitoring.png", "Monitoring", "Uptime, metadata and sitemap change detection with alerts"),
]


def tour(width: int = 1000) -> None:
    height = round(width * 1350 / 2160)
    font_t, font_s = _font(26), _font(17)
    frames: list[Image.Image] = []
    durations: list[int] = []
    base: list[Image.Image] = []
    for name, title, sub in TOUR:
        img = Image.open(SHOTS / name).convert("RGB").resize((width, height), Image.Resampling.LANCZOS)
        shade = Image.new("RGBA", (width, 92), (8, 12, 28, 215))
        img = img.convert("RGBA")
        img.alpha_composite(shade, (0, height - 92))
        d = ImageDraw.Draw(img)
        d.text((26, height - 82), title, font=font_t, fill=(255, 255, 255, 255))
        d.text((26, height - 44), sub, font=font_s, fill=(176, 192, 240, 255))
        base.append(img.convert("RGB"))
    for i, cur in enumerate(base):
        nxt = base[(i + 1) % len(base)]
        frames.append(cur)
        durations.append(2600)
        for a in (0.33, 0.66):
            frames.append(Image.blend(cur, nxt, a))
            durations.append(90)
    pal = [f.quantize(colors=128, method=Image.Quantize.MEDIANCUT, dither=Image.Dither.NONE) for f in frames]
    out = OUT / "tour.gif"
    pal[0].save(out, save_all=True, append_images=pal[1:], duration=durations, loop=0, optimize=True, disposal=1)
    print("tour.gif", round(out.stat().st_size / 1024), "KB,", len(frames), "frames")


# ------------------------------------------------------------------------------------------------ SVG feature grid
def icon_svg(name: str) -> str:
    src = (ICONS / f"{name}.js").read_text(encoding="utf-8")
    parts = []
    for tag, attrs in re.findall(r'\[\s*"(\w+)"\s*,\s*\{([^}]*)\}\s*\]', src):
        kv = {k: v for k, v in re.findall(r'(\w+):\s*"([^"]*)"', attrs) if k != "key"}
        parts.append(f"<{tag} " + " ".join(f'{k}="{v}"' for k, v in kv.items()) + "/>")
    return "".join(parts)


MODULES = [
    ("file-search", "Crawler", "robots.txt, sitemaps, JS rendering", "#3b6cf6"),
    ("bug", "Site audit", "95 rules with scores and fixes", "#ef4444"),
    ("network", "Internal linking", "PageRank, depth, orphans, graph", "#8b5cf6"),
    ("key-round", "Keyword research", "Autocomplete, clusters, intent", "#f59e0b"),
    ("search", "SERP analysis", "Provider results or pasted URLs", "#06b6d4"),
    ("pen-line", "Content optimizer", "Terms, readability, FAQ ideas", "#22c55e"),
    ("swords", "Competitors", "Crawl and compare on-site metrics", "#ec4899"),
    ("link-2", "Backlinks", "Import, verify live, anchors", "#3b6cf6"),
    ("chart-line", "Search Console", "OAuth or CSV: clicks and position", "#ef4444"),
    ("gauge", "Page speed", "PageSpeed API and Lighthouse", "#8b5cf6"),
    ("braces", "Schema markup", "Validate 25 types, generate 12", "#f59e0b"),
    ("list-tree", "Sitemaps", "Validate, find gaps, generate", "#06b6d4"),
    ("languages", "International SEO", "hreflang validation", "#22c55e"),
    ("map-pin", "Local SEO", "NAP and LocalBusiness checks", "#ec4899"),
    ("activity", "Monitoring", "Uptime, change alerts, schedules", "#3b6cf6"),
]


def features(dark: bool) -> None:
    card, title, muted, line = (("#161b22", "#f0f6fc", "#9198a1", "#30363d") if dark else ("#ffffff", "#1f2328", "#59636e", "#d1d9e0"))
    w, h, gap, cols = 224, 112, 14, 5
    width = cols * w + (cols - 1) * gap + 2
    rows = (len(MODULES) + cols - 1) // cols
    height = rows * h + (rows - 1) * gap + 2
    out = [f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {width} {height}" width="{width}" height="{height}" role="img" '
           f'aria-label="The 15 modules of OpenSEOSuite" font-family="Segoe UI, -apple-system, Helvetica, Arial, sans-serif">']
    for i, (icon, name, desc, color) in enumerate(MODULES):
        x, y = 1 + (i % cols) * (w + gap), 1 + (i // cols) * (h + gap)
        out.append(f'<g transform="translate({x} {y})">'
                   f'<rect width="{w}" height="{h}" rx="12" fill="{card}" stroke="{line}"/>'
                   f'<rect x="16" y="16" width="38" height="38" rx="10" fill="{color}" fill-opacity="{0.22 if dark else 0.14}"/>'
                   f'<g transform="translate(24.5 24.5) scale(0.875)" fill="none" stroke="{color}" stroke-width="2" '
                   f'stroke-linecap="round" stroke-linejoin="round">{icon_svg(icon)}</g>'
                   f'<text x="16" y="82" font-size="15" font-weight="700" fill="{title}">{html.escape(name)}</text>'
                   f'<text x="16" y="101" font-size="11.5" fill="{muted}">{html.escape(desc)}</text></g>')
    out.append("</svg>")
    (OUT / f"features-{'dark' if dark else 'light'}.svg").write_text("".join(out), encoding="utf-8")


def data_labels() -> None:
    items = [("Measured", "#1a7f37", "from your crawl or Google"), ("Imported", "#0969da", "from files you provide"),
             ("Estimated", "#bf8700", "a labelled heuristic"), ("Unavailable", "#6e7781", "left empty, never guessed")]
    w, h = 1000, 96
    out = [f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {w} {h}" width="{w}" height="{h}" role="img" '
           f'aria-label="Every number is labelled measured, imported, estimated or unavailable" '
           f'font-family="Segoe UI, -apple-system, Helvetica, Arial, sans-serif">']
    cell = (w - 3 * 12) / 4
    for i, (label, color, note) in enumerate(items):
        x = i * (cell + 12)
        out.append(f'<g transform="translate({x} 0)"><rect width="{cell}" height="{h}" rx="12" fill="{color}" fill-opacity="0.12" '
                   f'stroke="{color}" stroke-opacity="0.55"/><circle cx="26" cy="32" r="7" fill="{color}"/>'
                   f'<text x="42" y="38" font-size="19" font-weight="700" fill="{color}">{label}</text>'
                   f'<text x="20" y="72" font-size="14" fill="{color}">{html.escape(note)}</text></g>')
    out.append("</svg>")
    (OUT / "data-labels.svg").write_text("".join(out), encoding="utf-8")


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    missing = [n for n, *_ in TOUR if not (SHOTS / n).exists()] + [n for n in ("dashboard.png", "site-audit-dark.png") if not (SHOTS / n).exists()]
    if missing:
        print("missing screenshots:", missing, "- run scripts/capture_screenshots.py first", file=sys.stderr)
        return 2
    hero()
    social()
    tour()
    features(False)
    features(True)
    data_labels()
    print("written to", OUT)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
