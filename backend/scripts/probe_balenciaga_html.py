import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from playwright.sync_api import sync_playwright
from app.brands.browser_utils import launch_browser, new_stealth_context, dismiss_popups

api = "https://www.balenciaga.com/on/demandware.store/Sites-BAL-R-APAC-Site/ko_KR/Search-UpdateGrid?cgid=women&start=0&sz=48"

with sync_playwright() as p:
    browser = launch_browser(p, headless=False)
    ctx, page = new_stealth_context(browser)
    page.goto("https://www.balenciaga.com/ko-kr/women", wait_until="domcontentloaded", timeout=120000)
    dismiss_popups(page)
    html = page.evaluate(
        """async (url) => {
        const res = await fetch(url, { credentials: 'include' });
        return await res.text();
    }""",
        api,
    )
    out = Path(__file__).resolve().parents[2] / "data" / "debug_balenciaga.html"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(html[:100000], encoding="utf-8")
    print("len", len(html))
    print("tiles", html.count("product-tile"))
    print("links", len(re.findall(r'href=\"([^\"]+)\"', html)))
    for m in re.findall(r'data-gtm[^>]+', html)[:2]:
        print(m[:120])
    browser.close()
