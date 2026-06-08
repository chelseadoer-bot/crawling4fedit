import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from playwright.sync_api import sync_playwright
from app.brands.browser_utils import dismiss_popups, launch_browser, new_stealth_context

url = "https://www2.hm.com/ko_kr/ladies/shop-by-product/view-all.html"
apis = []

with sync_playwright() as p:
    browser = launch_browser(p, headless=False)
    ctx, page = new_stealth_context(browser)

    def on_resp(r):
        u = r.url
        if r.status != 200:
            return
        if any(x in u for x in ["search-services", "hmwebservices", "productpage", "listing"]):
            apis.append((u[:300], r.headers.get("content-type", "")))

    page.on("response", on_resp)
    page.goto(url, wait_until="networkidle", timeout=180000)
    page.wait_for_timeout(5000)
    dismiss_popups(page)
    for _ in range(10):
        page.evaluate("window.scrollBy(0,900)")
        page.wait_for_timeout(1500)
    print("title:", page.title())
    print("productpage links:", page.locator("a[href*='productpage']").count())
    for u, ct in apis[:15]:
        print(ct[:30], u)
    browser.close()
