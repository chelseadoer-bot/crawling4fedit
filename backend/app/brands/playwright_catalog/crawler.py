"""공통 Playwright 카탈로그 크롤러 (H&M, COS, 럭셔리 등)"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from typing import Any
from urllib.parse import parse_qs, urljoin, urlparse

from playwright.sync_api import sync_playwright

from app.brands.base import BaseBrandCrawler
from app.brands.browser_utils import dismiss_popups, launch_browser, new_stealth_context
from app.core.csv_schema import empty_row, now_timestamp


@dataclass(frozen=True)
class SiteProfile:
    brand_id: str
    brand_name: str
    source_site: str
    default_url: str
    api_patterns: tuple[str, ...]
    product_href_patterns: tuple[str, ...]
    scroll_rounds: int = 15


SITE_PROFILES: dict[str, SiteProfile] = {
    "hm": SiteProfile(
        brand_id="hm",
        brand_name="H&M",
        source_site="hm.com",
        default_url="https://www2.hm.com/ko_kr/ladies/shop-by-product/view-all.html",
        api_patterns=("search-services", "hmwebservices", "listing/resultpage"),
        product_href_patterns=("/productpage.", "/product/"),
    ),
    "cos": SiteProfile(
        brand_id="cos",
        brand_name="COS",
        source_site="cos.com",
        default_url="https://www.cos.com/ko-kr/search?q=",
        api_patterns=("/proxy/", "/api/", "search", "products", "catalog"),
        product_href_patterns=("/product/", "/products/", "/ko-kr/"),
    ),
    "balenciaga": SiteProfile(
        brand_id="balenciaga",
        brand_name="BALENCIAGA",
        source_site="balenciaga.com",
        default_url="https://www.balenciaga.com/ko-kr/women",
        api_patterns=("Search-", "Product-", "/api/", "search", "products"),
        product_href_patterns=("/products/", "/product/"),
        scroll_rounds=20,
    ),
    "chanel": SiteProfile(
        brand_id="chanel",
        brand_name="CHANEL",
        source_site="chanel.com",
        default_url="https://www.chanel.com/kr/fashion/pret-a-porter/",
        api_patterns=("/api/", "search", "products", "catalog", "graphql"),
        product_href_patterns=("/fashion/p/", "/fashion/products/", "/products/"),
        scroll_rounds=20,
    ),
    "moncler": SiteProfile(
        brand_id="moncler",
        brand_name="MONCLER",
        source_site="moncler.com",
        default_url="https://www.moncler.com/ko-kr/women/ready-to-wear",
        api_patterns=("SearchApi-Search",),
        product_href_patterns=(".html", "/ready-to-wear/"),
        scroll_rounds=20,
    ),
    "zara-home": SiteProfile(
        brand_id="zara",
        brand_name="ZARA",
        source_site="zara.com",
        default_url="https://www.zara.com/kr/ko/woman-new-in-l1180.html",
        api_patterns=("products", "search", "catalog"),
        product_href_patterns=("-p", "/product/"),
    ),
}


def strip_html(text: str) -> str:
    return re.sub(r"<[^>]+>", "", text or "").strip()


def first_str(*values: Any) -> str:
    for v in values:
        if v is None:
            continue
        if isinstance(v, (int, float)):
            return str(v)
        if isinstance(v, str) and v.strip():
            return v.strip()
    return ""


def normalize_price(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, (int, float)):
        return str(int(value)) if float(value).is_integer() else str(value)
    if isinstance(value, dict):
        for k in ("value", "amount", "formatted", "price", "current"):
            if value.get(k):
                return normalize_price(value[k])
        return ""
    text = strip_html(str(value))
    digits = re.sub(r"[^\d]", "", text)
    return digits or text


def normalize_image(value: Any, base: str = "") -> str:
    if isinstance(value, list) and value:
        return normalize_image(value[0], base)
    if isinstance(value, dict):
        for k in ("url", "src", "image", "imageUrl", "uri", "path"):
            if value.get(k):
                return normalize_image(value[k], base)
        return ""
    url = str(value or "")
    if not url:
        return ""
    if url.startswith("//"):
        return "https:" + url
    if url.startswith("/"):
        return urljoin(base, url)
    return url


def walk_product_dicts(node: Any, out: list[dict]) -> None:
    if isinstance(node, dict):
        keys = set(node.keys())
        name_keys = {"productName", "product_name", "name", "title", "displayName"}
        if keys & name_keys:
            out.append(node)
        for v in node.values():
            walk_product_dicts(v, out)
    elif isinstance(node, list):
        for item in node:
            walk_product_dicts(item, out)


def parse_product_dict(prod: dict, profile: SiteProfile, crawled_at: str, page_url: str) -> dict | None:
    name = first_str(
        prod.get("productName"),
        prod.get("product_name"),
        prod.get("name"),
        prod.get("title"),
        prod.get("displayName"),
    )
    if not name:
        return None

    pid = first_str(
        prod.get("productId"),
        prod.get("product_no"),
        prod.get("productNo"),
        prod.get("articleCode"),
        prod.get("code"),
        prod.get("sku"),
        prod.get("id"),
    )
    price = normalize_price(
        prod.get("price")
        or prod.get("salePrice")
        or prod.get("product_price")
        or prod.get("formattedPrice")
        or prod.get("priceValue")
    )
    image = normalize_image(
        prod.get("image")
        or prod.get("imageUrl")
        or prod.get("image_url")
        or prod.get("image_big")
        or prod.get("thumbnail")
        or prod.get("images"),
        base=f"https://www.{profile.source_site}",
    )
    url = first_str(prod.get("url"), prod.get("productUrl"), prod.get("link"))
    if url and not url.startswith("http"):
        url = urljoin(page_url, url)

    color = first_str(prod.get("color"), prod.get("colour"), prod.get("subtitle"))

    row = empty_row()
    row.update(
        {
            "brand": profile.brand_name,
            "product_id": pid,
            "product_name": strip_html(name),
            "category_large": "",
            "category_small": "",
            "price_original": price,
            "price_sale": "",
            "discount_rate": "",
            "color": color,
            "sizes_available": "",
            "stock_status": "unknown",
            "product_url": url,
            "image_url": image,
            "crawled_at": crawled_at,
            "source_site": profile.source_site,
        }
    )
    return row


def extract_from_dom(page, profile: SiteProfile, crawled_at: str) -> list[dict]:
    href_patterns = profile.product_href_patterns
    js = """
    (patterns) => {
      const anchors = Array.from(document.querySelectorAll('a[href]'));
      const out = [];
      const seen = new Set();
      for (const a of anchors) {
        const href = a.href || '';
        if (!patterns.some(p => href.includes(p))) continue;
        if (seen.has(href)) continue;
        seen.add(href);
        const img = a.querySelector('img');
        const imgSrc = img?.src || img?.dataset?.src || img?.getAttribute('data-src') || '';
        const texts = Array.from(a.querySelectorAll('span,p,h2,h3,div')).map(el => el.innerText.trim()).filter(Boolean);
        const name = texts.find(t => t.length > 2 && !/₩|원|KRW|\\d{1,3}(,\\d{3})+/.test(t)) || a.getAttribute('aria-label') || a.title || '';
        const priceText = texts.find(t => /₩|원|KRW|\\d{1,3}(,\\d{3})+/.test(t)) || '';
        if (!name) continue;
        out.push({ href, img: imgSrc, name, price: priceText.replace(/[^0-9]/g, '') });
      }
      return out;
    }
    """
    raw = page.evaluate(js, list(href_patterns))
    products = []
    seen = set()
    for item in raw:
        key = item.get("href", "")
        if not key or key in seen:
            continue
        seen.add(key)
        row = empty_row()
        row.update(
            {
                "brand": profile.brand_name,
                "product_id": re.search(r"(\d{5,})", key).group(1) if re.search(r"(\d{5,})", key) else "",
                "product_name": item.get("name", ""),
                "category_large": "",
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
                "source_site": profile.source_site,
            }
        )
        products.append(row)
    return products


class PlaywrightSiteCrawler(BaseBrandCrawler):
    """설정 기반 Playwright 크롤러"""

    def __init__(self, profile: SiteProfile):
        self.profile = profile
        self.brand_id = profile.brand_id
        self.brand_name = profile.brand_name
        self.source_site = profile.source_site

    def crawl(
        self,
        url: str | None = None,
        headless: bool = False,
        on_progress=None,
    ) -> list[dict]:
        target_url = url or self.profile.default_url
        crawled_at = now_timestamp()
        profile = self.profile
        captured: list[dict] = []
        api_products: list[dict] = []

        with sync_playwright() as p:
            browser = launch_browser(p, headless=headless)
            context, page = new_stealth_context(browser)

            def on_response(response):
                u = response.url
                if response.status != 200:
                    return
                if not any(pat in u for pat in profile.api_patterns):
                    return
                ct = response.headers.get("content-type", "")
                if "json" not in ct and "javascript" not in ct:
                    return
                try:
                    captured.append(response.json())
                except Exception:
                    pass

            page.on("response", on_response)
            page.goto(target_url, wait_until="domcontentloaded", timeout=120000)
            dismiss_popups(page)
            page.wait_for_timeout(3000)

            title = page.title().lower()
            body_snip = ""
            try:
                body_snip = page.locator("body").inner_text(timeout=3000)[:300].lower()
            except Exception:
                pass
            if "access denied" in title or "unavailable" in title or "access denied" in body_snip:
                browser.close()
                raise RuntimeError(
                    f"{profile.brand_name} 사이트 접근이 차단되었습니다. "
                    "브라우저 창에서 직접 접속·확인 후 다시 시도해주세요."
                )

            for i in range(profile.scroll_rounds):
                page.evaluate("window.scrollBy(0, window.innerHeight * 0.85)")
                page.wait_for_timeout(900)
                if on_progress and i % 3 == 0:
                    on_progress(len(api_products), i + 1)

            for payload in captured:
                candidates: list[dict] = []
                walk_product_dicts(payload, candidates)
                for prod in candidates:
                    row = parse_product_dict(prod, profile, crawled_at, target_url)
                    if row:
                        api_products.append(row)

            products = api_products
            if not products:
                products = extract_from_dom(page, profile, crawled_at)

            browser.close()

        deduped: list[dict] = []
        seen = set()
        for row in products:
            key = row.get("product_id") or row.get("product_url") or row.get("product_name")
            if key in seen:
                continue
            seen.add(key)
            deduped.append(row)

        if not deduped:
            raise RuntimeError(
                f"{profile.brand_name} 상품을 수집하지 못했습니다. "
                "봇 차단 또는 페이지 구조 변경 가능성이 있습니다."
            )
        return deduped


def make_crawler(site_key: str) -> PlaywrightSiteCrawler:
    profile = SITE_PROFILES[site_key]
    return PlaywrightSiteCrawler(profile)


class HmCrawler(BaseBrandCrawler):
    brand_id = "hm"
    brand_name = "H&M"
    source_site = "hm.com"

    def crawl(self, url: str | None = None, headless: bool = False, on_progress=None) -> list[dict]:
        return make_crawler("hm").crawl(url=url, headless=headless, on_progress=on_progress)


class CosCrawler(BaseBrandCrawler):
    brand_id = "cos"
    brand_name = "COS"
    source_site = "cos.com"

    def crawl(self, url: str | None = None, headless: bool = False, on_progress=None) -> list[dict]:
        return make_crawler("cos").crawl(url=url, headless=headless, on_progress=on_progress)


class ChanelCrawler(BaseBrandCrawler):
    brand_id = "chanel"
    brand_name = "CHANEL"
    source_site = "chanel.com"

    def crawl(self, url: str | None = None, headless: bool = False, on_progress=None) -> list[dict]:
        return make_crawler("chanel").crawl(url=url, headless=headless, on_progress=on_progress)


class MonclerCrawler(BaseBrandCrawler):
    brand_id = "moncler"
    brand_name = "MONCLER"
    source_site = "moncler.com"

    def crawl(self, url: str | None = None, headless: bool = False, on_progress=None) -> list[dict]:
        return make_crawler("moncler").crawl(url=url, headless=headless, on_progress=on_progress)
