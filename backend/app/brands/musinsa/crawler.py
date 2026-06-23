"""무신사 카테고리 PLP 크롤러"""

from __future__ import annotations

import json
import re
import time
from urllib.parse import parse_qs, urlparse

from playwright.sync_api import sync_playwright

from app.brands.base import BaseBrandCrawler
from app.brands.browser_utils import dismiss_popups, launch_browser, new_stealth_context
from app.core.csv_schema import make_product_row, today_yymmdd

SCROLL_ROUNDS = 20


def parse_brand_slug(url: str) -> str | None:
    m = re.search(r"/brand/([^/]+)/products", urlparse(url).path)
    return m.group(1) if m else None


def parse_category_code(url: str) -> str | None:
    path = urlparse(url).path.strip("/")
    m = re.search(r"category/(\d+)", path)
    if m:
        return m.group(1)
    return None


def parse_gf(url: str) -> str:
    return parse_qs(urlparse(url).query).get("gf", ["F"])[0]


def walk_products(node, out: list[dict]) -> None:
    if isinstance(node, dict):
        if {"goodsName", "goodsNo"} <= set(node.keys()) or {"productName", "goodsNo"} <= set(node.keys()):
            out.append(node)
        for v in node.values():
            walk_products(v, out)
    elif isinstance(node, list):
        for item in node:
            walk_products(item, out)


def dict_to_row(prod: dict, crawled_at: str) -> dict | None:
    name = (prod.get("goodsName") or prod.get("productName") or prod.get("goods_name") or "").strip()
    if not name:
        return None
    goods_no = str(prod.get("goodsNo") or prod.get("goods_no") or "")
    price = str(
        prod.get("price")
        or prod.get("normalPrice")
        or prod.get("salePrice")
        or prod.get("goodsPrice")
        or ""
    )
    price_digits = re.sub(r"[^\d]", "", price) or price
    image = prod.get("imageUrl") or prod.get("thumbnail") or prod.get("goodsImage") or ""
    if image and not str(image).startswith("http"):
        image = "https:" + image if str(image).startswith("//") else image
    link = prod.get("goodsLinkUrl") or prod.get("linkUrl") or prod.get("goodsLink") or ""
    if not link and goods_no:
        link = f"https://www.musinsa.com/products/{goods_no}"
    brand = prod.get("brandName") or prod.get("brand") or "MUSINSA"
    return make_product_row(
        brand=str(brand),
        platform="musinsa.com",
        product_name=name,
        regular_price=price_digits,
        current_price=price_digits,
        thumbnail=str(image),
        product_detail_url=str(link),
        crawled_at=crawled_at,
    )


def extract_dom_products(page, crawled_at: str) -> list[dict]:
    raw = page.evaluate(
        """() => {
        const cards = document.querySelectorAll('[data-item-id], a[href*="/products/"]');
        const out = [];
        const seen = new Set();
        for (const el of cards) {
            const a = el.closest('a[href*="/products/"]') || (el.matches('a[href*="/products/"]') ? el : null);
            if (!a) continue;
            const href = a.href;
            if (seen.has(href)) continue;
            seen.add(href);
            const name = a.querySelector('[class*="name"], [class*="title"], p, span')?.innerText?.trim()
                || a.getAttribute('aria-label') || a.title || '';
            const img = a.querySelector('img')?.currentSrc || a.querySelector('img')?.src || '';
            const price = a.innerText.match(/[\\d,]+원/)?.[0] || '';
            if (name) out.push({ name, href, img, price });
        }
        return out;
    }"""
    )
    rows = []
    for item in raw:
        price = re.sub(r"[^\d]", "", item.get("price", ""))
        rows.append(
            make_product_row(
                brand="MUSINSA",
                platform="musinsa.com",
                product_name=item["name"],
                regular_price=price,
                current_price=price,
                thumbnail=item.get("img", ""),
                product_detail_url=item.get("href", ""),
                crawled_at=crawled_at,
            )
        )
    return rows


class MusinsaCrawler(BaseBrandCrawler):
    brand_id = "musinsa"
    brand_name = "MUSINSA"
    source_site = "musinsa.com"

    def crawl(
        self,
        url: str | None = None,
        headless: bool = True,
        on_progress=None,
        brand_name: str | None = None,
        **_,
    ) -> list[dict]:
        target = url or "https://www.musinsa.com/category/001/goods?gf=F"
        brand_slug = parse_brand_slug(target)
        category = parse_category_code(target)
        gf = parse_gf(target)
        default_brand = brand_name or ("MUSINSA STANDARD" if brand_slug == "musinsastandard" else "MUSINSA")

        if brand_slug:
            if "?" not in target:
                target = f"{target}?gf={gf}"
        elif category:
            if "/goods" not in urlparse(target).path:
                target = f"https://www.musinsa.com/category/{category}/goods?gf={gf}"
        else:
            raise ValueError(f"무신사 카테고리/브랜드 URL이 아닙니다: {target}")

        crawled_at = today_yymmdd()
        captured: list[dict] = []
        seen: set[str] = set()
        products: list[dict] = []

        with sync_playwright() as p:
            browser = launch_browser(p, headless=headless)
            _, page = new_stealth_context(browser)

            def on_response(response):
                if response.status != 200:
                    return
                u = response.url
                if "musinsa" not in u:
                    return
                if not any(k in u for k in ("goods", "product", "plp", "listing", "category", "brand")):
                    return
                try:
                    body = response.json()
                except Exception:
                    return
                found: list[dict] = []
                walk_products(body, found)
                captured.extend(found)

            page.on("response", on_response)
            page.goto(target, wait_until="domcontentloaded", timeout=120000)
            dismiss_popups(page)
            page.wait_for_timeout(3000)

            for i in range(SCROLL_ROUNDS):
                page.evaluate("window.scrollBy(0, window.innerHeight * 0.9)")
                page.wait_for_timeout(900)
                for prod in captured:
                    row = dict_to_row(prod, crawled_at)
                    if row:
                        row["brand"] = default_brand
                    if not row:
                        continue
                    key = row.get("product_detail_url") or row.get("product_name")
                    if key in seen:
                        continue
                    seen.add(key)
                    products.append(row)
                captured.clear()
                if on_progress:
                    on_progress(len(products), i + 1)

            if len(products) < 5:
                for row in extract_dom_products(page, crawled_at):
                    row["brand"] = default_brand
                    key = row.get("product_detail_url") or row.get("product_name")
                    if key in seen:
                        continue
                    seen.add(key)
                    products.append(row)

            browser.close()

        if not products:
            raise RuntimeError("무신사 상품을 수집하지 못했습니다.")
        return products
