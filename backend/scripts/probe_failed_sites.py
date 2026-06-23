"""실패 사이트 API/구조 탐색"""
from playwright.sync_api import sync_playwright

SITES = {
    "wconcept": "https://display.wconcept.co.kr/category/women/001001",
    "spao-new": "https://www.spao.com/u/new?dispCategoryNo=2605000005",
    "spao-ok": "https://www.spao.com/c/ctg?dispCategoryNo=2605000015",
    "cos-new": "https://www.cos.com/ko-kr/women/new-arrivals.html",
    "cos-viewall": "https://www.cos.com/ko-kr/women/view-all.html",
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
        if "json" in ct or "api" in u.lower() or "graphql" in u.lower():
            skip = [
                "google",
                "analytics",
                "facebook",
                "onetrust",
                "hotjar",
                "segment",
                "cookielaw",
                "sentry",
            ]
            if not any(x in u.lower() for x in skip):
                apis.append(u[:280])

    page.on("response", on_resp)

    for name, url in SITES.items():
        apis.clear()
        try:
            page.goto(url, wait_until="domcontentloaded", timeout=90000)
            page.wait_for_timeout(5000)
            for _ in range(6):
                page.evaluate("window.scrollBy(0, 900)")
                page.wait_for_timeout(1000)
            title = page.title()
            links = page.evaluate(
                """() => {
                const as = Array.from(document.querySelectorAll('a[href]'));
                const productLinks = as.filter(a =>
                    /product|goods|Product|goodsNo|dispCategory|\/p\//i.test(a.href)
                ).length;
                const samples = as.filter(a =>
                    /product|goods|Product|goodsNo|dispCategory|\/p\//i.test(a.href)
                ).slice(0, 5).map(a => a.href);
                return { total: as.length, productLinks, samples };
            }"""
            )
            print(f"=== {name} | {title[:60]} | {links}")
            for u in apis[:15]:
                print(f"  {u}")
            if not apis:
                print("  (no api)")
        except Exception as e:
            print(f"=== {name} ERR: {e}")

    browser.close()
