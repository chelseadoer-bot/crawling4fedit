"""Dior with real Chrome channel + long wait for Akamai"""
import json
from playwright.sync_api import sync_playwright

URL = "https://www.dior.com/ko_kr/fashion/womens-fashion/ready-to-wear/all-ready-to-wear"

with sync_playwright() as p:
    try:
        browser = p.chromium.launch(channel="chrome", headless=False, args=["--disable-blink-features=AutomationControlled"])
    except Exception:
        browser = p.chromium.launch(headless=False, args=["--disable-blink-features=AutomationControlled"])

    context = browser.new_context(
        viewport={"width": 1400, "height": 900},
        locale="ko-KR",
        timezone_id="Asia/Seoul",
    )
    page = context.new_page()
    page.add_init_script("Object.defineProperty(navigator, 'webdriver', { get: () => undefined });")

    captured = []
    def on_response(response):
        u = response.url
        if response.status == 200 and "json" in response.headers.get("content-type", ""):
            if any(k in u for k in ["product", "catalog", "search", "listing", "grid", "api"]):
                try:
                    captured.append({"url": u[:300], "body": response.json()})
                except Exception:
                    pass

    page.on("response", on_response)
    page.goto(URL, wait_until="load", timeout=120000)

    for i in range(30):
        title = page.title()
        text = page.locator("body").inner_text()[:200]
        print(f"wait {i}: title={title!r} text={text[:80]!r}")
        if "unavailable" not in title.lower() and "unavailable" not in text.lower():
            break
        page.wait_for_timeout(3000)

    page.wait_for_timeout(5000)
    for _ in range(8):
        page.evaluate("window.scrollBy(0, 900)")
        page.wait_for_timeout(1200)

    dom = page.evaluate("""() => {
        const tiles = document.querySelectorAll('a[href*="/fashion/products/"], [data-testid], article');
        const links = Array.from(document.querySelectorAll('a[href*="/fashion/products/"]')).map(a => ({href: a.href, text: a.innerText.trim().slice(0,80)}));
        return { title: document.title, tileCount: tiles.length, links: links.slice(0, 10), body: document.body.innerText.slice(0, 300) };
    }""")
    print("DOM:", json.dumps(dom, ensure_ascii=False, indent=2))
    print("Captured APIs:", len(captured))
    for c in captured[:3]:
        print("API URL:", c["url"])
        if isinstance(c["body"], dict):
            print(" keys:", list(c["body"].keys())[:10])

    browser.close()
