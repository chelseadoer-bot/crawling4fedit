import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from playwright.sync_api import sync_playwright
from app.brands.browser_utils import dismiss_popups, launch_browser, new_stealth_context

urls = [
    "https://www.cos.com/ko-kr/women/shop-women",
    "https://www.cos.com/ko-kr/women/view-all",
    "https://www.cos.com/ko-kr/search?q=dress",
]

with sync_playwright() as p:
    browser = launch_browser(p, headless=False)
    ctx, page = new_stealth_context(browser)
    apis = []

    def on_resp(r):
        if r.status != 200:
            return
        u = r.url
        ct = r.headers.get("content-type", "")
        if "json" in ct or "proxy" in u:
            if "google" not in u:
                apis.append(u[:200])

    page.on("response", on_resp)
    for url in urls:
        apis.clear()
        page.goto(url, wait_until="domcontentloaded", timeout=120000)
        page.wait_for_timeout(4000)
        dismiss_popups(page)
        for _ in range(6):
            page.evaluate("window.scrollBy(0,900)")
            page.wait_for_timeout(800)
        print("URL", url)
        print(" title", page.title()[:50])
        print(" product links", page.locator("a[href*='/product']").count())
        print(" apis", len(apis))
        for u in apis[:8]:
            print("  ", u)
    browser.close()
