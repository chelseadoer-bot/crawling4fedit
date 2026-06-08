"""Dior probe with headless=False"""
import json
from playwright.sync_api import sync_playwright

URL = "https://www.dior.com/ko_kr/fashion/womens-fashion/ready-to-wear/all-ready-to-wear"
USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"

api_calls = []
with sync_playwright() as p:
    browser = p.chromium.launch(headless=False, args=["--disable-blink-features=AutomationControlled"])
    context = browser.new_context(viewport={"width": 1400, "height": 900}, user_agent=USER_AGENT, locale="ko-KR")
    page = context.new_page()
    page.add_init_script("Object.defineProperty(navigator, 'webdriver', { get: () => undefined });")

    def on_response(response):
        u = response.url
        ct = response.headers.get("content-type", "")
        if response.status == 200 and ("json" in ct or "graphql" in u.lower()):
            if any(k in u.lower() for k in ["product", "catalog", "search", "listing", "graphql", "api", "bff"]):
                try:
                    body = response.json()
                    api_calls.append({"url": u[:250], "keys": list(body.keys()) if isinstance(body, dict) else type(body).__name__})
                except Exception:
                    api_calls.append({"url": u[:250], "keys": "non-json"})

    page.on("response", on_response)
    page.goto(URL, wait_until="domcontentloaded", timeout=120000)
    page.wait_for_timeout(5000)

    for sel in ["#onetrust-accept-btn-handler", "button:has-text('동의')", "button:has-text('Accept')", "button:has-text('확인')"]:
        try:
            btn = page.locator(sel).first
            if btn.count() and btn.is_visible(timeout=2000):
                btn.click()
                page.wait_for_timeout(1000)
        except Exception:
            pass

    for _ in range(10):
        page.evaluate("window.scrollBy(0, 800)")
        page.wait_for_timeout(1000)

    dom = page.evaluate("""() => {
        const products = document.querySelectorAll('[data-testid*="product"], .product-card, article, [class*="ProductCard"], [class*="product-tile"]');
        const links = Array.from(document.querySelectorAll('a[href]')).map(a=>a.href).filter(h=>/product|item|pdp/.test(h));
        return {
            title: document.title,
            productEls: products.length,
            links: links.slice(0, 8),
            bodySample: document.body.innerText.slice(0, 500)
        };
    }""")
    print("DOM:", json.dumps(dom, ensure_ascii=False, indent=2))
    print("APIs:", json.dumps(api_calls[:25], ensure_ascii=False, indent=2))

    # save first API response sample
    for call in api_calls:
        if "product" in call["url"].lower() or "catalog" in call["url"].lower():
            print("Found product API:", call["url"])
            break

    browser.close()
