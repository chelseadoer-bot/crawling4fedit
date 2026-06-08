"""사이트 API/구조 탐색 스크립트"""
from playwright.sync_api import sync_playwright

SITES = {
    "cos": "https://www.cos.com/ko-kr/women",
    "hm": "https://www2.hm.com/ko_kr/ladies/shop-by-product/view-all.html",
    "barnet": "https://the-barnnet.com/product/list.html?cate_no=24",
    "balenciaga": "https://www.balenciaga.com/ko-kr/women",
    "chanel": "https://www.chanel.com/kr/fashion/",
    "moncler": "https://www.moncler.com/ko-kr/women",
    "dior": "https://www.dior.com/ko_kr/fashion/womens-fashion/ready-to-wear/all-ready-to-wear",
    "zara": "https://www.zara.com/kr/ko/woman-new-in-l1180.html",
}

with sync_playwright() as p:
    browser = p.chromium.launch(
        headless=True, args=["--disable-blink-features=AutomationControlled"]
    )
    ctx = browser.new_context(
        user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/131.0.0.0",
        locale="ko-KR",
    )
    page = ctx.new_page()
    apis: list[str] = []

    def on_resp(r):
        u = r.url
        ct = r.headers.get("content-type", "")
        if r.status != 200:
            return
        if "json" not in ct and "/api/" not in u and "graphql" not in u:
            return
        skip = ["google", "analytics", "facebook", "onetrust", "hotjar", "segment", "cookielaw"]
        if any(x in u.lower() for x in skip):
            return
        apis.append(u[:220])

    page.on("response", on_resp)

    for name, url in SITES.items():
        apis.clear()
        try:
            page.goto(url, wait_until="domcontentloaded", timeout=90000)
            page.wait_for_timeout(5000)
            for _ in range(4):
                page.evaluate("window.scrollBy(0, 900)")
                page.wait_for_timeout(1200)
            title = page.title()
            count = page.locator(
                'a[href*="/product"], a[href*="products"], .product-grid-product, article[data-testid]'
            ).count()
            print(f"=== {name} | {title[:70]} | links: {count}")
            for u in apis[:10]:
                print(f"  {u}")
            if not apis:
                print("  (no json api captured)")
        except Exception as e:
            print(f"=== {name} ERR: {e}")

    browser.close()
