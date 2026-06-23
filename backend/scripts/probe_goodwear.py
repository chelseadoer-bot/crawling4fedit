import json
import re
from playwright.sync_api import sync_playwright

from app.brands.browser_utils import launch_browser, new_stealth_context

url = "https://display-topten10.goodwearmall.com/category/SSMA42"
with sync_playwright() as p:
    browser = launch_browser(p, True)
    _, page = new_stealth_context(browser)
    captured = []

    def on_resp(r):
        if r.status != 200:
            return
        ct = r.headers.get("content-type", "")
        if "json" not in ct:
            return
        try:
            captured.append((r.url, r.json()))
        except Exception:
            pass

    page.on("response", on_resp)
    page.goto(url, wait_until="domcontentloaded", timeout=120000)
    page.wait_for_timeout(5000)
    for _ in range(8):
        page.evaluate("window.scrollBy(0, 1200)")
        page.wait_for_timeout(800)
    dom = page.evaluate(
        """() => {
        const out = [];
        const seen = new Set();
        for (const a of document.querySelectorAll('a[href]')) {
            const href = a.href || '';
            if (!/goods|product|item/i.test(href)) continue;
            if (seen.has(href)) continue;
            const text = (a.innerText || '').trim();
            if (!text || text.length < 5) continue;
            seen.add(href);
            out.push({href, text: text.slice(0,100)});
            if (out.length >= 5) break;
        }
        return out;
    }"""
    )
    html = page.content()
    browser.close()

print("dom", dom)
print("json responses", len(captured))
for u, body in captured:
    if "product" in u.lower() or "goods" in u.lower() or "category" in u.lower() or "plp" in u.lower():
        print("URL", u[:200])
        if isinstance(body, dict):
            print(" keys", list(body.keys())[:10])
            data = body.get("data") or body.get("payload") or body
            if isinstance(data, dict):
                print(" data keys", list(data.keys())[:12])

m = re.search(r"<script id=\"__NEXT_DATA__\"[^>]*>(.*?)</script>", html, re.S)
if m:
    data = json.loads(m.group(1))
    pp = data.get("props", {}).get("pageProps", {})
    print("pageProps keys", list(pp.keys())[:15])
