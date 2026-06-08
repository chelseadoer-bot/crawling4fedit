from playwright.sync_api import sync_playwright

from app.brands.browser_utils import dismiss_popups, launch_browser, new_stealth_context

SITES = [
    ("barnet", "https://the-barnnet.com/product/list.html?cate_no=24"),
    ("zara", "https://www.zara.com/kr/ko/woman-new-in-l1180.html"),
    ("cos", "https://www.cos.com/ko-kr/women"),
    ("hm", "https://www2.hm.com/ko_kr/ladies/shop-by-product/view-all.html"),
]

with sync_playwright() as p:
    browser = launch_browser(p, headless=False)
    ctx, page = new_stealth_context(browser)
    apis: list[str] = []

    def on_resp(r):
        u = r.url
        ct = r.headers.get("content-type", "")
        if r.status != 200:
            return
        if "json" not in ct and "/api/" not in u:
            return
        skip = ["google", "analytics", "facebook", "onetrust", "abtasty", "brightcove"]
        if any(x in u.lower() for x in skip):
            return
        apis.append(u[:240])

    page.on("response", on_resp)

    for name, url in SITES:
        apis.clear()
        page.goto(url, wait_until="domcontentloaded", timeout=120000)
        page.wait_for_timeout(4000)
        dismiss_popups(page)
        for _ in range(5):
            page.evaluate("window.scrollBy(0, 900)")
            page.wait_for_timeout(1000)
        print(f"=== {name} | {page.title()[:70]}")
        count = page.locator("a[href*='product']").count()
        print(f"  product links: {count}")
        for u in apis[:12]:
            print(f"  {u}")
        if name == "barnet":
            sample = page.evaluate(
                """() => Array.from(document.querySelectorAll('.prdList .name a, .description .name a'))
                .slice(0,5).map(a => ({t: a.innerText.trim(), h: a.href}))"""
            )
            print("  sample:", sample)

    browser.close()
