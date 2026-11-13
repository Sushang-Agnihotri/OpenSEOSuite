"""Capture README screenshots from a running instance.

Usage (from the repository root, with the backend virtualenv active and Playwright installed):

    SEO_TOKEN=<bearer token> python scripts/capture_screenshots.py [--base http://localhost:8000] [--out docs/screenshots]

The token is the value returned by POST /api/auth/login. Screens are captured from whatever data the
instance holds; see docs/screenshots/README.md for how to prepare the demo data.
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

from playwright.sync_api import sync_playwright

# (file name, route, themes)
SCREENS: list[tuple[str, str, tuple[str, ...]]] = [
    ("dashboard", "/", ("light", "dark")),
    ("site-audit", "/audit", ("light", "dark")),
    ("crawler", "/crawler", ("light",)),
    ("internal-links", "/internal-links", ("light", "dark")),
    ("link-graph", "/internal-links", ("light", "dark")),
    ("sitemaps", "/sitemaps", ("light",)),
    ("schema", "/schema", ("light",)),
    ("international", "/international", ("light",)),
    ("local", "/local", ("light",)),
    ("keywords", "/keywords", ("light",)),
    ("content-optimizer", "/content", ("light",)),
    ("competitors", "/competitors", ("light",)),
    ("backlinks", "/backlinks", ("light",)),
    ("monitoring", "/monitoring", ("light",)),
    ("reports", "/reports", ("light",)),
    ("settings", "/settings", ("light",)),
]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--base", default="http://localhost:8000")
    ap.add_argument("--out", default="docs/screenshots")
    ap.add_argument("--width", type=int, default=1440)
    ap.add_argument("--height", type=int, default=900)
    ap.add_argument("--seed", default="standing desk", help="seed keyword typed into Keyword Research")
    ap.add_argument("--extra", action="append", default=[], help="name=route, e.g. issue=/audit/issues/broken_internal_link")
    ap.add_argument("--only", action="append", default=[], help="capture only these screen names")
    args = ap.parse_args()

    token = os.environ.get("SEO_TOKEN")
    if not token:
        print("Set SEO_TOKEN to a bearer token for the instance.", file=sys.stderr)
        return 2

    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    screens = list(SCREENS)
    for item in args.extra:
        name, _, route = item.partition("=")
        screens.append((name, route, ("light",)))

    with sync_playwright() as p:
        browser = p.chromium.launch()
        for theme in ("light", "dark"):
            ctx = browser.new_context(
                viewport={"width": args.width, "height": args.height},
                device_scale_factor=1.5,
                color_scheme=theme,
            )
            ctx.add_init_script(
                f"localStorage.setItem('seotk.token', {token!r}); localStorage.setItem('seotk.theme', {theme!r});"
            )
            page = ctx.new_page()
            for name, route, themes in screens:
                if theme not in themes or (args.only and name not in args.only):
                    continue
                page.goto(args.base + route, wait_until="networkidle")
                if name == "keywords":
                    # Real suggestions fetched live from the public autocomplete endpoints.
                    page.get_by_placeholder("e.g. standing desk").fill(args.seed)
                    page.get_by_role("button", name="Get suggestions").click()
                    busy = page.get_by_text("Collecting suggestions")
                    busy.wait_for(state="visible", timeout=10_000)
                    busy.wait_for(state="hidden", timeout=120_000)
                if name == "link-graph":
                    page.get_by_role("button", name="Link graph").or_(page.get_by_role("tab", name="Link graph")).first.click()
                    page.wait_for_timeout(2500)  # let the layout settle
                    page.get_by_text("Radial view by crawl depth").scroll_into_view_if_needed()
                    page.mouse.move(args.width // 2, args.height // 2)
                    page.mouse.wheel(0, 420)
                page.wait_for_timeout(900)  # let charts finish animating
                target = out / (f"{name}.png" if theme == "light" else f"{name}-dark.png")
                page.screenshot(path=str(target))
                print("saved", target)
            ctx.close()
        browser.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
