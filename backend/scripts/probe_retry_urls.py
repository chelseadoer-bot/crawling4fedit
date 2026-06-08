"""COS / H&M / Balenciaga URL 재탐색"""
import re
import sys
from pathlib import Path
from urllib.parse import unquote

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from playwright.sync_api import sync_playwright
from app.brands.browser_utils import dismiss_popups, launch_browser, new_stealth_context

URLS = {
    "cos": "https://www.cos.com/ko-kr/women/view-all.html",
    "hm": "https://www2.hm.com/ko_kr/ladies/shop-by-product/view-all.html",
    "balenciaga": "https://www.balenciaga.com/ko-kr/%EC%97%AC%EC%84%B1/%EC%97%AC%EC%84%B1-%EB%A0%88%EB%94%94-%ED%88%AC-%EC%9B%A8%EC%96%B4",
}

with sync_playwright() as p:
    browser = launch_browser(p, headless=False)
    ctx, page = new_stealth_context(browser)
    apis: list[str] = []

    def on_resp(r):
        if r.status != 200:
            return
        u = r.url
        if any(x in u for x in ["google", "onetrust", "abtasty", "brightcove", "cookielaw"]):
            return
        if any(x in u for x in ["search-services", "hmwebservices", "UpdateGrid", "/proxy/", "product"]):
            apis.append(u[:280])

    page.on("response", on_resp)

    for name, url in URLS.items():
        apis.clear()
        print("\n===", name, unquote(url)[:80])
        try:
            page.goto(url, wait_until="domcontentloaded", timeout=120000)
            page.wait_for_timeout(5000)
            dismiss_popups(page)
            for _ in range(6):
                page.evaluate("window.scrollBy(0, 900)")
                page.wait_for_timeout(1200)
            print(" title:", page.title()[:70])
            body = page.content()
            cgids = re.findall(r'cgid["\']?\s*[:=]\s*["\']([^"\']+)', body)
            cgids += re.findall(r"Search-UpdateGrid\?[^\"']*cgid=([^&\"']+)", body)
            print(" cgids:", list(dict.fromkeys(cgids))[:5])
            print(" gtm count:", body.count("data-gtmproduct"))
            print(" product links:", page.locator("a[href*='product']").count())
            for u in apis[:12]:
                print(" ", u)
        except Exception as e:
            print(" ERR:", e)

    browser.close()
