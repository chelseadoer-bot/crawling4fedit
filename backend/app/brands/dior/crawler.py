"""Dior 브랜드 크롤러 (Akamai 우회: headless=False 필수)"""

import json
import re
from urllib.parse import urlparse

from playwright.sync_api import sync_playwright

from app.brands.base import BaseBrandCrawler
from app.brands.browser_utils import dismiss_popups, launch_browser, new_stealth_context
from app.core.csv_schema import empty_row, now_timestamp

CATEGORY_API_MAP = {
    "all-ready-to-wear": "diorcom_femme_pretaporter_tout",
    "ready-to-wear": "diorcom_femme_pretaporter_tout",
}


def extract_category_id(url: str) -> str:
    path = urlparse(url).path.strip("/").split("/")
    slug = path[-1] if path else ""
    return CATEGORY_API_MAP.get(slug, "diorcom_femme_pretaporter_tout")


def parse_api_product(prod: dict, crawled_at: str) -> dict | None:
    title = prod.get("title") or prod.get("name") or prod.get("productName") or ""
    if not title:
        return None

    price = ""
    for key in ("price", "salePrice", "formattedPrice"):
        if prod.get(key):
            price = str(prod[key])
            break
    if not price and isinstance(prod.get("price"), dict):
        price = str(prod["price"].get("value") or prod["price"].get("formatted") or "")

    image = ""
    for key in ("uri", "image", "imageUrl", "thumbnail"):
        if prod.get(key):
            image = prod[key]
            break
    if not image and prod.get("images"):
        imgs = prod["images"]
        if isinstance(imgs, list) and imgs:
            image = imgs[0].get("uri") or imgs[0].get("url") or ""
        elif isinstance(imgs, dict):
            image = next(iter(imgs.values()), {}).get("uri", "") if imgs else ""

    color = prod.get("subtitle") or prod.get("color") or ""
    sku = prod.get("sku") or prod.get("code") or prod.get("backend_sku") or prod.get("id") or ""
    url = prod.get("url") or prod.get("productUrl") or ""

    row = empty_row()
    row.update(
        {
            "brand": "DIOR",
            "product_id": str(sku),
            "product_name": title,
            "category_large": "여성 RTW",
            "category_small": "",
            "price_original": price,
            "price_sale": "",
            "discount_rate": "",
            "color": color,
            "sizes_available": "",
            "stock_status": prod.get("status", "unknown"),
            "product_url": url if url.startswith("http") else f"https://www.dior.com{url}" if url else "",
            "image_url": image if image.startswith("http") else f"https:{image}" if image.startswith("//") else image,
            "crawled_at": crawled_at,
            "source_site": "dior.com",
        }
    )
    return row


def parse_api_payload(payload: dict, crawled_at: str) -> list[dict]:
    products = []
    seen = set()

    candidates = []
    if isinstance(payload, list):
        candidates = payload
    elif isinstance(payload, dict):
        for key in ("products", "items", "hits", "results", "content", "elements"):
            val = payload.get(key)
            if isinstance(val, list):
                candidates.extend(val)
            elif isinstance(val, dict):
                for sub in ("products", "items", "list"):
                    if isinstance(val.get(sub), list):
                        candidates.extend(val[sub])

    for prod in candidates:
        if not isinstance(prod, dict):
            continue
        row = parse_api_product(prod, crawled_at)
        if not row:
            continue
        key = row["product_id"] or row["product_name"]
        if key in seen:
            continue
        seen.add(key)
        products.append(row)

    return products


