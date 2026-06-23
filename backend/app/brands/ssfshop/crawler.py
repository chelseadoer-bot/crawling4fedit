"""SSF SHOP (에잇세컨즈 등) 카테고리 크롤러"""

from __future__ import annotations

import re
from urllib.parse import urlparse

from playwright.sync_api import Page, sync_playwright

from app.brands.base import BaseBrandCrawler
from app.brands.browser_utils import dismiss_popups, launch_browser, new_stealth_context
from app.core.csv_schema import make_product_row, today_yymmdd

SKIP_NAMES = {"바로가기", "전체 상품", "신상품순", "인기상품순", "낮은가격순", "높은가격순"}
PAGE_WAIT_MS = 2500
BLOCK_WAIT_MS = 2000

EXTRACT_PRODUCTS_JS = """() => {
    const out = [];
    const seen = new Set();
    for (const a of document.querySelectorAll('a[href*="/good"]')) {
        const href = a.href || '';
        if (!href.includes('GM00') || seen.has(href)) continue;
        const img = a.querySelector('img');
        let name = (img?.alt || a.getAttribute('aria-label') || '').trim();
        if (name.includes(',')) name = name.split(',')[0].trim();
        const card = a.closest('li, article, div') || a;
        const priceMatch = (card.innerText || '').match(/[\\d,]+\\s*원/);
        seen.add(href);
        out.push({
            name,
            href,
            image: img?.currentSrc || img?.src || '',
            price: priceMatch ? priceMatch[0] : '',
        });
    }
    return out;
}"""

CLICK_PAGE_JS = """(pageNo) => {
    const el = document.querySelector(`#page_${pageNo}`)
        || document.querySelector(`a.btn_paging[pageno="${pageNo}"]`);
    if (!el || el.classList.contains('disabled')) return false;
    el.click();
    return true;
}"""

ADVANCE_PAGE_JS = """(nextPage) => {
    const direct = document.querySelector(`#page_${nextPage}`)
        || document.querySelector(`a.btn_paging[pageno="${nextPage}"]`);
    if (direct && !direct.classList.contains('disabled')) {
        direct.click();
        return 'direct';
    }
    const next = document.querySelector('#page_next:not(.disabled)');
    if (!next) return '';
    const target = next.getAttribute('pageno');
    if (target === String(nextPage)) {
        next.click();
        return 'next';
    }
    next.click();
    return 'shift';
}"""


def normalize_ssf_url(url: str) -> str:
    parsed = urlparse(url)
    host = parsed.netloc.replace("m.", "www.")
    return f"{parsed.scheme}://{host}{parsed.path}?{parsed.query}" if parsed.query else f"{parsed.scheme}://{host}{parsed.path}"


def get_total_pages(page: Page) -> int:
    last = page.locator("#page_last")
    if last.count():
        raw = last.get_attribute("pageno") or last.inner_text()
        digits = re.sub(r"[^\d]", "", raw or "")
        if digits:
            return max(1, int(digits))
    match = re.search(r"([\d,]+)\s*개\s*상품", page.inner_text("body"))
    if match:
        total_products = int(re.sub(r"[^\d]", "", match.group(1)))
        return max(1, (total_products + 59) // 60)
    return 1


def advance_to_next_page(page: Page, next_page: int) -> bool:
    moved = page.evaluate(ADVANCE_PAGE_JS, next_page)
    if moved in {"direct", "next"}:
        page.wait_for_timeout(PAGE_WAIT_MS)
        return True
    if moved == "shift":
        page.wait_for_timeout(BLOCK_WAIT_MS)
        if page.evaluate(CLICK_PAGE_JS, next_page):
            page.wait_for_timeout(PAGE_WAIT_MS)
            return True
    return False


def extract_page_products(page: Page) -> list[dict]:
    return page.evaluate(EXTRACT_PRODUCTS_JS)


class SsfshopCrawler(BaseBrandCrawler):
    brand_id = "ssfshop"
    brand_name = "8SECONDS"
    source_site = "ssfshop.com"

    def crawl(
        self,
        url: str | None = None,
        headless: bool = True,
        on_progress=None,
        brand_name: str | None = None,
        **_,
    ) -> list[dict]:
        if not url:
            raise ValueError("SSF SHOP URL이 필요합니다.")
        target = normalize_ssf_url(url)
        label = brand_name or "8SECONDS"
        crawled_at = today_yymmdd()
        products: list[dict] = []
        seen: set[str] = set()

        with sync_playwright() as p:
            browser = launch_browser(p, headless=headless)
            _, page = new_stealth_context(browser)
            page.goto(target, wait_until="domcontentloaded", timeout=120000)
            dismiss_popups(page)
            page.wait_for_timeout(3500)

            total_pages = get_total_pages(page)

            for page_no in range(1, total_pages + 1):
                if page_no > 1 and not advance_to_next_page(page, page_no):
                    break

                for item in extract_page_products(page):
                    name = (item.get("name") or "").strip()
                    if not name or name in SKIP_NAMES or len(name) < 3:
                        continue
                    href = item.get("href", "")
                    if not href or href in seen:
                        continue
                    seen.add(href)
                    price = re.sub(r"[^\d]", "", item.get("price", ""))
                    products.append(
                        make_product_row(
                            brand=label,
                            platform=urlparse(target).netloc,
                            product_name=name,
                            regular_price=price,
                            current_price=price,
                            thumbnail=item.get("image", ""),
                            product_detail_url=href,
                            crawled_at=crawled_at,
                        )
                    )

                if on_progress:
                    on_progress(len(products), page_no)

            browser.close()

        if not products:
            raise RuntimeError(f"SSF SHOP 상품을 수집하지 못했습니다: {url}")
        return products
