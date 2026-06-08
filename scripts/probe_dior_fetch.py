"""Dior in-browser fetch via Playwright session"""
import json
from playwright.sync_api import sync_playwright

URL = "https://www.dior.com/ko_kr/fashion/womens-fashion/ready-to-wear/all-ready-to-wear"
API = "https://www.dior.com/couture/ecommerce/api/v1/catalog/categories/diorcom_femme_pretaporter_tout/products?offset=0&limit=48"

with sync_playwright() as p:
    browser = p.chromium.launch(headless=False, args=["--disable-blink-features=AutomationControlled"])
    context = browser.new_context(locale="ko-KR", viewport={"width": 1400, "height": 900})
    page = context.new_page()
    page.add_init_script("Object.defineProperty(navigator, 'webdriver', { get: () => undefined });")

    page.goto(URL, wait_until="domcontentloaded", timeout=120000)
    for i in range(20):
        if "unavailable" not in page.title().lower():
            break
        page.wait_for_timeout(3000)

    result = page.evaluate("""async (apiUrl) => {
        try {
            const res = await fetch(apiUrl, { credentials: 'include', headers: { 'Accept': 'application/json' } });
            const text = await res.text();
            return { status: res.status, text: text.slice(0, 2000) };
        } catch (e) {
            return { error: String(e) };
        }
    }""", API)
    print("fetch result:", json.dumps(result, ensure_ascii=False, indent=2)[:2500])

    browser.close()
