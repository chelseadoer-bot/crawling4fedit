"""The Barnnet (Cafe24) 크롤러 — 상세 페이지 패브릭 정보 포함"""

import json
import re
import time
import urllib.parse
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed
from urllib.parse import parse_qs, urlparse

from app.brands.base import BaseBrandCrawler
from app.core.csv_schema import make_product_row, today_yymmdd

BASE = "https://the-barnnet.com"
PAGE_SIZE = 40
REQUEST_DELAY_SEC = 0.3
DETAIL_WORKERS = 6
DETAIL_DELAY_SEC = 0.15

UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/131.0.0.0 Safari/537.36"}

FABRIC_KEYS = {
    "lining": ["안감", "내부", "내면"],
    "thickness": ["두께감", "두께", "두께 감"],
    "season": ["계절감", "계절", "시즌"],
    "transparency": ["비침", "비침감", "투명도"],
    "elasticity": ["신축성", "늘어남", "탄성"],
    "material": ["소재", "원단", "재질", "소재/원단"],
    "fit": ["핏", "핏감"],
    "length": ["기장", "기장감", "총장"],
    "sleeve_length": ["소매", "소매길이", "소매 길이"],
    "color": ["색상", "컬러"],
}

_DETAIL_LABELS = [
    ("핏", "fit"), ("기장", "length"), ("소매길이", "sleeve_length"),
    ("안감", "lining"), ("두께감", "thickness"), ("계절감", "season"),
    ("비침", "transparency"), ("신축성", "elasticity"),
]


def strip_html(text: str) -> str:
    return re.sub(r"<[^>]+>", "", text or "").strip()


def parse_cate_no(url: str) -> str:
    parsed = urlparse(url)
    params = parse_qs(parsed.query)
    cate = params.get("cate_no", [None])[0]
    if cate:
        return str(cate)
    if "list_all.html" in parsed.path:
        return "299"
    return "101"


def fetch_page(cate_no: str, page: int) -> dict:
    query = urllib.parse.urlencode({"cate_no": cate_no, "page": page, "count": PAGE_SIZE})
    api_url = f"{BASE}/exec/front/Product/ApiProductList?{query}"
    req = urllib.request.Request(api_url, headers=UA)
    with urllib.request.urlopen(req, timeout=60) as resp:
        return json.loads(resp.read())


def fetch_detail_html(product_no: str) -> str:
    url = f"{BASE}/product/detail.html?product_no={product_no}"
    req = urllib.request.Request(url, headers=UA)
    try:
        with urllib.request.urlopen(req, timeout=20) as resp:
            return resp.read().decode("utf-8", "replace")
    except Exception:
        return ""


def parse_fabric_info(html: str) -> dict:
    result = {k: "" for k in FABRIC_KEYS}

    table_pattern = re.compile(
        r'<th[^>]*>\s*([^<]+?)\s*</th>\s*<td[^>]*>(.*?)</td>',
        re.S | re.I,
    )
    for m in table_pattern.finditer(html):
        label = strip_html(m.group(1)).replace("\xa0", "").strip()
        value = strip_html(m.group(2)).replace("\xa0", " ").strip()
        if not value or value in ("-", "—", "없음"):
            continue
        for key, aliases in FABRIC_KEYS.items():
            if any(alias in label for alias in aliases):
                if not result[key]:
                    result[key] = value

    dt_dd = re.compile(r'<dt[^>]*>\s*([^<]+?)\s*</dt>\s*<dd[^>]*>(.*?)</dd>', re.S | re.I)
    for m in dt_dd.finditer(html):
        label = strip_html(m.group(1)).strip()
        value = strip_html(m.group(2)).strip()
        if not value or value in ("-", "—"):
            continue
        for key, aliases in FABRIC_KEYS.items():
            if any(alias in label for alias in aliases):
                if not result[key]:
                    result[key] = value

    li_pattern = re.compile(r'<li[^>]*>\s*([^<:]+?)\s*:\s*([^<]+?)\s*</li>', re.S | re.I)
    for m in li_pattern.finditer(html):
        label = m.group(1).strip()
        value = m.group(2).strip()
        if not value or value in ("-", "—"):
            continue
        for key, aliases in FABRIC_KEYS.items():
            if any(alias in label for alias in aliases):
                if not result[key]:
                    result[key] = value

    return result


