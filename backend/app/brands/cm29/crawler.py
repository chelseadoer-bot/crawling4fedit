"""29CM 브랜드 크롤러"""

import json
import re
import time
import urllib.error
import urllib.request
from urllib.parse import parse_qs, urlparse

from app.brands.base import BaseBrandCrawler
from app.core.csv_schema import make_product_row, today_yymmdd

LISTING_API = "https://display-bff-api.29cm.co.kr/api/v1/listing/items?colorchipVariant=control"
PAGE_SIZE = 50
REQUEST_DELAY_SEC = 0.3

# 베스트(랭킹) API — /store/best-items 페이지
BEST_API = "https://recommend-api.29cm.co.kr/api/v4/best/items"
BEST_LIMIT = 100
IMG_BASE = "https://img.29cm.co.kr"


def parse_category_from_url(url: str) -> tuple[int | None, int | None]:
    parsed = urlparse(url)
    params = parse_qs(parsed.query)
    large = params.get("categoryLargeCode", [None])[0]
    medium = params.get("categoryMediumCode", [None])[0]
    return (int(large) if large else None, int(medium) if medium else None)


def extract_color_from_name(name: str) -> str:
    match = re.search(r"\s[-–]\s([^-]+)$", name)
    return match.group(1).strip() if match else ""


def fetch_page(large_id: int, medium_id: int | None, page: int) -> dict:
    facets: dict = {"categoryFacetInputs": [{"largeId": large_id}]}
    if medium_id:
        facets["categoryFacetInputs"][0]["middleId"] = medium_id

    payload = {
        "pageType": "CATEGORY_PLP",
        "sortType": "RECOMMENDED",
        "facets": facets,
        "pageRequest": {"page": page, "size": PAGE_SIZE},
    }
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        LISTING_API,
        data=data,
        headers={"Content-Type": "application/json", "User-Agent": "Mozilla/5.0"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=60) as resp:
        return json.loads(resp.read())


def item_to_row(item: dict, crawled_at: str) -> dict:
    info = item.get("itemInfo") or {}
    event = (item.get("itemEvent") or {}).get("eventProperties") or {}
    url_obj = item.get("itemUrl") or {}

    name = info.get("productName") or event.get("itemName") or ""
    price = str(info.get("displayPrice") or event.get("price") or "")
    brand = info.get("brandName") or event.get("brandName") or "29CM"
    image = info.get("thumbnailUrl") or ""
    product_url = url_obj.get("webLink") or ""

    color = extract_color_from_name(name)
    if not color and info.get("colorName"):
        color = info.get("colorName")

    category = event.get("largeCategoryName") or event.get("middleCategoryName") or ""

    return make_product_row(
        platform="29cm",
        brand=brand,
        main_category=event.get("largeCategoryName") or "",
        category=event.get("middleCategoryName") or category,
        product_name=name,
        regular_price=price,
        current_price=price,
        discount_rate=str(info.get("saleRate") or event.get("discountRate") or ""),
        color=color,
        thumbnail=image,
        product_detail_url=product_url,
        crawled_at=crawled_at,
    )


def is_best_url(url: str) -> bool:
    return "best-items" in urlparse(url).path


# ── 베스트(랭킹) /best-products — 성별·연령 세그먼트 실시간 인기 ──────────────
BEST_PRODUCTS_API = "https://display-bff-api.29cm.co.kr/api/v1/plp/best/items"
BEST_PRODUCTS_SIZE = 100
_AGE_SEGMENT = {"10": "TEENS", "20": "TWENTIES", "30": "THIRTIES", "40": "FORTIES", "50": "FIFTIES"}


def is_best_products_url(url: str) -> bool:
    return "best-products" in urlparse(url).path


def fetch_best_products_page(params: dict, page: int) -> dict:
    payload = {
        "pageRequest": {"page": page, "size": BEST_PRODUCTS_SIZE},
        "userSegment": {"gender": params.get("gender", "F"), "age": params.get("age", "THIRTIES")},
        "facets": {
            "periodFacetInput": {"type": params.get("period", "HOURLY"), "order": "DESC"},
            "rankingFacetInput": {"type": params.get("ranking", "POPULARITY")},
        },
    }
    req = urllib.request.Request(
        BEST_PRODUCTS_API,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json", "User-Agent": "Mozilla/5.0",
                 "Referer": "https://www.29cm.co.kr/"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=60) as resp:
        return json.loads(resp.read())


