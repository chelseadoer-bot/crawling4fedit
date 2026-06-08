import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from playwright.sync_api import sync_playwright
from app.brands.browser_utils import launch_browser, new_stealth_context, dismiss_popups

tests = [
    (
        "balenciaga",
        "https://www.balenciaga.com/ko-kr/women",
        "https://www.balenciaga.com/on/demandware.store/Sites-BAL-R-APAC-Site/ko_KR/Search-UpdateGrid?cgid=women&start=0&sz=48",
    ),
    (
        "chanel",
        "https://www.chanel.com/kr/fashion/handbags/",
        None,
    ),
]

with sync_playwright() as p:
    browser = launch_browser(p, headless=False)
    ctx, page = new_stealth_context(browser)
    for name, landing, api in tests:
        page.goto(landing, wait_until="domcontentloaded", timeout=120000)
        page.wait_for_timeout(4000)
        dismiss_popups(page)
        print("===", name, page.title()[:60])
        print(" links", page.locator("a[href*='product']").count())
        if api:
            result = page.evaluate(
                """async (url) => {
                try {
                  const res = await fetch(url, { credentials: 'include' });
                  const text = await res.text();
                  return { ok: res.ok, status: res.status, len: text.length, sample: text.slice(0,200) };
                } catch (e) { return { ok: false, error: String(e) }; }
            }""",
                api,
            )
            print(" api", result)
    browser.close()
