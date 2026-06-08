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
    page.wait_for_timeout(2000)
    raw = page.evaluate(
        """async (url) => {
        const res = await fetch(url, { credentials: 'include' });
        return await res.text();
    }""",
        API,
    )
    j = json.loads(raw)
    data = j.get("data") or {}
    print("data type", type(data), "keys", list(data.keys())[:15] if isinstance(data, dict) else "")
    if isinstance(data, dict):
        for k, v in data.items():
            if isinstance(v, list):
                print(f" list {k} len", len(v))
                if v:
                    print("  sample keys", list(v[0].keys())[:15] if isinstance(v[0], dict) else v[0])
            elif isinstance(v, str) and len(v) > 200:
                print(f" str {k} len", len(v), "productName" in v, "gdasNm" in v)
                names = re.findall(r'"gdasNm"\s*:\s*"([^"]+)"', v)
                prices = re.findall(r'"sellPrc"\s*:\s*(\d+)', v)
                print("  names", len(names), names[:3])
                print("  prices", len(prices), prices[:3])
    browser.close()
