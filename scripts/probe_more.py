"""29CM pagination + uniqlo/dior probe"""
import json
import re
import urllib.request

# 29CM direct API test
def test_29cm():
    url = "https://display-bff-api.29cm.co.kr/api/v1/listing/items?colorchipVariant=control"
    body = json.dumps({
        "pageType": "CATEGORY_PLP",
        "sortType": "RECOMMENDED",
        "facets": {"categoryFacetInputs": [{"largeId": 268100100, "middleId": 268103100}]},
        "pageRequest": {"page": 1, "size": 50}
    }).encode()
    req = urllib.request.Request(url, data=body, headers={"Content-Type": "application/json", "User-Agent": "Mozilla/5.0"}, method="POST")
    with urllib.request.urlopen(req, timeout=30) as resp:
        data = json.loads(resp.read())
    pag = data["data"]["pagination"]
    print("29CM pagination:", pag)
    print("items page1:", len(data["data"]["list"]))

    body2 = json.dumps({
        "pageType": "CATEGORY_PLP",
        "sortType": "RECOMMENDED",
        "facets": {"categoryFacetInputs": [{"largeId": 268100100, "middleId": 268103100}]},
        "pageRequest": {"page": 2, "size": 50}
    }).encode()
    req2 = urllib.request.Request(url, data=body2, headers={"Content-Type": "application/json"}, method="POST")
    with urllib.request.urlopen(req2, timeout=30) as resp:
        data2 = json.loads(resp.read())
    print("items page2:", len(data2["data"]["list"]))

def probe_uniqlo_dior():
    from playwright.sync_api import sync_playwright
    USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
    for name, url in [
        ("uniqlo", "https://www.uniqlo.com/kr/ko/women/tops"),
        ("dior", "https://www.dior.com/ko_kr/fashion/womens-fashion/ready-to-wear/all-ready-to-wear"),
    ]:
        print(f"\n=== {name} ===")
        api_calls = []
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True, args=["--disable-blink-features=AutomationControlled"])
            context = browser.new_context(user_agent=USER_AGENT, locale="ko-KR")
            page = context.new_page()
            page.add_init_script("Object.defineProperty(navigator, 'webdriver', { get: () => undefined });")

            def on_response(response):
                u = response.url
                if response.status == 200 and ("json" in response.headers.get("content-type", "") or ".json" in u):
                    if any(k in u.lower() for k in ["product", "item", "catalog", "search", "listing", "goods", "cgc", "bff", "api"]):
                        try:
                            body = response.json()
                            api_calls.append({"url": u[:200], "keys": list(body.keys()) if isinstance(body, dict) else f"list[{len(body)}]"})
                        except Exception:
                            pass
            page.on("response", on_response)
            page.goto(url, wait_until="domcontentloaded", timeout=90000)
            page.wait_for_timeout(4000)
            for _ in range(8):
                page.evaluate("window.scrollBy(0, 900)")
                page.wait_for_timeout(800)
            dom = page.evaluate("""() => {
                const imgs = document.querySelectorAll('img[src*="product"], img[src*="uniqlo"], img[alt]');
                const links = Array.from(document.querySelectorAll('a[href]')).map(a=>a.href).filter(h=>/product|goods|item/.test(h));
                const classes = new Set();
                document.querySelectorAll('[class]').forEach(el => {
                    const c = el.className;
                    if (typeof c === 'string' && /product|item|tile|card/i.test(c)) classes.add(c.split(' ')[0]);
                });
                return { imgCount: imgs.length, links: links.slice(0,5), classes: Array.from(classes).slice(0,15), title: document.title, bodyLen: document.body.innerText.length };
            }""")
            print("DOM:", json.dumps(dom, ensure_ascii=False))
            print("APIs:", json.dumps(api_calls[:20], ensure_ascii=False, indent=2))
            browser.close()

if __name__ == "__main__":
    test_29cm()
    probe_uniqlo_dior()
