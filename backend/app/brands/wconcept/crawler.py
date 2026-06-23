"""W컨셉 카테고리 크롤러 (display API)"""

from __future__ import annotations

import json
import os
import re
import time
import urllib.error
import urllib.request
from urllib.parse import urlparse

from playwright.sync_api import sync_playwright

from app.brands.base import BaseBrandCrawler
from app.brands.browser_utils import launch_browser, new_stealth_context
from app.core.csv_schema import make_product_row, today_yymmdd

API_BASE = "https://api-display.wconcept.co.kr/display/api/v2/category/products"
MODULE_ID = "M33439436"
DEFAULT_API_KEY = "VWmkUPgs6g2fviPZ5JQFQ3pERP4tIXv/J2jppLqSRBk="
PAGE_SIZE = 60
MAX_PAGES = int(os.environ.get("WCONCEPT_MAX_PAGES", "30"))
PRODUCT_BASE = "https://www.wconcept.co.kr"

_api_key_cache: str | None = None


def parse_category(url: str) -> tuple[str, str]:
    """URL에서 카테고리 코드와 API path(001/001) 추출."""
    path = urlparse(url).path.strip("/")
    match = re.search(r"/?(\d{6})\s*$", path) or re.search(r"(\d{6})", path)
    if not match:
        raise ValueError(f"W컨셉 카테고리 코드를 찾을 수 없습니다: {url}")
    code = match.group(1)
    return code, f"{code[:3]}/{code[3:]}"


def resolve_api_key() -> str:
    global _api_key_cache
    if _api_key_cache:
        return _api_key_cache

    captured: list[str] = []

    with sync_playwright() as p:
        browser = launch_browser(p, headless=True)
        _, page = new_stealth_context(browser)

        def on_request(request):
            key = request.headers.get("display-api-key")
            if key:
                captured.append(key)

        page.on("request", on_request)
        page.goto(
            "https://display.wconcept.co.kr/category/women/001001",
            wait_until="domcontentloaded",
            timeout=90000,
        )
        page.wait_for_timeout(4000)
        browser.close()

    _api_key_cache = captured[0] if captured else DEFAULT_API_KEY
    return _api_key_cache


def fetch_product_page(api_path: str, page_no: int, api_key: str, referer: str) -> dict:
    body = json.dumps(
        {
            "custNo": "",
            "gender": "All",
            "sort": "WCK",
            "pageNo": page_no,
            "pageSize": PAGE_SIZE,
            "bcds": [],
            "colors": [],
            "benefits": [],
            "discounts": [],
            "status": ["01"],
            "shopCds": [],
            "domainType": "pc",
        }
    ).encode()
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/131.0.0.0",
        "Accept": "application/json, text/plain, */*",
        "Referer": referer,
        "display-api-key": api_key,
        "devicetype": "PC",
        "agegroup": "10",
        "gendertype": "all",
        "cust_no": "",
        "wck-cust-birthdate": "",
        "Content-Type": "application/json; charset=UTF-8",
    }
    url = f"{API_BASE}/{MODULE_ID}/{api_path}"
    req = urllib.request.Request(url, data=body, headers=headers, method="POST")
    with urllib.request.urlopen(req, timeout=60) as resp:
        payload = json.loads(resp.read().decode())
    if payload.get("result") != "SUCCESS":
        raise RuntimeError(payload.get("message") or "W컨셉 API 오류")
    return payload["data"]["productList"]


def product_url(item: dict) -> str:
    href = item.get("webViewUrl") or item.get("newTargetUrl") or ""
    if not href:
        return f"{PRODUCT_BASE}/Product/{item.get('itemCd', '')}"
    if href.startswith("http"):
        return href
    return f"{PRODUCT_BASE}{href}"


def parse_item(item: dict, crawled_at: str) -> dict | None:
    name = (item.get("itemName") or "").strip()
    if not name:
        return None
    price = item.get("finalPrice") or item.get("salePrice") or item.get("customerPrice") or ""
    regular = item.get("customerPrice") or item.get("salePrice") or price
    return make_product_row(
        brand=item.get("brandNameKr") or item.get("brandNameEn") or "WCONCEPT",
        platform="display.wconcept.co.kr",
        product_name=name,
        gender="women",
        regular_price=str(int(regular)) if regular else "",
        current_price=str(int(price)) if price else "",
        thumbnail=item.get("imageUrlMobile") or "",
        rating=str(item.get("reviewScore") or ""),
        reviews=str(item.get("reviewCnt") or ""),
        likes=str(item.get("heartCnt") or ""),
        product_detail_url=product_url(item),
        crawled_at=crawled_at,
    )


class WconceptCrawler(BaseBrandCrawler):
    brand_id = "wconcept"
    brand_name = "WCONCEPT"
    source_site = "display.wconcept.co.kr"

    def crawl(
        self,
        url: str | None = None,
        headless: bool = True,
        on_progress=None,
        **_kwargs,
    ) -> list[dict]:
        if not url:
            raise ValueError("URL이 필요합니다.")

        _, api_path = parse_category(url)
        referer = url if url.startswith("http") else f"https://display.wconcept.co.kr/{url}"
        api_key = resolve_api_key()
        crawled_at = today_yymmdd()
        products: list[dict] = []
        seen: set[str] = set()
        page_no = 1
        total_pages = min(int(os.environ.get("WCONCEPT_MAX_PAGES", str(MAX_PAGES))), MAX_PAGES)

        while page_no <= total_pages:
            try:
                listing = fetch_product_page(api_path, page_no, api_key, referer)
            except urllib.error.HTTPError as exc:
                if exc.code in (401, 403) and api_key == DEFAULT_API_KEY:
                    global _api_key_cache
                    _api_key_cache = None
                    api_key = resolve_api_key()
                    listing = fetch_product_page(api_path, page_no, api_key, referer)
                else:
                    raise

            total_pages = min(int(listing.get("totalPages") or 1), MAX_PAGES)
            batch = listing.get("content") or []
            if not batch:
                break

            for item in batch:
                row = parse_item(item, crawled_at)
                if not row:
                    continue
                key = row.get("product_detail_url") or row.get("product_name")
                if key in seen:
                    continue
                seen.add(key)
                products.append(row)

            if on_progress:
                on_progress(len(products), page_no)
            if page_no >= total_pages:
                break
            page_no += 1
            time.sleep(0.15)

        if not products:
            raise RuntimeError(f"W컨셉 상품을 수집하지 못했습니다: {url}")
        return products
