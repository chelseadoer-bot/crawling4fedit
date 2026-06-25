"""SPAO 크롤러 (공개 API + 상세 HTML 보강)"""

from __future__ import annotations

import json
import re
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
DETAIL_DELAY_SEC = 0.12
_ITEM_DETAIL_RE = re.compile(r"_state\.itemDetail\s*=\s*(\{.+?\});\s*\n", re.S)


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


def normalize_brand(name: str) -> str:
    name = (name or "스파오").strip()
    name = re.sub(r"^\[공식\]\s*", "", name)
    return name or "스파오"


def image_url(path: str) -> str:
    if not path:
        return ""
    if path.startswith("http"):
        return path
    path = path.lstrip("/")
    if not path.startswith("r/"):
        path = f"r/{path}"
    return f"{IMAGE_CDN}/{path}"


def product_link(item: dict) -> str:
    item_no = item.get("itemNo") or ""
    vendor = item.get("lowerVendNo") or DEFAULT_VENDOR
    return f"{BASE}/i/item?itemNo={item_no}&lowerVendNo={vendor}"


def colors_from_item(item: dict) -> str:
    chips = item.get("colorChip") or []
    names = [c.get("colorName", "").strip() for c in chips if c.get("colorName")]
    return ", ".join(names)


def price_pair_from_item(item: dict) -> tuple[str, str]:
    regular = item.get("orgSellprice") or item.get("sellprice") or ""
    final = item.get("finalDcPrice") or item.get("sellprice") or regular
    dc_rate = item.get("dcRate") or 0
    regular_s = str(regular) if regular not in (None, "") else ""
    if not regular_s:
        return "", ""
    try:
        if int(dc_rate) > 0 and int(final) < int(regular_s):
            return regular_s, str(final)
    except (TypeError, ValueError):
        pass
    return regular_s, ""


def fetch_item_detail(item_no: str, vendor: str) -> dict | None:
    if not item_no:
        return None
    url = f"{BASE}/i/item?itemNo={item_no}&lowerVendNo={vendor}"
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0", "Referer": f"{BASE}/"})
    try:
        html = urllib.request.urlopen(req, timeout=60).read().decode("utf-8", "ignore")
    except Exception:
        return None
    match = _ITEM_DETAIL_RE.search(html)
    if not match:
        return None
    try:
        return json.loads(match.group(1))
    except json.JSONDecodeError:
        return None


def category_from_detail(detail: dict | None, fallback: str = "") -> str:
    if not detail:
        return fallback
    cat = detail.get("category") or {}
    parts = [
        cat.get("largeClassDispCategoryName", "").strip(),
        cat.get("middleClassDispCategoryName", "").strip(),
        cat.get("smallClassDispCategoryName", "").strip(),
    ]
    joined = " > ".join(p for p in parts if p)
    return joined or fallback


def material_from_detail(detail: dict | None) -> str:
    if not detail:
        return ""
    desc = detail.get("descInfo") or {}
    for entry in desc.get("itemProvideMntList") or []:
        if not isinstance(entry, dict):
            continue
        name = (entry.get("itemProvideMntArtiName") or "").strip()
        content = (entry.get("itemProvideMntArtiCon") or "").strip()
        if not content:
            continue
        if "소재" in name or name.startswith("제품"):
            return content
    return ""


def manufacture_date_from_detail(detail: dict | None) -> str:
    if not detail:
        return ""
    desc = detail.get("descInfo") or {}
    for entry in desc.get("itemProvideMntList") or []:
        if not isinstance(entry, dict):
            continue
        name = (entry.get("itemProvideMntArtiName") or "").strip()
        content = (entry.get("itemProvideMntArtiCon") or "").strip()
        if not content:
            continue
        if "제조연월" in name or "제조년월" in name:
            return content
    return ""


def image_from_detail(detail: dict | None) -> str:
    if not detail:
        return ""
    images = (detail.get("images") or {}).get("itemImages") or []
    for img in images:
        if img.get("representYn") == "Y" and img.get("imagePath"):
            return image_url(img["imagePath"])
    for img in images:
        if img.get("imagePath"):
            return image_url(img["imagePath"])
    return ""


