"""IMWEB(아임웹) 쇼핑몰 Playwright 크롤러"""

from __future__ import annotations

import re
from urllib.parse import urljoin, urlparse

from playwright.sync_api import sync_playwright

from app.brands.base import BaseBrandCrawler
from app.brands.browser_utils import dismiss_popups, launch_browser, new_stealth_context
from app.core.csv_schema import make_product_row, today_yymmdd

SCROLL_ROUNDS = 25

EXTRACT_JS = """() => {
    const out = [];
    const seen = new Set();
    const cards = document.querySelectorAll('.shop-item._shop_item, .shop-item, li.shop-item');
    for (const card of cards) {
        const link = card.querySelector('a[href*="idx="]') || card.querySelector('a._fade_link') || card.querySelector('a[href]');
        if (!link) continue;
        const href = link.href || link.getAttribute('href') || '';
        if (!href || seen.has(href)) continue;
        const isProduct = href.includes('idx=') || href.includes('shop_view');
        if (!isProduct) continue;
        seen.add(href);
        const titleEl = card.querySelector('.shop-title, .item-detail .shop-title, .prod-name, .item-name');
        let name = titleEl?.innerText?.trim() || '';
        if (!name) {
            const lines = (card.innerText || link.innerText || '').split('\\n').map(s => s.trim()).filter(Boolean);
            name = lines.find(l => l.length > 2 && !/^[\\d$€₩%.,\\s]+$/.test(l)) || lines[0] || '';
        }
        const img = card.querySelector('img')?.currentSrc || card.querySelector('img')?.src || '';
        const text = card.innerText || '';
        const won = text.match(/[\\d,]+\\s*원/g) || [];
        const usd = text.match(/\\$[\\d,]+(?:\\.\\d+)?/g) || [];
        const eur = text.match(/€[\\d,]+(?:\\.\\d+)?/g) || [];
        const prices = won.length ? won : (usd.length ? usd : eur);
        const regular = prices[0] || '';
        const current = prices.length > 1 ? prices[prices.length - 1] : '';
        if (name.length > 2) out.push({ name, href, img, regular, current });
    }
    if (!out.length) {
        for (const a of document.querySelectorAll('a[href*="shop_view"], a[href*="idx="]')) {
            const href = a.href || '';
            if (!href || seen.has(href)) continue;
            seen.add(href);
            const name = a.querySelector('.shop-title')?.innerText?.trim()
                || a.innerText?.trim()?.split('\\n')?.[0]
                || a.querySelector('img')?.alt?.trim() || '';
            const img = a.querySelector('img')?.src || '';
            const text = (a.closest('.shop-item, li, div') || a).innerText || '';
            const prices = text.match(/[\\d,]+\\s*원|\\$[\\d,]+(?:\\.\\d+)?|€[\\d,]+(?:\\.\\d+)?/g) || [];
            if (name.length > 2) out.push({ name, href, img, regular: prices[0] || '', current: prices.length > 1 ? prices[prices.length - 1] : '' });
        }
    }
    return out;
}"""

EENK_REDIRECTS = {
    "eenk.co.kr": "https://eenkshop.com/shop",
    "www.eenk.co.kr": "https://eenkshop.com/shop",
}

CATS_JS = """() => Array.from(document.querySelectorAll('a[href]'))
    .map(a => a.href)
    .filter(h => /^https:\\/\\/[^/]+\\/\\d+$/.test(h))
    .filter((v, i, a) => a.indexOf(v) === i)"""

PAGE_LINKS_JS = """() => Array.from(document.querySelectorAll('.pagination a[href], .paging a[href]'))
    .map(a => a.href)
    .filter(h => h && !h.startsWith('javascript') && h.includes('page='))"""


def _resolve_imweb_url(url: str) -> str:
    host = urlparse(url).netloc.lower()
    if host in EENK_REDIRECTS:
        return EENK_REDIRECTS[host]
    if "eenk.co.kr" in host and urlparse(url).path.upper() in {"/WOMENS", "/WOMEN"}:
        return "https://eenkshop.com/shop"
    return url


def _normalize_price(value: str) -> str:
    value = value.strip()
    if not value:
        return ""
    if value.endswith("원"):
        return re.sub(r"[^\d]", "", value)
    return value


def _product_key(href: str) -> str:
    m = re.search(r"[?&]idx=(\d+)", href)
    return m.group(1) if m else href


