"""사이트 API 구조 탐색용 스크립트"""
import json
import sys
from playwright.sync_api import sync_playwright

URLS = {
    "29cm": "https://www.29cm.co.kr/store/category/list?categoryLargeCode=268100100&categoryMediumCode=268103100&sort=RECOMMENDED&defaultSort=RECOMMENDED&page=1",
    "uniqlo": "https://www.uniqlo.com/kr/ko/women/tops",
    "dior": "https://www.dior.com/ko_kr/fashion/womens-fashion/ready-to-wear/all-ready-to-wear",
}

USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/131.0.0.0 Safari/537.36"
)

def probe(name: str, url: str):
    api_calls = []
    print(f"\n=== {name} ===")

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False, args=["--disable-blink-features=AutomationControlled"])
        context = browser.new_context(viewport={"width": 1280, "height": 900}, user_agent=USER_AGENT, locale="ko-KR")
        page = context.new_page()
        page.add_init_script("Object.defineProperty(navigator, 'webdriver', { get: () => undefined });")

        def on_response(response):
            u = response.url
            ct = response.headers.get("content-type", "")
            if response.status == 200 and ("json" in ct or "graphql" in u.lower() or "api" in u.lower()):
                if any(k in u.lower() for k in ["product", "item", "catalog", "category", "search", "listing", "goods", "graphql"]):
                    try:
                        body = response.json()
                        api_calls.append({"url": u, "keys": list(body.keys()) if isinstance(body, dict) else type(body).__name__, "sample_len": len(body) if isinstance(body, (list, dict)) else 0})
                    except Exception:
                        api_calls.append({"url": u, "keys": "non-json"})

        page.on("response", on_response)
        page.goto(url, wait_until="domcontentloaded", timeout=90000)
        page.wait_for_timeout(5000)

        # scroll
        for _ in range(5):
            page.evaluate("window.scrollBy(0, 800)")
            page.wait_for_timeout(1000)

        page.wait_for_timeout(3000)

        # DOM sample
        dom_info = page.evaluate("""() => {
            const selectors = [
                '[data-testid]', 'article', '.product', '[class*="Product"]',
                '[class*="product"]', 'li[class]', 'a[href*="product"]', 'a[href*="goods"]'
            ];
            const results = {};
            for (const sel of selectors) {
                const els = document.querySelectorAll(sel);
                if (els.length > 0) results[sel] = els.length;
            }
            // get first product-like element classes
            const links = Array.from(document.querySelectorAll('a[href]')).slice(0, 30).map(a => a.href).filter(h => h.includes('product') || h.includes('goods') || h.includes('item'));
            return { counts: results, productLinks: links.slice(0, 5), title: document.title };
        }""")

        print("Title:", dom_info.get("title"))
        print("DOM counts:", json.dumps(dom_info.get("counts"), ensure_ascii=False))
        print("Product links:", dom_info.get("productLinks"))
        print("API calls:", json.dumps(api_calls[:15], ensure_ascii=False, indent=2))

        browser.close()

if __name__ == "__main__":
    target = sys.argv[1] if len(sys.argv) > 1 else "all"
    for name, url in URLS.items():
        if target == "all" or target == name:
            probe(name, url)
