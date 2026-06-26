"""범용 Playwright 스토어 크롤러 (SPAO, W컨셉, 에잇세컨즈, 릿킴 등)"""

from __future__ import annotations

import re
from urllib.parse import urlparse

from playwright.sync_api import sync_playwright

from app.brands.base import BaseBrandCrawler
from app.brands.browser_utils import dismiss_popups, launch_browser, new_stealth_context
from app.core.csv_schema import make_product_row, today_yymmdd

SCROLL_ROUNDS = 18

SITE_HINTS: dict[str, dict] = {
    "spao.com": {"brand": "SPAO", "link_patterns": ["/products/", "/product/", "dispCategoryNo"]},
    "wconcept.co.kr": {"brand": "WCONCEPT", "link_patterns": ["/Product/", "/product/", "goodsNo"]},
    "ssfshop.com": {"brand": "8SECONDS", "link_patterns": ["/goods/", "/product/", "dspCtgryNo"]},
    "reetkeem.com": {"brand": "REETKEEM", "link_patterns": ["/product/", "/goods/", "/category/"]},
}


def site_hint(url: str, brand_name: str | None = None) -> dict:
    host = urlparse(url).netloc.lower().replace("www.", "").replace("m.", "")
    for key, hint in SITE_HINTS.items():
        if key in host:
            return {**hint, "brand": brand_name or hint["brand"]}
    return {
        "brand": brand_name or host.split(".")[0].upper(),
        "link_patterns": ["/product", "/goods", "/Product", "detail"],
    }


class PlaywrightStoreCrawler(BaseBrandCrawler):
    brand_id = "playwright_store"
    brand_name = "STORE"
    source_site = "store"

    def crawl(
        self,
        url: str | None = None,
        headless: bool = True,
        on_progress=None,
        brand_name: str | None = None,
        **_,
    ) -> list[dict]:
        if not url:
            raise ValueError("URL이 필요합니다.")
        hint = site_hint(url, brand_name)
        patterns = hint["link_patterns"]
        crawled_at = today_yymmdd()
        products: list[dict] = []
        seen: set[str] = set()

        with sync_playwright() as p:
            browser = launch_browser(p, headless=headless)
            _, page = new_stealth_context(browser)
            page.goto(url, wait_until="domcontentloaded", timeout=120000)
            dismiss_popups(page)
            page.wait_for_timeout(3500)

            for i in range(SCROLL_ROUNDS):
                raw = page.evaluate(
                    """(patterns) => {
                    const anchors = Array.from(document.querySelectorAll('a[href]'));
                    const out = [];
                    const seen = new Set();
                    for (const a of anchors) {
                        const href = a.href || '';
                        if (!patterns.some(p => href.includes(p))) continue;
                        if (seen.has(href)) continue;
                        seen.add(href);
                        const name = a.querySelector('img')?.alt?.trim()
                            || a.getAttribute('aria-label')?.trim()
                            || a.querySelector('[class*="name"], [class*="title"], p, span, strong')?.innerText?.trim()
                            || '';
                        const img = a.querySelector('img')?.currentSrc || a.querySelector('img')?.src || '';
                        const price = (a.closest('li, article, div') || a).innerText.match(/[\\d,]+\\s*원|₩\\s*[\\d,]+/)?.[0] || '';
                        if (name && name.length > 2) out.push({ name, href, img, price });
                    }
                    return out;
                }""",
                    patterns,
                )
                for item in raw:
                    key = item.get("href", item.get("name", ""))
                    if key in seen:
                        continue
                    seen.add(key)
                    price = re.sub(r"[^\d]", "", item.get("price", ""))
                    products.append(
                        make_product_row(
                            brand=hint["brand"],
                            platform="",
                            product_name=item["name"],
                            regular_price=price,
                            current_price="",
                            thumbnail=item.get("img", ""),
                            product_detail_url=item.get("href", ""),
                            crawled_at=crawled_at,
                        )
                    )
                page.evaluate("window.scrollBy(0, window.innerHeight * 0.85)")
                page.wait_for_timeout(800)
                if on_progress:
                    on_progress(len(products), i + 1)

            browser.close()

        if not products:
            raise RuntimeError(f"상품을 수집하지 못했습니다: {url}")
        return products
