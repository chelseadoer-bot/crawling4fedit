from playwright.sync_api import sync_playwright

from app.brands.browser_utils import dismiss_popups, launch_browser, new_stealth_context

with sync_playwright() as p:
    browser = launch_browser(p, headless=False)
    _, page = new_stealth_context(browser)
    page.goto("https://www.cos.com/ko-kr/women/new-arrivals.html", wait_until="domcontentloaded", timeout=120000)
    dismiss_popups(page)
    page.wait_for_timeout(5000)
    print("COS title:", page.title())
    print("COS product links:", page.locator('a[href*="product"]').count())
    sect = page.evaluate(
        """() => {
        const html = document.documentElement.innerHTML;
        const m = html.match(/sectId[=:]["']?(\\d{5,6})/);
        return m ? m[1] : null;
    }"""
    )
    print("COS sectId from page:", sect)
    api = (
        "https://www.cos.com/ko-kr/proxy/v1/dp/gbModule/categoryProductList"
        f"?sectId={sect or '252012'}&pageSize=36&pageNum=1&sectDispGbcd=10"
        "&sectDispSiteCd=&preview=false&searchSort=disp_prty&isFilterYn=0"
    )
    res = page.evaluate(
        """async (u) => {
        const r = await fetch(u, { credentials: 'include' });
        const text = await r.text();
        return { ok: r.ok, status: r.status, len: text.length, head: text.slice(0, 120) };
    }""",
        api,
    )
    print("COS api:", res)
    browser.close()
