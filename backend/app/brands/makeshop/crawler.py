"""MakeShop shopbrand.html 크롤러"""

from __future__ import annotations

import re
import urllib.request
from urllib.parse import urljoin, urlparse

from app.brands.base import BaseBrandCrawler
from app.core.csv_schema import make_product_row, today_yymmdd

UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/131.0.0.0"}


def site_base(url: str) -> str:
    parsed = urlparse(url)
    return f"{parsed.scheme}://{parsed.netloc}"


def parse_prices(block: str) -> tuple[str, str]:
    strike = re.search(r"<strike[^>]*>([\d,]+)</strike>", block, re.I)
    amounts = re.findall(r"([\d,]+)", block)
    if strike:
        regular = strike.group(1).replace(",", "")
        others = [a.replace(",", "") for a in amounts if a.replace(",", "") != regular]
        current = others[-1] if others else ""
        return regular, current
    if amounts:
        val = amounts[-1].replace(",", "")
        return val, ""
    return "", ""


def parse_products(html: str, base: str) -> list[dict]:
    products: list[dict] = []
    seen: set[str] = set()
    pattern = re.compile(
        r'<figure class="product-image--holder">\s*'
        r'<img[^>]+src="([^"]+)"[^>]*>.*?'
        r'href="(/shop/shopdetail\.html\?branduid=\d+[^"]*)".*?'
        r'class="product-title"[^>]*>\s*<a[^>]*>([^<]+)</a>.*?'
        r'class="new-price"(.*?)</span>',
        re.S | re.I,
    )
    for img, href_path, title, price_block in pattern.findall(html):
        href = urljoin(base, href_path)
        uid_m = re.search(r"branduid=(\d+)", href)
        uid = uid_m.group(1) if uid_m else href
        if uid in seen:
            continue
        seen.add(uid)
        name = re.sub(r"\s+", " ", title).strip()
        thumb = urljoin(base, img)
        regular, current = parse_prices(price_block)
        products.append(
            {"name": name, "href": href, "thumb": thumb, "regular": regular, "current": current}
        )
    return products


class MakeshopCrawler(BaseBrandCrawler):
    brand_id = "makeshop"
    brand_name = "MAKESHOP"
    source_site = "makeshop.co.kr"

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
            raise ValueError("MakeShop URL이 필요합니다.")
        base = site_base(url)
        label = brand_name or "MAKESHOP"
        crawled_at = today_yymmdd()
        req = urllib.request.Request(url, headers=UA)
        html = urllib.request.urlopen(req, timeout=60).read().decode("utf-8", "ignore")
        raw = parse_products(html, base)
        products: list[dict] = []
        for item in raw:
            if not item.get("name"):
                continue
            products.append(
                make_product_row(
                    brand=label,
                    platform="",
                    product_name=item["name"],
                    category=category_name or "",
                    regular_price=item["regular"],
                    current_price=item["current"],
                    thumbnail=item["thumb"],
                    product_detail_url=item["href"],
                    crawled_at=crawled_at,
                )
            )
        if on_progress:
            on_progress(len(products), 1)
        if not products:
            raise RuntimeError(f"MakeShop 상품을 수집하지 못했습니다: {url}")
        return products