def fetch_product_detail(product_no: str) -> dict:
    html = fetch_detail_html(product_no)
    if not html:
        return {k: "" for k in FABRIC_KEYS}
    time.sleep(DETAIL_DELAY_SEC)
    return parse_fabric_info(html)


def item_to_row(item: dict, fabric: dict, crawled_at: str) -> dict:
    name = strip_html(item.get("product_name") or item.get("product_name_tag") or "")
    price = str(item.get("product_price") or item.get("price") or "").split(".")[0]
    product_no = str(item.get("product_no") or "")
    image = item.get("image_medium") or item.get("image_big") or item.get("image_small") or ""
    if image.startswith("/"):
        image = BASE + image
    if image and not image.startswith("http"):
        image = "https:" + image if image.startswith("//") else ""

    color = fabric.get("color") or item.get("option_text") or item.get("color") or ""
    sale_price = str(item.get("sale_price") or "").split(".")[0]
    detail_url = f"{BASE}/product/detail.html?product_no={product_no}" if product_no else ""

    # Merge non-spec fabric fields into details
    detail_parts = []
    for label, key in _DETAIL_LABELS:
        v = fabric.get(key, "")
        if v:
            detail_parts.append(f"{label}: {v}")

    return make_product_row(
        brand="THE BARNNET",
        platform="the-barnnet.com",
        product_name=name,
        regular_price=price,
        current_price=sale_price or price,
        discount_rate=str(item.get("discount_rate") or ""),
        color=color,
        thumbnail=image,
        material=fabric.get("material", ""),
        details=" | ".join(detail_parts),
        product_detail_url=detail_url,
        crawled_at=crawled_at,
    )


class BarnetCrawler(BaseBrandCrawler):
    brand_id = "barnet"
    brand_name = "THE BARNNET"
    source_site = "the-barnnet.com"

    def crawl(
        self,
        url: str | None = None,
        headless: bool = True,
        on_progress=None,
    ) -> list[dict]:
        target_url = url or f"{BASE}/product/list_all.html?cate_no=299"
        cate_no = parse_cate_no(target_url)
        crawled_at = today_yymmdd()
        raw_items: list[dict] = []
        seen: set[str] = set()
        page_num = 1

        while True:
            data = fetch_page(cate_no, page_num)
            items = data.get("Data") or data.get("data") or []
            if not isinstance(items, list) or not items:
                break

            for item in items:
                pid = str(item.get("product_no") or "")
                if not pid or pid in seen:
                    continue
                seen.add(pid)
                raw_items.append(item)

            if on_progress:
                on_progress(len(raw_items), page_num)

            if len(items) < PAGE_SIZE:
                break
            page_num += 1
            time.sleep(REQUEST_DELAY_SEC)

        fabric_map: dict[str, dict] = {}
        total = len(raw_items)

        with ThreadPoolExecutor(max_workers=DETAIL_WORKERS) as executor:
            future_to_pid = {
                executor.submit(fetch_product_detail, str(item.get("product_no", ""))): str(item.get("product_no", ""))
                for item in raw_items
            }
            done = 0
            for future in as_completed(future_to_pid):
                pid = future_to_pid[future]
                try:
                    fabric_map[pid] = future.result()
                except Exception:
                    fabric_map[pid] = {k: "" for k in FABRIC_KEYS}
                done += 1
                if on_progress and done % 20 == 0:
                    on_progress(total + done, page_num)

        products = []
        for item in raw_items:
            pid = str(item.get("product_no") or "")
            fabric = fabric_map.get(pid, {k: "" for k in FABRIC_KEYS})
            products.append(item_to_row(item, fabric, crawled_at))

        return products
