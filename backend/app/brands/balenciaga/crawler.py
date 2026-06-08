"""Balenciaga (Demandware) 크롤러"""

import html
import json
import re
from urllib.parse import unquote, urlparse

from playwright.sync_api import sync_playwright

from app.brands.base import BaseBrandCrawler
from app.brands.browser_utils import dismiss_popups, launch_browser, new_stealth_context
from app.core.csv_schema import empty_row, now_timestamp

GRID_API = (
    "https://www.balenciaga.com/on/demandware.store/Sites-BAL-R-APAC-Site/ko_KR/"
    "Search-UpdateGrid?cgid={cgid}&start={start}&sz={size}"
)
PAGE_SIZE = 48

URL_CGID_MAP = {
    "women": "women",
    "women-rtw": "women_rtw_all",
    "ready-to-wear": "women_rtw_all",
    "레디": "women_rtw_all",
    "레디-투-웨어": "women_rtw_all",
}


def extract_cgid(url: str) -> str:
    path = unquote(urlparse(url).path).strip("/").lower()
    parts = path.split("/")
    if "women_rtw" in path or "레디" in path:
        return "women_rtw_all"
    slug = parts[-1] if parts else "women"
    for key, cgid in URL_CGID_MAP.items():
        if key in slug or key in path:
            return cgid
    if parts and parts[-1] not in ("ko-kr", "women"):
        return parts[-1].replace(" ", "-")
    return "women_rtw_all" if "women" in path else "women"


def parse_gtm_products(fragment: str, crawled_at: str) -> list[dict]:
    products: list[dict] = []
    seen: set[str] = set()
    for raw in re.findall(r'data-gtmproduct="([^"]+)"', fragment):
        decoded = html.unescape(raw)
        try:
            data = json.loads(decoded)
        except json.JSONDecodeError:
            continue
        pid = str(data.get("id") or "")
        name = data.get("name") or data.get("productName") or ""
        if not pid or not name or pid in seen:
            continue
        seen.add(pid)
        price = str(data.get("price") or data.get("salePrice") or data.get("unitPrice") or "")
        prod_url = data.get("url") or data.get("productUrl") or ""
        if prod_url and not prod_url.startswith("http"):
            prod_url = "https://www.balenciaga.com" + prod_url
        image = data.get("image") or data.get("imageUrl") or ""
        row = empty_row()
        row.update(
            {
                "brand": "BALENCIAGA",
                "product_id": pid,
                "product_name": name,
                "category_large": data.get("category") or "",
                "category_small": "",
                "price_original": re.sub(r"[^\d]", "", price) or price,
                "price_sale": "",
                "discount_rate": "",
                "color": data.get("variant") or data.get("color") or "",
                "sizes_available": "",
                "stock_status": "unknown",
                "product_url": prod_url,
                "image_url": image if str(image).startswith("http") else "",
                "crawled_at": crawled_at,
                "source_site": "balenciaga.com",
            }
        )
        products.append(row)
    return products