def best_products_item_to_row(item: dict, crawled_at: str, rank: int) -> dict | None:
    info = item.get("itemInfo") or {}
    event = (item.get("itemEvent") or {}).get("eventProperties") or {}
    name = (info.get("productName") or event.get("itemName") or "").strip()
    if not name:
        return None
    return make_product_row(
        platform="29cm",
        is_ranking="true",
        rank=str(rank),
        brand=info.get("brandName") or event.get("brandName") or "",
        main_category=event.get("largeCategoryName") or "",
        category=event.get("middleCategoryName") or "",
        product_name=name,
        regular_price=str(info.get("originalPrice") or ""),
        current_price=str(info.get("displayPrice") or ""),
        discount_rate=str(info.get("saleRate") or ""),
        rating=str(info.get("reviewScore") or ""),
        reviews=str(info.get("reviewCount") or ""),
        thumbnail=info.get("thumbnailUrl") or "",
        product_detail_url=(item.get("itemUrl") or {}).get("webLink") or "",
        crawled_at=crawled_at,
    )


def fetch_best_page(category_code: str, offset: int) -> dict:
    query = f"?categoryList={category_code}&periodSort=NOW&limit={BEST_LIMIT}&offset={offset}"
    req = urllib.request.Request(
        BEST_API + query,
        headers={
            "User-Agent": "Mozilla/5.0",
            "Accept": "application/json",
            "Referer": "https://www.29cm.co.kr/",
        },
    )
    with urllib.request.urlopen(req, timeout=60) as resp:
        payload = json.loads(resp.read())
    if not payload.get("data"):
        raise RuntimeError(payload.get("message") or "29CM 베스트 API 오류")
    return payload["data"]


def best_item_to_row(item: dict, crawled_at: str, rank: int) -> dict | None:
    name = (item.get("itemName") or "").strip()
    if not name:
        return None
    image = item.get("imageUrl") or ""
    if image and not image.startswith("http"):
        image = IMG_BASE + image
    cat_info = item.get("frontCategoryInfo") or []
    main_cat, sub_cat = "", ""
    if isinstance(cat_info, list) and cat_info:
        first = cat_info[0] or {}
        main_cat = first.get("category1Name") or first.get("largeName") or ""
        sub_cat = first.get("category2Name") or first.get("middleName") or ""
    item_no = item.get("itemNo") or ""
    return make_product_row(
        platform="29cm",
        is_ranking="true",
        rank=str(rank),
        brand=item.get("frontBrandNameKor") or item.get("frontBrandNameEng") or "",
        main_category=main_cat,
        category=sub_cat,
        product_name=name,
        regular_price=str(item.get("consumerPrice") or ""),
        current_price=str(item.get("lastSalePrice") or ""),
        discount_rate=str(item.get("lastSalePercent") or ""),
        thumbnail=image,
        rating=str(item.get("reviewAveragePoint") or ""),
        reviews=str(item.get("reviewCount") or ""),
        product_detail_url=f"https://product.29cm.co.kr/catalog/{item_no}" if item_no else "",
        crawled_at=crawled_at,
    )


