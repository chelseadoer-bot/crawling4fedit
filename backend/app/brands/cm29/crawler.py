"""29CM 브랜드 크롤러"""

import json
import re
import time
import urllib.error
import urllib.request
from urllib.parse import parse_qs, urlparse

from app.brands.base import BaseBrandCrawler
from app.core.csv_schema import empty_row, now_timestamp

LISTING_API = "https://display-bff-api.29cm.co.kr/api/v1/listing/items?colorchipVariant=control"
PAGE_SIZE = 50
REQUEST_DELAY_SEC = 0.3


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
    price = info.get("displayPrice") or event.get("price") or ""
    brand = info.get("brandName") or event.get("brandName") or "29CM"
    image = info.get("thumbnailUrl") or ""
    product_url = url_obj.get("webLink") or ""
    item_id = item.get("itemId") or event.get("itemNo") or ""

    color = extract_color_from_name(name)
    if not color and info.get("colorName"):
        color = info.get("colorName")

    row = empty_row()
    row.update(
        {
            "brand": brand,
            "product_id": str(item_id),
            "product_name": name,
            "category_large": event.get("largeCategoryName") or "",
            "category_small": event.get("middleCategoryName") or "",
            "price_original": str(price),
            "price_sale": "",
            "discount_rate": str(info.get("saleRate") or event.get("discountRate") or ""),
            "color": color,
            "sizes_available": "",
            "stock_status": "out_of_stock" if info.get("isSoldOut") else "in_stock",
            "product_url": product_url,
            "image_url": image,
            "crawled_at": crawled_at,
            "source_site": "29cm.co.kr",
        }
    )
    return row


class Cm29Crawler(BaseBrandCrawler):
    brand_id = "29cm"
    brand_name = "29CM"
    source_site = "29cm.co.kr"

    def crawl(
        self,
        url: str | None = None,
        headless: bool = False,
        on_progress=None,
    ) -> list[dict]:
        target_url = url or (
            "https://www.29cm.co.kr/store/category/list?"
            "categoryLargeCode=268100100&categoryMediumCode=268103100"
        )
        large_id, medium_id = parse_category_from_url(target_url)
        if not large_id:
            raise ValueError("29CM URL에 categoryLargeCode가 필요합니다.")

        crawled_at = now_timestamp()
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