def _add_products(
    raw: list[dict],
    *,
    base: str,
    label: str,
    category_name: str | None,
    crawled_at: str,
    seen: set[str],
    products: list[dict],
) -> None:
    for item in raw:
        href = item.get("href", "")
        if href.startswith("/"):
            href = urljoin(base, href)
        key = _product_key(href) if "idx=" in href else (href or item.get("name", ""))
        if key in seen:
            continue
        seen.add(key)
        regular = _normalize_price(item.get("regular", ""))
        current = _normalize_price(item.get("current", ""))
        if regular and current and regular == current:
            current = ""
        products.append(
            make_product_row(
                brand=label,
                platform="",
                product_name=item.get("name", ""),
                category=category_name or "",
                regular_price=regular,
                current_price=current,
                thumbnail=item.get("img", ""),
                product_detail_url=href,
                crawled_at=crawled_at,
            )
        )


def _crawl_eenkshop(
    page,
    *,
    start_url: str,
    base: str,
    label: str,
    category_name: str | None,
    crawled_at: str,
    on_progress=None,
) -> list[dict]:
    products: list[dict] = []
    seen: set[str] = set()
    page.goto(start_url, wait_until="domcontentloaded", timeout=120000)
    dismiss_popups(page)
    page.wait_for_timeout(4000)
    categories = [start_url]
    if "/shop" in urlparse(start_url).path:
        categories = [start_url] + page.evaluate(CATS_JS)

    for cat_url in categories:
        page.goto(cat_url, wait_until="domcontentloaded", timeout=120000)
        dismiss_popups(page)
        page.wait_for_timeout(2500)
        visited_pages: set[str] = set()
        for _ in range(30):
            page_key = page.url
            if page_key in visited_pages:
                break
            visited_pages.add(page_key)
            for _ in range(8):
                _add_products(
                    page.evaluate(EXTRACT_JS),
                    base=base,
                    label=label,
                    category_name=category_name,
                    crawled_at=crawled_at,
                    seen=seen,
                    products=products,
                )
                page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
                page.wait_for_timeout(500)
            if on_progress:
                on_progress(len(products), len(categories))
            next_links = [
                u for u in page.evaluate(PAGE_LINKS_JS)
                if u not in visited_pages
            ]
            if not next_links:
                break
            page.goto(next_links[0], wait_until="domcontentloaded", timeout=120000)
            page.wait_for_timeout(2000)
    return products


class ImwebCrawler(BaseBrandCrawler):
    brand_id = "imweb"
    brand_name = "IMWEB"
    source_site = "imweb.me"

    def crawl(
        self,
        url: str | None = None,
        headless: bool = True,
        on_progress=None,
        brand_name: str | None = None,
        category_name: str | None = None,
        **_,
    ) -> list[dict]:
        if not url:
            raise ValueError("IMWEB URL이 필요합니다.")
        url = _resolve_imweb_url(url)
        base = f"{urlparse(url).scheme}://{urlparse(url).netloc}"
        label = brand_name or "IMWEB"
        crawled_at = today_yymmdd()
        host = urlparse(url).netloc.lower()

        with sync_playwright() as p:
            browser = launch_browser(p, headless=headless)
            _, page = new_stealth_context(browser)
            if "eenkshop.com" in host:
                products = _crawl_eenkshop(
                    page,
                    start_url=url,
                    base=base,
                    label=label,
                    category_name=category_name,
                    crawled_at=crawled_at,
                    on_progress=on_progress,
                )
            else:
                products: list[dict] = []
                seen: set[str] = set()
                page.goto(url, wait_until="domcontentloaded", timeout=120000)
                dismiss_popups(page)
                page.wait_for_timeout(5000)
                prev_count = 0
                for i in range(SCROLL_ROUNDS):
                    _add_products(
                        page.evaluate(EXTRACT_JS),
                        base=base,
                        label=label,
                        category_name=category_name,
                        crawled_at=crawled_at,
                        seen=seen,
                        products=products,
                    )
                    page.evaluate("window.scrollBy(0, window.innerHeight * 0.9)")
                    page.wait_for_timeout(900)
                    if on_progress:
                        on_progress(len(products), i + 1)
                    if len(products) == prev_count and i > 5:
                        break
                    prev_count = len(products)
            browser.close()

        if not products:
            raise RuntimeError(f"IMWEB 상품을 수집하지 못했습니다: {url}")
        return products
