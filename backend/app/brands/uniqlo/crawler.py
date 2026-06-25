"""Uniqlo 브랜드 크롤러"""

import json
import re
import time
import urllib.request
from urllib.parse import parse_qs, urlencode, urlparse

from app.brands.base import BaseBrandCrawler
from app.core.csv_schema import make_product_row, today_yymmdd

PRODUCTS_API = "https://www.uniqlo.com/kr/api/commerce/v5/ko/products"
DETAIL_API = "https://www.uniqlo.com/kr/api/commerce/v5/ko/products/{product_id}"
LIMIT = 36
REQUEST_DELAY_SEC = 0.35
DETAIL_DELAY_SEC = 0.2


def parse_uniqlo_params(url: str) -> dict:
    """URL 또는 기본 women/tops 파라미터"""
    parsed = urlparse(url)
    path = parsed.path.strip("/")
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


def fetch_product_detail(product_id: str) -> dict | None:
    if not product_id:
        return None
    req = urllib.request.Request(
        DETAIL_API.format(product_id=product_id),
        headers={"User-Agent": "Mozilla/5.0", "Accept": "application/json"},
    )
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            data = json.loads(resp.read())
        if data.get("status") == "ok" and isinstance(data.get("result"), dict):
            return data["result"]
    except Exception:
        return None
    return None


def _price_value(block: dict | None) -> str:
    if not isinstance(block, dict):
        return ""
    value = block.get("value")
    return str(value) if value not in (None, "") else ""


def get_price_pair(item: dict) -> tuple[str, str]:
    prices = item.get("prices") or {}
    base = prices.get("base") or prices.get("regular") or {}
    promo = prices.get("promo") or prices.get("sale") or {}
    regular = _price_value(base)
    current = _price_value(promo)
    if not regular and not current:
        for key in prices:
            if isinstance(prices[key], dict) and prices[key].get("value"):
                val = str(prices[key]["value"])
                regular = regular or val
                current = current or val
    if regular and current and int(current) >= int(regular):
        current = ""
    elif not regular:
        regular = current
        current = ""
    return regular, current


def parse_rating_reviews(item: dict) -> tuple[str, str]:
    rating_raw = item.get("rating")
    if isinstance(rating_raw, dict):
        avg = rating_raw.get("average")
        count = rating_raw.get("count")
        return (
            str(avg) if avg not in (None, "") else "",
            str(count) if count not in (None, "") else "",
        )
    reviews = item.get("reviewCount") or item.get("numReviews") or ""
    rating = str(rating_raw) if rating_raw not in (None, "") else ""
    return rating, str(reviews) if reviews not in (None, "") else ""


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


def _clean_html(text: str) -> str:
    if not text:
        return ""
    text = re.sub(r"<br\s*/?>", " | ", text, flags=re.I)
    text = re.sub(r"<[^>]+>", "", text)
    return re.sub(r"\s+", " ", text).strip()


def category_from_detail(detail: dict | None, fallback: str = "") -> str:
    if not detail:
        return fallback
    breadcrumbs = detail.get("breadcrumbs") or {}
    for key in ("subcategory", "category", "class"):
        node = breadcrumbs.get(key) or {}
        locale = (node.get("locale") or node.get("name") or "").strip()
        if locale:
            return locale
    return fallback


def manufacture_date_from_detail(detail: dict | None) -> str:
    if not detail:
        return ""
    mfg = detail.get("manufacturingDate") or {}
    if isinstance(mfg, dict):
        return str(mfg.get("localizedDate") or mfg.get("date") or "").strip()
    return str(mfg).strip()


def details_from_detail(detail: dict | None, item: dict) -> str:
    parts: list[str] = []
    if detail:
        design = _clean_html(detail.get("designDetail") or "")
        if design:
            parts.append(design)
        short = _clean_html(detail.get("shortDescription") or "")
        if short and short not in parts:
            parts.append(short)
    fit = item.get("fit") or item.get("silhouette") or ""
    length = item.get("length") or item.get("clothesLength") or ""
    for extra in (fit, length):
        if extra and extra not in parts:
            parts.append(str(extra))
    return " | ".join(parts)


def material_from_detail(detail: dict | None, item: dict) -> str:
    if detail:
        comp = detail.get("composition") or detail.get("material") or ""
        if comp:
            return str(comp).strip()
    mat = item.get("materialComposition") or item.get("material") or ""
    return str(mat).strip() if mat else ""


def item_to_row(
    item: dict,
    crawled_at: str,
    detail: dict | None = None,
    category_fallback: str = "",
) -> dict:
    product_id = item.get("productId") or ""
    name = item.get("name") or ""
    img = get_image(item)
    if img and not img.startswith("http"):
        img = "https:" + img if img.startswith("//") else ""

    regular, current = get_price_pair(item)
    rating, reviews = parse_rating_reviews(item)
    gender = item.get("genderName") or item.get("genderCategory") or ""

    return make_product_row(
        brand="UNIQLO",
        product_name=name,
        category=category_from_detail(detail, category_fallback),
        gender=gender,
        regular_price=regular,
        current_price=current,
        color=get_colors(item),
        thumbnail=img,
        material=material_from_detail(detail, item),
        details=details_from_detail(detail, item),
        rating=rating,
        reviews=reviews,
        manufacture_date=manufacture_date_from_detail(detail),
        product_detail_url=f"https://www.uniqlo.com/kr/ko/products/{product_id}/00" if product_id else "",
        crawled_at=crawled_at,
    )


class UniqloCrawler(BaseBrandCrawler):
    brand_id = "uniqlo"
    brand_name = "UNIQLO"
    source_site = "uniqlo.com"

    def crawl(
        self,
        url: str | None = None,
        headless: bool = True,
        category_name: str | None = None,
        **_,
    ) -> list[dict]:
        target_url = url or "https://www.uniqlo.com/kr/ko/women/tops"
        base_params = parse_uniqlo_params(target_url)
        crawled_at = today_yymmdd()
        category_fallback = category_name or ""
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
                detail = fetch_product_detail(pid)
                products.append(item_to_row(item, crawled_at, detail, category_fallback))
                time.sleep(DETAIL_DELAY_SEC)

            offset += len(items)
            if total is not None and offset >= total:
                break
            if len(items) < LIMIT:
                break

            time.sleep(REQUEST_DELAY_SEC)

        return products
