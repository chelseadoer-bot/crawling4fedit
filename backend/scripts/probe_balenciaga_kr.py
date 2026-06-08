import re
import sys
from pathlib import Path
from urllib.parse import unquote

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from playwright.sync_api import sync_playwright
from app.brands.browser_utils import launch_browser, new_stealth_context, dismiss_popups

URL = "https://www.balenciaga.com/ko-kr/%EC%97%AC%EC%84%B1/%EC%97%AC%EC%84%B1-%EB%A0%88%EB%94%94-%ED%88%AC-%EC%9B%A8%EC%96%B4"

with sync_playwright() as p:
    browser = launch_browser(p, headless=False)
    ctx, page = new_stealth_context(browser)
    page.goto(URL, wait_until="domcontentloaded", timeout=120000)
    dismiss_popups(page)
    page.wait_for_timeout(4000)
    html = page.content()
    cgids = re.findall(r'cgid["\']?\s*[:=]\s*["\']([^"\']+)', html)
    cgids += re.findall(r"UpdateGrid\?[^\"']*cgid=([^&\"']+)", html)
    cgids += re.findall(r'data-category-id="([^"]+)"', html)
    print("cgids", list(dict.fromkeys(cgids)))
    print("gtm", html.count("data-gtmproduct"))

    for cgid in list(dict.fromkeys(cgids))[:3] or ["women"]:
        api = (
            "https://www.balenciaga.com/on/demandware.store/Sites-BAL-R-APAC-Site/ko_KR/"
            f"Search-UpdateGrid?cgid={cgid}&start=0&sz=48"
        )
        frag = page.evaluate(
            """async (url) => {
            const res = await fetch(url, { credentials: 'include' });
            return { ok: res.ok, len: (await res.text()).length, gtm: (await res.clone().text()).includes('data-gtmproduct') };
        }""",
            api,
        )
        print("try cgid", cgid, frag)

    browser.close()
