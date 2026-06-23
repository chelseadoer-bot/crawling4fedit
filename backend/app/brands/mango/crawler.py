"""MANGO shop.mango.com 카테고리 크롤러"""

from __future__ import annotations

import re
from urllib.parse import urlparse

from playwright.sync_api import sync_playwright

from app.brands.base import BaseBrandCrawler
from app.brands.browser_utils import dismiss_popups, launch_browser, new_stealth_context
from app.core.csv_schema import make_product_row, today_yymmdd

SCROLL_ROUNDS = 22


def clean_mango_name(raw: str) -> str:
    name = raw.strip()
    if " Ref:" in name:
        name = name.split(" Ref:")[0].strip()
    if " - " in name:
        name = name.split(" - ")[0].strip()
    return name


class MangoCrawler(BaseBrandCrawler):
    brand_id = "mango"
    brand_name = "MANGO"
    source_site = "shop.mango.com"

    def crawl(
        self,
        url: str | None = None,
        headless: bool = True,
        on_progress=None,
        brand_name: str | None = None,
        **_,
    ) -> list[dict]:
        if not url:
            raise ValueError("MANGO URL이 필요합니다.")
        label = brand_name or "MANGO"
        crawled_at = today_yymmdd()
        products: list[dict] = []
        seen: set[str] = set()

        with sync_playwright() as p:
            browser = launch_browser(p, headless=headless)
            _, page = new_stealth_context(browser)
            page.goto(url, wait_until="domcontentloaded", timeout=120000)
            dismiss_popups(page)
            page.wait_for_timeout(4000)

            for i in range(SCROLL_ROUNDS):
                raw = page.evaluate(
                    """() => {
                    const out = [];
                    const seen = new Set();
                    for (const a of document.querySelectorAll('a[href*="/p/"], a[href*="/product"]')) {
                        const href = a.href || '';
                        if (!href || seen.has(href)) continue;
                        const name = (a.getAttribute('aria-label') || a.querySelector('img')?.alt || '').trim();
                        if (!name || name.length < 3) continue;
                        const img = a.querySelector('img')?.currentSrc || a.querySelector('img')?.src || '';
                        const price = (a.closest('article, li, div') || a).innerText.match(/[\\d.,]+\\s*₩|[\\d.,]+\\s*원/)?.[0] || '';
                        seen.add(href);
                        out.push({ name, href, img, price });
                    }
                    return out;
                }"""
                )
                for item in raw:
                    href = item.get("href", "")
                    if href in seen:
                        continue
                    name = clean_mango_name(item.get("name", ""))
                    if not name:
                        continue
                    seen.add(href)
                    price = re.sub(r"[^\d]", "", item.get("price", ""))
                    products.append(
                        make_product_row(
                            brand=label,
                            platform=urlparse(url).netloc,
                            product_name=name,
                            regular_price=price,
                            current_price=price,
                            thumbnail=item.get("img", ""),
                            product_detail_url=href,
                            crawled_at=crawled_at,
                        )
                    )
                page.evaluate("window.scrollBy(0, window.innerHeight * 0.85)")
                page.wait_for_timeout(850)
                if on_progress:
                    on_progress(len(products), i + 1)

            browser.close()

        if not products:
            raise RuntimeError(f"MANGO 상품을 수집하지 못했습니다: {url}")
        return products