def enrich_row(row: dict, detail: dict | None, category_fallback: str = "") -> dict:
    if not detail:
        return row
    detail_cat = category_from_detail(detail)
    if detail_cat:
        row["category"] = detail_cat
    elif not row.get("category"):
        row["category"] = category_fallback
    if not row.get("material"):
        row["material"] = material_from_detail(detail)
    if not row.get("manufacture_date"):
        row["manufacture_date"] = manufacture_date_from_detail(detail)
    if not row.get("thumbnail"):
        row["thumbnail"] = image_from_detail(detail)
    return row


def parse_item(item: dict, crawled_at: str, category_fallback: str = "") -> dict | None:
    name = (item.get("itemName") or "").strip()
    item_no = item.get("itemNo")
    if not name or not item_no:
        return None

    vendor = item.get("lowerVendNo") or DEFAULT_VENDOR
    regular, current = price_pair_from_item(item)
    thumb = image_url(item.get("representImagePath") or "")
    if not thumb and isinstance(item.get("image"), list) and item["image"]:
        thumb = image_url(item["image"][0].get("imagePath") or "")

    category = (item.get("dispCategoryName") or "").strip()
    row = make_product_row(
        brand=normalize_brand(item.get("brandName") or "스파오"),
        platform="",
        product_name=name,
        category=category,
        gender="women",
        regular_price=regular,
        current_price=current,
        color=colors_from_item(item),
        thumbnail=thumb,
        rating=str(item.get("reviewScore") or ""),
        reviews=str(item.get("reviewCount") or ""),
        product_detail_url=product_link(item),
        crawled_at=crawled_at,
    )

    detail = fetch_item_detail(str(item_no), vendor)
    time.sleep(DETAIL_DELAY_SEC)
    return enrich_row(row, detail, category_fallback)


def crawl_planshop(
    exhibition_no: str,
    crawled_at: str,
    on_progress=None,
    category_fallback: str = "",
) -> list[dict]:
    """기획전(/p/planshop?exhibitionNo=) 상품 수집."""
    products: list[dict] = []
    seen: set[str] = set()
    section_sn = 0

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
                    "itemSize": PAGE_SIZE,
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
                row = parse_item(item, crawled_at, category_fallback)
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
            if item_start + PAGE_SIZE > total or len(batch) < PAGE_SIZE:
                break
            item_start += PAGE_SIZE
            time.sleep(0.1)

        if not section_had_items:
            break
        section_sn += 1

    return products


def crawl_new(category_no: str, crawled_at: str, on_progress=None, category_fallback: str = "") -> list[dict]:
    url = f"{BASE}/api/item/new?size=1000&dispCategoryNo={category_no}"
    data = api_get(url)
    batch = data.get("data") or []
    if not isinstance(batch, list):
        return []
    products: list[dict] = []
    seen: set[str] = set()
    for item in batch:
        row = parse_item(item, crawled_at, category_fallback)
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


def crawl_category(category_no: str, crawled_at: str, on_progress=None, category_fallback: str = "") -> list[dict]:
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
            row = parse_item(item, crawled_at, category_fallback)
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
        category_name: str | None = None,
        **_kwargs,
    ) -> list[dict]:
        if not url:
            raise ValueError("URL이 필요합니다.")
        crawled_at = today_yymmdd()
        category_fallback = category_name or ""
        if is_planshop_url(url):
            exhibition_no = parse_exhibition_no(url)
            products = crawl_planshop(exhibition_no, crawled_at, on_progress, category_fallback)
        else:
            category_no = parse_disp_category_no(url)
            if is_new_url(url):
                products = crawl_new(category_no, crawled_at, on_progress, category_fallback)
            else:
                products = crawl_category(category_no, crawled_at, on_progress, category_fallback)
        if not products:
            raise RuntimeError(f"SPAO 상품을 수집하지 못했습니다: {url}")
        return products
