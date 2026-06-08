import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from playwright.sync_api import sync_playwright
from app.brands.browser_utils import launch_browser, new_stealth_context, dismiss_popups

URL = "https://www.balenciaga.com/ko-kr/%EC%97%AC%EC%84%B1/%EC%97%AC%EC%84%B1-%EB%A0%88%EB%94%94-%ED%88%AC-%EC%9B%A8%EC%96%B4"
API = (
    "https://www.balenciaga.com/on/demandware.store/Sites-BAL-R-APAC-Site/ko_KR/"
    "Search-UpdateGrid?cgid=women_rtw_all&start=0&sz=48"
)

with sync_playwright() as p:
    browser = launch_browser(p, headless=False)
    ctx, page = new_stealth_context(browser)
    page.goto(URL, wait_until="domcontentloaded", timeout=120000)
    dismiss_popups(page)
    page.wait_for_timeout(3000)
    text = page.evaluate(
        """async (url) => {
        const res = await fetch(url, { credentials: 'include' });
        return await res.text();
    }""",
        API,
    )
    print("len", len(text), "gtm", text.count("data-gtmproduct"))
    browser.close()