def extract_from_dom(page, crawled_at: str) -> list[dict]:
    raw = page.evaluate(
        """() => {
        const cards = document.querySelectorAll('a[href*="/fashion/products/"]');
        return Array.from(cards).map(a => {
            const href = a.href;
            const img = a.querySelector('img')?.src || a.querySelector('img')?.dataset?.src || '';
            const texts = Array.from(a.querySelectorAll('span, p, h2, h3')).map(el => el.innerText.trim()).filter(Boolean);
            const name = texts.find(t => t.length > 3) || a.getAttribute('aria-label') || '';
            const priceText = texts.find(t => /₩|원|KRW|\\d{1,3}(,\\d{3})+/.test(t)) || '';
            return { href, img, name, price: priceText.replace(/[^0-9]/g, '') };
        }).filter(x => x.name && x.href.includes('/fashion/products/'));
    }"""
    )

    products = []
    seen = set()
    for item in raw:
        key = item["href"]
        if key in seen:
            continue
        seen.add(key)
        row = empty_row()
        row.update(
            {
                "brand": "DIOR",
                "product_id": re.search(r"/products/([^/?#]+)", item["href"]).group(1) if re.search(r"/products/", item["href"]) else "",
                "product_name": item.get("name", ""),
                "category_large": "여성 RTW",
                "category_small": "",
                "price_original": item.get("price", ""),
                "price_sale": "",
                "discount_rate": "",
                "color": "",
                "sizes_available": "",
                "stock_status": "unknown",
                "product_url": item.get("href", ""),
                "image_url": item.get("img", ""),
                "crawled_at": crawled_at,
                "source_site": "dior.com",
            }
        )
        products.append(row)
    return products


def wait_for_page_ready(page, max_wait_sec: int = 90) -> bool:
    for _ in range(max_wait_sec // 3):
        title = page.title().lower()
        body = page.locator("body").inner_text(timeout=2000).lower()
        if "unavailable" in title or "unavailable" in body[:200]:
            page.wait_for_timeout(3000)
            continue
        if page.locator('a[href*="/fashion/products/"]').count() > 0:
            return True
        page.wait_for_timeout(3000)
    return "unavailable" not in page.title().lower()


class DiorCrawler(BaseBrandCrawler):
    brand_id = "dior"
    brand_name = "DIOR"
    source_site = "dior.com"

    def crawl(self, url: str | None = None, headless: bool = False) -> list[dict]:
        target_url = url or (
            "https://www.dior.com/ko_kr/fashion/womens-fashion/ready-to-wear/all-ready-to-wear"
        )
        category_id = extract_category_id(target_url)
        crawled_at = now_timestamp()
        api_products: list[dict] = []
        captured_payloads: list[dict] = []

        with sync_playwright() as p:
            browser = launch_browser(p, headless=False)
            context, page = new_stealth_context(browser)

            def on_response(response):
                u = response.url
                if response.status != 200:
                    return
                if not any(k in u for k in ["/ecommerce/api/", "/products", "catalog", "listing"]):
                    return
                try:
                    if "json" in response.headers.get("content-type", ""):
                        captured_payloads.append(response.json())
                except Exception:
                    pass

            page.on("response", on_response)
            page.goto(target_url, wait_until="domcontentloaded", timeout=120000)
            dismiss_popups(page)

            if not wait_for_page_ready(page):
                browser.close()
                raise RuntimeError(
                    "Dior 사이트 접근이 차단되었습니다. "
                    "브라우저 창에서 보안 확인 후 다시 시도해주세요."
                )

            for _ in range(12):
                page.evaluate("window.scrollBy(0, window.innerHeight * 0.9)")
                page.wait_for_timeout(1200)

            for payload in captured_payloads:
                api_products.extend(parse_api_payload(payload, crawled_at))

            if not api_products:
                offset = 0
                limit = 48
                while offset < 2000:
                    api_url = (
                        f"https://www.dior.com/couture/ecommerce/api/v1/catalog/"
                        f"categories/{category_id}/products?offset={offset}&limit={limit}"
                    )
                    result = page.evaluate(
                        """async (url) => {
                        try {
                            const res = await fetch(url, { credentials: 'include', headers: { Accept: 'application/json' } });
                            if (!res.ok) return { ok: false, status: res.status };
                            return { ok: true, data: await res.json() };
                        } catch (e) {
                            return { ok: false, error: String(e) };
                        }
                    }""",
                        api_url,
                    )
                    if not result.get("ok"):
                        break
                    batch = parse_api_payload(result.get("data") or {}, crawled_at)
                    if not batch:
                        break
                    api_products.extend(batch)
                    if len(batch) < limit:
                        break
                    offset += limit

            products = api_products
            if not products:
                products = extract_from_dom(page, crawled_at)

            browser.close()

        if not products:
            raise RuntimeError("Dior 상품을 수집하지 못했습니다. 사이트 차단 또는 구조 변경 가능성이 있습니다.")

        deduped = []
        seen = set()
        for row in products:
            key = row.get("product_id") or row.get("product_name")
            if key in seen:
                continue
            seen.add(key)
            deduped.append(row)

        return deduped
