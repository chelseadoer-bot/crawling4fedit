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
OUT = Path(__file__).resolve().parents[2] / "data" / "cos_sample.json"

with sync_playwright() as p:
    browser = launch_browser(p, headless=False)
    ctx, page = new_stealth_context(browser)
    page.goto("https://www.cos.com/ko-kr/women/view-all.html", wait_until="networkidle", timeout=180000)
    dismiss_popups(page)
    raw = page.evaluate(
        """async (url) => {
        const res = await fetch(url, { credentials: 'include' });
        return await res.text();
    }""",
        API,
    )
    OUT.write_text(raw[:500000], encoding="utf-8")
    j = json.loads(raw)
    data = j.get("data")
    print("data type", type(data))
    if isinstance(data, dict):
        print("data keys", list(data.keys()))
        for k, v in data.items():
            t = type(v).__name__
            extra = len(v) if isinstance(v, (list, str, dict)) else ""
            print(f"  {k}: {t} {extra}")
    # regex on full json string
    names = re.findall(r'"gdasNm"\s*:\s*"([^"\\]+)"', raw)
    print("gdasNm count", len(names), names[:5])
    browser.close()
