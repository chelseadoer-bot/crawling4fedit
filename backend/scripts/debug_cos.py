import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from playwright.sync_api import sync_playwright
from app.brands.browser_utils import launch_browser, new_stealth_context, dismiss_popups

API = (
    "https://www.cos.com/ko-kr/proxy/v1/dp/gbModule/categoryProductList"
    "?sectId=252012&pageSize=36&pageNum=1&sectDispGbcd=10"
    "&sectDispSiteCd=&preview=false&searchSort=disp_prty&isFilterYn=0"
)

with sync_playwright() as p:
    browser = launch_browser(p, headless=False)
    ctx, page = new_stealth_context(browser)
    page.goto("https://www.cos.com/ko-kr/women/view-all.html", wait_until="domcontentloaded", timeout=120000)
    dismiss_popups(page)
    page.wait_for_timeout(3000)
    raw = page.evaluate(
        """async (url) => {
        const res = await fetch(url, { credentials: 'include' });
        return await res.text();
    }""",
        API,
    )
    print("len", len(raw))
    print("godNo", len(re.findall(r'"godNo"', raw)))
    print("gdasNm", len(re.findall(r'"gdasNm"', raw)))
    j = json.loads(raw)
    d = j.get("data")
    if isinstance(d, dict):
        print("data keys", list(d.keys()))
        for k, v in d.items():
            if isinstance(v, list):
                print(k, "list", len(v))
                if v and isinstance(v[0], dict):
                    print(" sample", list(v[0].keys())[:15])
            elif isinstance(v, str):
                print(k, "str", len(v))
    browser.close()
