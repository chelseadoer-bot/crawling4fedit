import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from playwright.sync_api import sync_playwright

from app.brands.browser_utils import dismiss_popups, launch_browser, new_stealth_context

url = "https://www.cos.com/ko-kr/women"
apis = []

with sync_playwright() as p:
    browser = launch_browser(p, headless=False)
    ctx, page = new_stealth_context(browser)

    def on_resp(r):
        u = r.url
        if r.status == 200 and ("json" in r.headers.get("content-type", "") or "/api/" in u):
            if any(x in u for x in ["google", "onetrust", "abtasty"]):
                return
            apis.append(u[:250])

    page.on("response", on_resp)
    page.goto(url, wait_until="domcontentloaded", timeout=120000)
    page.wait_for_timeout(5000)
    dismiss_popups(page)
    for _ in range(8):
        page.evaluate("window.scrollBy(0,900)")
        page.wait_for_timeout(1000)
    print("title:", page.title())
    print("links:", page.locator("a[href*='/product']").count())
    print("apis:")
    for u in apis[:20]:
        print(" ", u)
    browser.close()
