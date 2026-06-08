"""H&M 페이지/API 디버그"""
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from playwright.sync_api import sync_playwright

from app.brands.browser_utils import dismiss_popups, launch_browser, new_stealth_context

URLS = [
    "https://www2.hm.com/ko_kr/index.html",
    "https://www2.hm.com/ko_kr/ladies/shop-by-product/view-all.html",
]
API_PREFIX = "https://api.hm.com/search-services/v1/ko_kr/listing/resultpage"


def main():
    captured = []
    with sync_playwright() as p:
        browser = launch_browser(p, headless=False)
        context, page = new_stealth_context(browser)

        def on_response(response):
            u = response.url
            if response.status != 200:
                return
            if "search-services" not in u and "hmwebservices" not in u:
                return
            try:
                body = response.json()
                captured.append((u, body))
            except Exception:
                pass

        page.on("response", on_response)

        for url in URLS:
            print("--- goto", url)
            page.goto(url, wait_until="networkidle", timeout=120000)
            dismiss_popups(page)
            page.wait_for_timeout(4000)
            print("  title:", page.title())
            print("  captured:", len(captured))

        # API 직접 호출 (세션 쿠키)
        api_url = (
            API_PREFIX
            + "?pageSource=PLP&page=1&sort=RELEVANCE"
            + "&pageId=/ladies/shop-by-product/view-all&page-size=36"
        )
        resp = context.request.get(
            api_url,
            headers={
                "Accept": "application/json",
                "Referer": URLS[-1],
            },
        )
        print("direct API status", resp.status)
        if resp.ok:
            data = resp.json()
            print("  keys", list(data.keys())[:10])
            hits = data.get("results") or data.get("products") or []
            print("  hits", len(hits) if isinstance(hits, list) else type(hits))

        for u, _ in captured[:3]:
            print("sample url:", u[:120])

        browser.close()


if __name__ == "__main__":
    main()