def parse_dom_products(page, crawled_at: str) -> list[dict]:
    raw = page.evaluate(
        """() => {
        const tiles = document.querySelectorAll('[data-gtmproduct], .product-tile, li[data-pid]');
        const out = [];
        for (const el of tiles) {
            const gtm = el.getAttribute('data-gtmproduct');
            if (gtm) { out.push({ type: 'gtm', gtm }); continue; }
            const a = el.querySelector('a[href*="/product"], a[href*="products"]') || el.closest('a');
            const name = el.querySelector('.name, .product-name, h2, h3')?.innerText?.trim()
                || el.getAttribute('data-product-name') || '';
            const price = el.innerText.match(/₩[\\d,]+/)?.[0] || '';
            if (name && a) out.push({ type: 'dom', name, href: a.href, price, img: el.querySelector('img')?.src || '' });
        }
        return out;
    }"""
    )
    products: list[dict] = []
    seen: set[str] = set()
    for item in raw:
        if item.get("type") == "gtm":
            batch = parse_gtm_products(f'data-gtmproduct="{item["gtm"]}"', crawled_at)
            for row in batch:
                if row["product_id"] not in seen:
                    seen.add(row["product_id"])
                    products.append(row)
        elif item.get("name"):
            key = item.get("href", item["name"])
            if key in seen:
                continue
            seen.add(key)
            row = empty_row()
            row.update(
                {
                    "brand": "BALENCIAGA",
                    "product_id": re.search(r"/(\d+)", item.get("href", "")).group(1) if re.search(r"/(\d+)", item.get("href", "")) else "",
                    "product_name": item["name"],
                    "price_original": re.sub(r"[^\d]", "", item.get("price", "")),
                    "product_url": item.get("href", ""),
                    "image_url": item.get("img", ""),
                    "crawled_at": crawled_at,
                    "source_site": "balenciaga.com",
                }
            )
            products.append(row)
    return products


class BalenciagaCrawler(BaseBrandCrawler):
    brand_id = "balenciaga"
    brand_name = "BALENCIAGA"
    source_site = "balenciaga.com"

    def crawl(
        self,
        url: str | None = None,
        headless: bool = False,
        on_progress=None,
    ) -> list[dict]:
        target_url = url or (
            "https://www.balenciaga.com/ko-kr/%EC%97%AC%EC%84%B1/"
            "%EC%97%AC%EC%84%B1-%EB%A0%88%EB%94%94-%ED%88%AC-%EC%9B%A8%EC%96%B4"
        )
        cgid = extract_cgid(target_url)
        crawled_at = now_timestamp()
        all_products: list[dict] = []
        seen: set[str] = set()

        with sync_playwright() as p:
            browser = launch_browser(p, headless=headless)
            context, page = new_stealth_context(browser)
            page.goto(target_url, wait_until="domcontentloaded", timeout=120000)
            dismiss_popups(page)
            page.wait_for_timeout(4000)

            def merge_batch(batch: list[dict]) -> None:
                for row in batch:
                    key = row["product_id"] or row["product_name"]
                    if key in seen:
                        continue
                    seen.add(key)
                    all_products.append(row)

            # 초기 페이지 + 스크롤
            merge_batch(parse_gtm_products(page.content(), crawled_at))
            merge_batch(parse_dom_products(page, crawled_at))

            for round_i in range(25):
                page.evaluate("window.scrollBy(0, window.innerHeight)")
                page.wait_for_timeout(800)
                merge_batch(parse_gtm_products(page.content(), crawled_at))

                for selector in [
                    "button:has-text('더 로드하기')",
                    "button:has-text('Load more')",
                    ".load-more button",
                ]:
                    try:
                        btn = page.locator(selector).first
                        if btn.count() and btn.is_visible(timeout=500):
                            btn.click()
                            page.wait_for_timeout(2500)
                            merge_batch(parse_gtm_products(page.content(), crawled_at))
                            break
                    except Exception:
                        pass

                if on_progress:
                    on_progress(len(all_products), round_i + 1)

            # API 페이지네이션
            start = 0
            while start < 5000:
                api_url = GRID_API.format(cgid=cgid, start=start, size=PAGE_SIZE)
                fragment = page.evaluate(
                    """async (url) => {
                    const res = await fetch(url, { credentials: 'include' });
                    if (!res.ok) return '';
                    return await res.text();
                }""",
                    api_url,
                )
                if not fragment or "data-gtmproduct" not in fragment:
                    break
                batch = parse_gtm_products(fragment, crawled_at)
                if not batch:
                    break
                before = len(all_products)
                merge_batch(batch)
                if len(all_products) == before:
                    break
                if len(batch) < PAGE_SIZE:
                    break
                start += PAGE_SIZE

            browser.close()

        if not all_products:
            raise RuntimeError("Balenciaga 상품을 수집하지 못했습니다.")
        return all_products
