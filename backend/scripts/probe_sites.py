"""Temporary site probe script."""
import json
import re
from playwright.sync_api import sync_playwright

from app.brands.browser_utils import launch_browser, new_stealth_context


def sniff(url, json_only=False):
    apis = []
    with sync_playwright() as p:
        browser = launch_browser(p, True)
        _, page = new_stealth_context(browser)

        def on_resp(r):
            if r.status != 200:
                return
            u = r.url
            if json_only:
                try:
                    body = r.json()
                    apis.append((u, body))
                except Exception:
                    return
            elif any(k in u for k in ("goods", "product", "brand", "listing", "gods", "God", ".json", "api")):
                try:
                    body = r.json()
                    apis.append((u, body))
                except Exception:
                    pass

        page.on("response", on_resp)
        page.goto(url, wait_until="domcontentloaded", timeout=120000)
        page.wait_for_timeout(4000)
        for _ in range(5):
            page.evaluate("window.scrollBy(0, 1200)")
            page.wait_for_timeout(900)
        dom = page.evaluate(
            """() => {
            const out = [];
            const seen = new Set();
            for (const a of document.querySelectorAll('a[href]')) {
                const href = a.href || '';
                if (!href || seen.has(href)) continue;
                if (!(/goods/i.test(href) || /products/i.test(href) || /product_no=/i.test(href) || /detail/i.test(href))) continue;
                const name = (a.querySelector('img')?.alt || a.innerText || '').trim().replace(/\\s+/g, ' ');
                if (!name || name.length < 3) continue;
                seen.add(href);
                out.push({name: name.slice(0, 80), href});
                if (out.length >= 5) break;
            }
            return out;
        }"""
        )
        html_snip = page.content()[:5000]
        scripts = page.evaluate(
            """() => [...document.querySelectorAll('script')].map(s => s.textContent || '').filter(t => t.includes('product') || t.includes('goods') || t.includes('SSMA')).map(t => t.slice(0,200))"""
        )
        browser.close()
    return apis, dom, html_snip, scripts


if __name__ == "__main__":
    targets = [
        "https://m.ssfshop.com/8seconds/WOMEN/list?dspCtgryNo=SFMA41&brandShopNo=BDMA07A01&brndShopId=8SBSS",
        "https://display-topten10.goodwearmall.com/category/SSMA42",
        "https://www.musinsa.com/brand/musinsastandard/products?gf=F",
    ]
    for url in targets:
        print("===", url[:80])
        apis, dom, html_snip, scripts = sniff(url)
        print("dom", dom)
        print("apis", len(apis))
        for u, body in apis[:12]:
            print(" ", u[:200])
            if isinstance(body, dict):
                print("   keys", list(body.keys())[:8])
                if "data" in body and isinstance(body["data"], dict):
                    print("   data keys", list(body["data"].keys())[:10])
            elif isinstance(body, list):
                print("   list", len(body))
        print("scripts", len(scripts))
        for s in scripts[:3]:
            print(" script", s[:150])
        if "goodwearmall" in url:
            import re
            m = re.search(r"SSMA42", html_snip)
            print("has cat", bool(m))
