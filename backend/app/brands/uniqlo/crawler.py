"""Uniqlo 브랜드 크롤러"""

import json
import time
import urllib.request
from urllib.parse import parse_qs, urlencode, urlparse

from app.brands.base import BaseBrandCrawler
from app.core.csv_schema import make_product_row, today_yymmdd

PRODUCTS_API = "https://www.uniqlo.com/kr/api/commerce/v5/ko/products"
LIMIT = 36
REQUEST_DELAY_SEC = 0.5


def parse_uniqlo_params(url: str) -> dict:
    """URL 또는 기본 women/tops 파라미터"""
    parsed = urlparse(url)
    path = parsed.path.strip("/")
    # 기본: women tops
    params = {
        "path": "57892,57959,,",
        "genderId": "57892",
        "offset": "0",
        "limit": str(LIMIT),
        "imageRatio": "3x4",
        "rankingGender": "women",
        "rankingClassId": "57959",
        "httpFailure": "true",
    }

    # 홈(/kr/ko/) → 여성 전체
    if path in ("kr/ko", "kr/ko/", "") or path.endswith("/kr/ko"):
        params["path"] = "57892,,,"
        params["rankingClassId"] = ""
        params.pop("rankingClassId", None)
        params["rankingGender"] = "women"

    query = parse_qs(parsed.query)
    if query.get("path"):
        params["path"] = query["path"][0]
    if query.get("genderId"):
        params["genderId"] = query["genderId"][0]
    if query.get("rankingClassId"):
        params["rankingClassId"] = query["rankingClassId"][0]
    if query.get("rankingGender"):
        params["rankingGender"] = query["rankingGender"][0]

    return params


def fetch_products(base_params: dict, offset: int) -> dict:
    params = {**base_params, "offset": str(offset)}
    api_url = f"{PRODUCTS_API}?{urlencode(params)}"
    req = urllib.request.Request(
        api_url,
        headers={"User-Agent": "Mozilla/5.0", "Accept": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=60) as resp:
        return json.loads(resp.read())


def get_price(item: dict) -> str:
    prices = item.get("prices") or {}
    promo = prices.get("promo") or prices.get("sale") or {}
    base = prices.get("base") or prices.get("regular") or {}
    value = promo.get("value") or base.get("value") or ""
    if not value and isinstance(prices, dict):
        for key in prices:
            if isinstance(prices[key], dict) and prices[key].get("value"):
                value = prices[key]["value"]
                break
    return str(value) if value else ""


def get_image(item: dict) -> str:
    images = item.get("images") or {}
    main = images.get("main") or {}
    rep_code = item.get("representativeColorDisplayCode") or item.get("representative", {}).get("colorDisplayCode")
    if rep_code and str(rep_code) in main:
        return main[str(rep_code)].get("image", "")
    if main:
        first = next(iter(main.values()), {})
        return first.get("image", "")
    rep = item.get("representative") or {}
    return rep.get("imageUrl") or rep.get("image") or ""


def get_colors(item: dict) -> str:
    return ", ".join(c.get("name", "") for c in item.get("colors", []) if c.get("name"))


def get_sizes(item: dict) -> str:
    sizes = []
    for s in item.get("sizes", []):
        label = s.get("name") or s.get("displayCode") or s.get("code") or ""
        if label and label not in sizes:
            sizes.append(str(label))
    if not sizes:
        for s in item.get("stocks", []):
            label = s.get("size") or s.get("sizeName") or ""
            if label and label not in sizes:
                sizes.append(str(label))
    return ", ".join(sizes)


def get_material(item: dict) -> str:
    mat = item.get("materialComposition") or item.get("material") or ""
    if mat:
        return str(mat).strip()
    descriptions = item.get("shortDescription") or item.get("description") or ""
    if isinstance(descriptions, list):
        descriptions = " / ".join(str(d) for d in descriptions)
    return str(descriptions).strip() if descriptions else ""


def get_fit(item: dict) -> str:
    return item.get("fit") or item.get("silhouette") or ""


def get_length(item: dict) -> str:
    return item.get("length") or item.get("clothesLength") or ""


def item_to_row(item: dict, crawled_at: str) -> dict:
    product_id = item.get("productId") or ""
    name = item.get("name") or ""
    img = get_image(item)
    if img and not img.startswith("http"):
        img = "https:" + img if img.startswith("//") else ""
    price = get_price(item)
    # fit/length → details로 통합
    fit = get_fit(item)
    length = get_length(item)
    details_parts = [p for p in [fit, length] if p]
    return make_product_row(
        brand="UNIQLO",
        product_name=name,
        category=item.get("subCategoryName") or item.get("categoryName") or "",
        gender=item.get("genderName") or "",
        regular_price=price,
        current_price=price,
        color=get_colors(item),
        thumbnail=img,
        material=get_material(item),
        details=" | ".join(details_parts),
        rating=str(item.get("rating") or ""),
        reviews=str(item.get("reviewCount") or item.get("numReviews") or ""),
        product_detail_url=f"https://www.uniqlo.com/kr/ko/products/{product_id}/00" if product_id else "",
        crawled_at=crawled_at,
    )


class UniqloCrawler(BaseBrandCrawler):
    brand_id = "uniqlo"
    brand_name = "UNIQLO"
    source_site = "uniqlo.com"

    def crawl(self, url: str | None = None, headless: bool = True) -> list[dict]:
        target_url = url or "https://www.uniqlo.com/kr/ko/women/tops"
        base_params = parse_uniqlo_params(target_url)
        crawled_at = today_yymmdd()
        products: list[dict] = []
        seen: set[str] = set()
        offset = 0
        total = None

        while True:
            data = fetch_products(base_params, offset)
            if data.get("status") != "ok":
                break

            result = data.get("result") or {}
            items = result.get("items") or []
            pagination = result.get("pagination") or {}
            total = pagination.get("total", total)

            if not items:
                break

            for item in items:
                pid = item.get("productId") or ""
                if not pid or pid in seen:
                    continue
                seen.add(pid)
                products.append(item_to_row(item, crawled_at))

            offset += len(items)
            if total is not None and offset >= total:
                break
            if len(items) < LIMIT:
                break

            time.sleep(REQUEST_DELAY_SEC)

        return products
