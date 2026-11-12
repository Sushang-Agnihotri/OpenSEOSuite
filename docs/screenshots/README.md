# Screenshots

Screenshots in this folder must come from a real running instance, never from mock data.

To regenerate them:

1. Start the bundled flawed test website: `cd backend && python -m tests.fixture_site 8765`
2. Start the app with `SEO_ALLOW_PRIVATE_NETWORKS=true` and add `http://127.0.0.1:8765/` as a website.
3. Run a crawl, then capture the Dashboard, Site Audit, Crawler, Internal Linking and Content Optimizer pages in light and dark mode.
4. Save them here as PNG and reference them from the main `README.md`.

Because the data comes from the test website, the captures are clearly demo data: the site name and URL are visible in every screenshot.
