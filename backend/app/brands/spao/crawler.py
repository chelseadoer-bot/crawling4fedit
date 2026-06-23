"""SPAO 크롤러 (공개 API)"""

from __future__ import annotations

import json
import time
import urllib.parse
import urllib.request
from urllib.parse import parse_qs, urlparse

from app.brands.base import BaseBrandCrawler
from app.core.csv_schema import make_product_row, today_yymmdd

BASE = "https://www.spao.com"
IMAGE_CDN = "https://static.elandrs.com/spao"
PAGE_SIZE = 100
DEFAULT_VENDOR = "LV26000002"


def parse_disp_category_no(url: str) -> str:
    params = parse_qs(urlparse(url).query)
    cat = params.get("dispCategoryNo", [""])[0]
    if not cat:
        raise ValueError(f"SPAO dispCategoryNo를 찾을 수 없습니다: {url}")
    return cat


def parse_exhibition_no(url: str) -> str:
    params = parse_qs(urlparse(url).query)
    ex = params.get("exhibitionNo", [""])[0]
    if not ex:
        raise ValueError(f"SPAO exhibitionNo를 찾을 수 없습니다: {url}")
    return ex


def is_planshop_url(url: str) -> bool:
    path = urlparse(url).path
    return "/p/planshop" in path or "exhibitionNo" in urlparse(url).query


def is_new_url(url: str) -> bool:
    return "/u/new" in urlparse(url).path


def api_get(url: str) -> dict:
    req = urllib.request.Request(
        url,
        headers={"User-Agent": "Mozilla/5.0", "Referer": f"{BASE}/"},
    )
    with urllib.request.urlopen(req, timeout=60) as resp:
        payload = json.loads(resp.read().decode())
    if payload.get("resultCode") not in ("200", 200, "SUCCESS"):
        raise RuntimeError(payload.get("resultMessage") or "SPAO API 오류")
    return payload


def image_url(path: str) -> str:
    if not path:
        return ""
    if path.startswith("http"):
        return path
    return f"{IMAGE_CDN}/{path.lstrip('/')}"


def product_link(item: dict) -> str:
    item_no = item.get("itemNo") or ""
    vendor = item.get("lowerVendNo") or DEFAULT_VENDOR
    return f"{BASE}/i/item?itemNo={item_no}&lowerVendNo={vendor}"


def parse_item(item: dict, crawled_at: str) -> dict | None:
    name = (item.get("itemName") or "").strip()
    if not name or not item.get("itemNo"):
        return None
    price = item.get("finalDcPrice") or item.get("sellprice") or item.get("orgSellprice") or ""
    regular = item.get("orgSellprice") or price
    thumb = image_url(item.get("representImagePath") or "")
    if not thumb and isinstance(item.get("image"), list) and item["image"]:
        thumb = image_url(item["image"][0].get("imagePath") or "")
    return make_product_row(
        brand=item.get("brandName") or "SPAO",
        platform="www.spao.com",
        product_name=name,
        gender="women",
        regular_price=str(regular),
        current_price=str(price),
        thumbnail=thumb,
        rating=str(item.get("reviewScore") or ""),
        reviews=str(item.get("reviewCount") or ""),
        product_detail_url=product_link(item),
        crawled_at=crawled_at,
    )


def crawl_planshop(exhibition_no: str, crawled_at: str, on_progress=None) -> list[dict]:
    """기획전(/p/planshop?exhibitionNo=) 상품 수집."""
    products: list[dict] = []
    seen: set[str] = set()
    section_sn = 0
    page_size = 100

    while section_sn < 20:
        item_start = 1
        section_had_items = False
        while item_start <= 500:
            query = urllib.parse.urlencode(
                {
                    "exhibitionNo": exhibition_no,
                    "previewYn": "N",
                    "exhibitionSectionSn": section_sn,
                    "itemStart": item_start,
                    "itemSize": page_size,
                }
            )
            data = api_get(f"{BASE}/v1/auto/exhibition/section/item/api?{query}")
            sections = (data.get("data") or {}).get("exhibitionSection") or []
            if not sections:
                break

            batch: list[dict] = []
            for section in sections:
                batch.extend(section.get("item") or [])

            if not batch:
                break

            section_had_items = True
            for item in batch:
                row = parse_item(item, crawled_at)
                if not row:
                    continue
                key = row.get("product_detail_url") or ""
                if key in seen:
                    continue
                seen.add(key)
                products.append(row)

            if on_progress:
                on_progress(len(products), section_sn + 1)

            total = int(sections[0].get("total") or len(batch))
            if item_start + page_size > total or len(batch) < page_size:
                break
            item_start += page_size
            time.sleep(0.1)

        if not section_had_items:
            break
        section_sn += 1

    return products


def crawl_new(category_no: str, crawled_at: str, on_progress=None) -> list[dict]:
    url = f"{BASE}/api/item/new?size=1000&dispCategoryNo={category_no}"
    data = api_get(url)
    batch = data.get("data") or []
    if not isinstance(batch, list):
        return []
    products: list[dict] = []
    seen: set[str] = set()
    for item in batch:
        row = parse_item(item, crawled_at)
        if not row:
            continue
        key = row.get("product_detail_url") or ""
        if key in seen:
            continue
        seen.add(key)
        products.append(row)
    if on_progress:
        on_progress(len(products), 1)
    return products


def crawl_category(category_no: str, crawled_at: str, on_progress=None) -> list[dict]:
    products: list[dict] = []
    seen: set[str] = set()
    page = 1
    total_pages = 1
    while page <= total_pages:
        query = urllib.parse.urlencode(
            {
                "dispMctgNo": category_no,
                "aggSize": 200,
                "aggColor": 200,
                "aggPrice": 200,
                "aggFit": 200,
                "aggGender": 200,
                "page": page,
                "size": 20,
                "infinity": "true",
            }
        )
        data = api_get(f"{BASE}/v1/search/leaf/cate/item/api?{query}")
        item_block = (data.get("data") or {}).get("srchOutCome", {}).get("item", {})
        total = int(item_block.get("total") or 0)
        batch = item_block.get("list") or []
        if total:
            total_pages = max(total_pages, (total + 19) // 20)
        if not batch:
            break
        for item in batch:
            row = parse_item(item, crawled_at)
            if not row:
                continue
            key = row.get("product_detail_url") or ""
            if key in seen:
                continue
            seen.add(key)
            products.append(row)
        if on_progress:
            on_progress(len(products), page)
        if len(batch) < 20:
            break
        page += 1
        time.sleep(0.1)
    return products


class SpaoCrawler(BaseBrandCrawler):
    brand_id = "spao"
    brand_name = "SPAO"
    source_site = "spao.com"

    def crawl(
        self,
        url: str | None = None,
        headless: bool = True,
        on_progress=None,
        **_kwargs,
    ) -> list[dict]:
        if not url:
            raise ValueError("URL이 필요합니다.")
        crawled_at = today_yymmdd()
        if is_planshop_url(url):
            exhibition_no = parse_exhibition_no(url)
            products = crawl_planshop(exhibition_no, crawled_at, on_progress)
        else:
            category_no = parse_disp_category_no(url)
            if is_new_url(url):
                products = crawl_new(category_no, crawled_at, on_progress)
            else:
                products = crawl_category(category_no, crawled_at, on_progress)
        if not products:
            raise RuntimeError(f"SPAO 상품을 수집하지 못했습니다: {url}")
        return products
