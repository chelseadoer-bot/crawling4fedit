"""Shopify 스토어 공통 크롤러 (collections/.../products.json)"""

from __future__ import annotations

import json
import re
import time
import urllib.request
from urllib.parse import urlparse

from app.brands.base import BaseBrandCrawler
from app.core.csv_schema import make_product_row, today_yymmdd

PAGE_LIMIT = 250
REQUEST_DELAY_SEC = 0.2
UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/131.0.0.0"}


def site_base(url: str) -> str:
    parsed = urlparse(url)
    return f"{parsed.scheme}://{parsed.netloc}"


def collection_handle(url: str) -> str:
    match = re.search(r"/collections/([^/?#]+)", url)
    if not match:
        raise ValueError(f"Shopify collection URL이 필요합니다: {url}")
    return match.group(1)


def detect_currency(url: str, product: dict) -> str:
    host = urlparse(url).netloc.lower()
    if host.endswith(".fr") or "lemaire" in host:
        return "EUR"
    variants = product.get("variants") or []
    price = (variants[0].get("price") if variants else "") or ""
    if isinstance(price, str) and "," in price and "." not in price.split(",")[-1]:
        return "EUR"
    return "KRW"


def fetch_collection_page(base: str, handle: str, page: int) -> list[dict]:
    query = f"limit={PAGE_LIMIT}&page={page}"
    api_url = f"{base}/collections/{handle}/products.json?{query}"
    req = urllib.request.Request(api_url, headers={**UA, "Referer": f"{base}/collections/{handle}"})
    with urllib.request.urlopen(req, timeout=60) as resp:
        data = json.loads(resp.read().decode())
    products = data.get("products") or []
    return products if isinstance(products, list) else []


def variant_prices(variant: dict) -> tuple[str, str]:
    compare = variant.get("compare_at_price")
    price = variant.get("price") or ""
    if compare not in (None, ""):
        try:
            if float(price) < float(compare):
                return str(compare), str(price)
        except (TypeError, ValueError):
            pass
    return str(price), ""


def product_to_row(product: dict, base: str, brand_name: str, crawled_at: str, currency: str) -> dict:
    variants = product.get("variants") or [{}]
    regular, current = variant_prices(variants[0])
    images = product.get("images") or []
    thumb = images[0].get("src", "") if images else ""
    if thumb.startswith("//"):
        thumb = "https:" + thumb
    handle = product.get("handle") or ""
    detail = f"{base}/products/{handle}" if handle else ""
    colors = ", ".join(
        v.get("title", "")
        for v in variants
        if v.get("title") and v.get("title") != "Default Title"
    )
    return make_product_row(
        brand=brand_name,
        platform="",
        product_name=(product.get("title") or "").strip(),
        regular_price=regular,
        current_price=current,
        color=colors,
        thumbnail=thumb,
        product_detail_url=detail,
        crawled_at=crawled_at,
        currency=currency,
    )


class ShopifyCrawler(BaseBrandCrawler):
    brand_id = "shopify"
    brand_name = "SHOPIFY"
    source_site = "shopify.com"

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
            raise ValueError("Shopify URL이 필요합니다.")
        base = site_base(url)
        handle = collection_handle(url)
        label = brand_name or urlparse(url).netloc.split(".")[0].upper()
        crawled_at = today_yymmdd()
        products: list[dict] = []
        seen: set[str] = set()
        page = 1

        while True:
            batch = fetch_collection_page(base, handle, page)
            if not batch:
                break
            for product in batch:
                pid = str(product.get("id") or product.get("handle") or "")
                if not pid or pid in seen:
                    continue
                seen.add(pid)
                currency = detect_currency(url, product)
                row = product_to_row(product, base, label, crawled_at, currency)
                if category_name and not row.get("category"):
                    row["category"] = category_name
                products.append(row)
            if on_progress:
                on_progress(len(products), page)
            if len(batch) < PAGE_LIMIT:
                break
            page += 1
            time.sleep(REQUEST_DELAY_SEC)

        if not products:
            raise RuntimeError(f"Shopify 상품을 수집하지 못했습니다: {url}")
        return products
