import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from playwright.sync_api import sync_playwright
from app.brands.browser_utils import launch_browser, new_stealth_context, dismiss_popups

BASE = "https://www.cos.com/ko-kr/women/view-all.html"
API_TMPL = (
    "https://www.cos.com/ko-kr/proxy/v1/dp/gbModule/categoryProductList"
    "?sectId={sect_id}&pageSize=36&pageNum={page}&sectDispGbcd=10"
    "&sectDispSiteCd=&preview=false&searchSort=disp_prty&isFilterYn=0"
)

with sync_playwright() as p:
    browser = launch_browser(p, headless=False)
    ctx, page = new_stealth_context(browser)
    page.goto(BASE, wait_until="domcontentloaded", timeout=120000)
    dismiss_popups(page)
    page.wait_for_timeout(3000)

    for page_num in [1, 2]:
        url = API_TMPL.format(sect_id=252012, page=page_num)
        data = page.evaluate(
            """async (url) => {
            const res = await fetch(url, { credentials: 'include', headers: { Accept: 'application/json' } });
            return { ok: res.ok, status: res.status, body: await res.text() };
        }""",
            url,
        )
        print("page", page_num, "ok", data["ok"], "status", data["status"], "len", len(data["body"]))
        if data["ok"]:
            j = json.loads(data["body"])
            print(" keys", list(j.keys())[:10])
            items = j.get("data") or j.get("productList") or j.get("list") or []
            if isinstance(j.get("data"), dict):
                items = j["data"].get("list") or j["data"].get("products") or []
            print(" items", len(items) if isinstance(items, list) else type(items))
            if items:
                print(" sample keys", list(items[0].keys())[:12])
                print(" sample", {k: items[0].get(k) for k in list(items[0].keys())[:6]})

    browser.close()
