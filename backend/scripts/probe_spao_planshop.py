from playwright.sync_api import sync_playwright

URL = (
    "https://www.spao.com/p/planshop"
    "?exhibitionNo=202605000704&pageId=1782171792741&preCornerNo=R13701005_menuCategory"
)

with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    page = browser.new_page()
    apis: list[str] = []

    def on_resp(r):
        u = r.url
        if r.status != 200:
            return
        if "spao.com" not in u:
            return
        if any(x in u for x in ("criteo", "airbridge", "cre.ma", "naver", "google", "tuho")):
            return
        if "json" in r.headers.get("content-type", "") or "/api/" in u or "/v1/" in u:
            apis.append(u)

    page.on("response", on_resp)
    page.goto(URL, wait_until="networkidle", timeout=120000)
    page.wait_for_timeout(3000)
    for u in sorted(set(apis)):
        print(u)
    sample = page.evaluate(
        """() => Array.from(document.querySelectorAll('a[href*="itemNo"]'))
        .slice(0, 5)
        .map(a => ({
            name: (a.querySelector('img')?.alt || a.innerText || '').trim().slice(0, 80),
            href: a.href
        }))"""
    )
    print("DOM:", sample)
    browser.close()