class Cm29Crawler(BaseBrandCrawler):
    brand_id = "29cm"
    brand_name = "29CM"
    source_site = "29cm.co.kr"

    def _crawl_best(self, url: str, on_progress=None) -> list[dict]:
        """베스트(랭킹) 수집: is_ranking=true, rank 부여."""
        params = parse_qs(urlparse(url).query)
        category_code = (params.get("category_large_code") or params.get("categoryLargeCode") or ["268100100"])[0]
        crawled_at = today_yymmdd()
        products: list[dict] = []
        seen: set[str] = set()
        offset = 0

        while True:
            data = fetch_best_page(category_code, offset)
            batch = data.get("content") or []
            if not batch:
                break
            for i, item in enumerate(batch):
                rank = offset + i + 1
                row = best_item_to_row(item, crawled_at, rank)
                if not row:
                    continue
                key = row.get("product_detail_url") or row.get("product_name")
                if key in seen:
                    continue
                seen.add(key)
                products.append(row)
            if on_progress:
                on_progress(len(products), offset // BEST_LIMIT + 1)
            total = int(data.get("total") or 0)
            offset += BEST_LIMIT
            if offset >= total:
                break
            time.sleep(REQUEST_DELAY_SEC)

        if not products:
            raise RuntimeError(f"29CM 베스트 상품을 수집하지 못했습니다: {url}")
        return products

    def _crawl_best_products(self, url: str, on_progress=None) -> list[dict]:
        """/best-products 랭킹 수집 (성별·연령·기간 세그먼트): is_ranking=true, rank 부여."""
        qs = parse_qs(urlparse(url).query)
        params = {
            "period": (qs.get("period") or ["HOURLY"])[0],
            "ranking": (qs.get("ranking") or ["POPULARITY"])[0],
            "gender": (qs.get("gender") or ["F"])[0],
        }
        age_raw = (qs.get("age") or ["30"])[0]
        params["age"] = _AGE_SEGMENT.get(age_raw, age_raw)

        crawled_at = today_yymmdd()
        products: list[dict] = []
        seen: set[str] = set()
        page = 1

        while True:
            try:
                data = (fetch_best_products_page(params, page).get("data")) or {}
            except urllib.error.HTTPError as exc:
                if page == 1:
                    raise RuntimeError(f"29CM 베스트 API 오류: {exc}") from exc
                break  # 후속 페이지 오류는 상위 랭킹만으로 마감
            batch = data.get("list") or []
            if not batch:
                break
            for i, item in enumerate(batch):
                rank = (page - 1) * BEST_PRODUCTS_SIZE + i + 1
                row = best_products_item_to_row(item, crawled_at, rank)
                if not row:
                    continue
                key = row.get("product_detail_url") or row.get("product_name")
                if key in seen:
                    continue
                seen.add(key)
                products.append(row)
            if on_progress:
                on_progress(len(products), page)
            if not (data.get("pagination") or {}).get("hasNext"):
                break
            page += 1
            time.sleep(REQUEST_DELAY_SEC)

        if not products:
            raise RuntimeError(f"29CM 베스트 상품을 수집하지 못했습니다: {url}")
        return products

    def crawl(
        self,
        url: str | None = None,
        headless: bool = True,
        on_progress=None,
    ) -> list[dict]:
        target_url = url or (
            "https://www.29cm.co.kr/store/category/list?"
            "categoryLargeCode=268100100&categoryMediumCode=268103100"
        )
        if is_best_url(target_url):
            return self._crawl_best(target_url, on_progress)
        if is_best_products_url(target_url):
            return self._crawl_best_products(target_url, on_progress)
        large_id, medium_id = parse_category_from_url(target_url)
        if not large_id:
            raise ValueError("29CM URL에 categoryLargeCode가 필요합니다.")

        crawled_at = today_yymmdd()
        products: list[dict] = []
        seen_ids: set[str] = set()
        page_num = 1

        while True:
            try:
                data = fetch_page(large_id, medium_id, page_num)
            except urllib.error.HTTPError as exc:
                if page_num == 1:
                    raise RuntimeError(f"29CM API 오류: {exc}") from exc
                break

            listing = data.get("data") or {}
            items = listing.get("list") or []
            pagination = listing.get("pagination") or {}

            for item in items:
                if item.get("itemType") != "PRODUCT":
                    continue
                item_id = str(item.get("itemId") or "")
                if not item_id or item_id in seen_ids:
                    continue
                seen_ids.add(item_id)
                products.append(item_to_row(item, crawled_at))

            if not pagination.get("hasNext"):
                break

            if on_progress and (page_num == 1 or page_num % 5 == 0):
                on_progress(len(products), page_num)

            page_num += 1
            if page_num % 50 == 0:
                print(f"[29CM] page {page_num}, collected {len(products)} items...", flush=True)
            time.sleep(REQUEST_DELAY_SEC)

        return products
