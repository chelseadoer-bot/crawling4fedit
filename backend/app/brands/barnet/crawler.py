"""The Barnnet (Cafe24) 크롤러"""

import json
import re
import time
import urllib.parse
import urllib.request
from urllib.parse import parse_qs, urlparse

from app.brands.base import BaseBrandCrawler
from app.core.csv_schema import empty_row, now_timestamp

BASE = "https://the-barnnet.com"
PAGE_SIZE = 40
REQUEST_DELAY_SEC = 0.3


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
    req = urllib.request.Request(
        api_url,
        headers={"User-Agent": "Mozilla/5.0", "Accept": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=60) as resp:
        return json.loads(resp.read())


def item_to_row(item: dict, crawled_at: str) -> dict:
    name = strip_html(item.get("product_name") or item.get("product_name_tag") or "")
    price = str(item.get("product_price") or item.get("price") or "").split(".")[0]
    product_no = str(item.get("product_no") or "")
    image = item.get("image_medium") or item.get("image_big") or item.get("image_small") or ""
    if image.startswith("/"):
        image = BASE + image

    row = empty_row()
    row.update(
        {
            "brand": "THE BARNNET",
            "product_id": product_no,
            "product_name": name,
            "category_large": "",
            "category_small": "",
            "price_original": price,
            "price_sale": "",
            "discount_rate": "",
            "color": "",
            "sizes_available": "",
            "stock_status": "unknown",
            "product_url": f"{BASE}/product/detail.html?product_no={product_no}" if product_no else "",
            "image_url": image,
            "crawled_at": crawled_at,
            "source_site": "the-barnnet.com",
        }
    )
    return row


class BarnetCrawler(BaseBrandCrawler):
    brand_id = "barnet"
    brand_name = "THE BARNNET"
    source_site = "the-barnnet.com"

    def crawl(
        self,
        url: str | None = None,
        headless: bool = False,
        on_progress=None,
    ) -> list[dict]:
        target_url = url or f"{BASE}/product/list_all.html?cate_no=299"
        cate_no = parse_cate_no(target_url)
        crawled_at = now_timestamp()
        products: list[dict] = []
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
                products.append(item_to_row(item, crawled_at))

            if on_progress:
                on_progress(len(products), page_num)

            if len(items) < PAGE_SIZE:
                break
            page_num += 1
            time.sleep(REQUEST_DELAY_SEC)

        return products
