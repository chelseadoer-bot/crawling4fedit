"""Cafe24 쇼핑몰 공통 크롤러 (product/list.html?cate_no=)"""

from __future__ import annotations

import json
import re
import time
import urllib.parse
import urllib.request
from urllib.parse import parse_qs, urlparse

from app.brands.base import BaseBrandCrawler
from app.core.csv_schema import make_product_row, today_yymmdd

PAGE_SIZE = 40
REQUEST_DELAY_SEC = 0.25
UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/131.0.0.0 Safari/537.36"}


def strip_html(text: str) -> str:
    return re.sub(r"<[^>]+>", "", text or "").strip()


def site_base(url: str) -> str:
    parsed = urlparse(url)
    return f"{parsed.scheme}://{parsed.netloc}"


def brand_label_from_url(url: str, fallback: str = "") -> str:
    if fallback:
        return fallback
    host = urlparse(url).netloc.lower().replace("www.", "").replace("m.", "")
    name = host.split(".")[0]
    return name.upper()


def parse_cate_no(url: str) -> str:
    parsed = urlparse(url)
    params = parse_qs(parsed.query)
    cate = params.get("cate_no", [None])[0]
    if cate:
        return str(cate)
    path_match = re.search(r"/category/[^/]+/(\d+)", parsed.path)
    if path_match:
        return path_match.group(1)
    path_match = re.search(r"/(?:new|category)/(\d+)", parsed.path)
    if path_match:
        return path_match.group(1)
    raise ValueError(f"Cafe24 URL에 cate_no가 필요합니다: {url}")


def list_page_url(base: str, cate_no: str) -> str:
    return f"{base}/product/list.html?cate_no={cate_no}"


def fetch_page(base: str, cate_no: str, page: int, referer: str | None = None) -> dict:
    query = urllib.parse.urlencode({"cate_no": cate_no, "page": page, "count": PAGE_SIZE})
    api_url = f"{base}/exec/front/Product/ApiProductList?{query}"
    headers = {
        **UA,
        "Referer": referer or list_page_url(base, cate_no),
        "Accept": "application/json, text/javascript, */*; q=0.01",
    }
    req = urllib.request.Request(api_url, headers=headers)
    with urllib.request.urlopen(req, timeout=60) as resp:
        return json.loads(resp.read())


def item_to_row(item: dict, base: str, brand_name: str, crawled_at: str) -> dict:
    name = strip_html(item.get("product_name") or item.get("product_name_tag") or "")
    price = str(item.get("product_price") or item.get("price") or "").split(".")[0]
    product_no = str(item.get("product_no") or "")
    image = item.get("image_medium") or item.get("image_big") or item.get("image_small") or ""
    if image.startswith("/"):
        image = base + image
    elif image.startswith("//"):
        image = "https:" + image

    sale_price = str(item.get("sale_price") or "").split(".")[0]
    detail_url = f"{base}/product/detail.html?product_no={product_no}" if product_no else ""

    return make_product_row(
        brand=brand_name,
        platform=urlparse(base).netloc,
        product_name=name,
        regular_price=price,
        current_price=sale_price or price,
        discount_rate=str(item.get("discount_rate") or ""),
        color=item.get("option_text") or item.get("color") or "",
        thumbnail=image,
        product_detail_url=detail_url,
        crawled_at=crawled_at,
    )


class Cafe24Crawler(BaseBrandCrawler):
    brand_id = "cafe24"
    brand_name = "CAFE24"
    source_site = "cafe24.com"

    def crawl(
        self,
        url: str | None = None,
        headless: bool = True,
        on_progress=None,
        brand_name: str | None = None,
        **_,
    ) -> list[dict]:
        if not url:
            raise ValueError("Cafe24 크롤 URL이 필요합니다.")
        base = site_base(url)
        cate_no = parse_cate_no(url)
        label = brand_label_from_url(url, brand_name or "")
        referer = url if "cate_no=" in url else list_page_url(base, cate_no)
        crawled_at = today_yymmdd()
        products: list[dict] = []
        seen: set[str] = set()
        page_num = 1

        while True:
            try:
                data = fetch_page(base, cate_no, page_num, referer=referer)
            except Exception as exc:
                if page_num == 1:
                    raise RuntimeError(f"Cafe24 API 실패 ({base}): {exc}") from exc
                break

            items = data.get("Data") or data.get("data") or []
            if not isinstance(items, list) or not items:
                break

            for item in items:
                pid = str(item.get("product_no") or "")
                if not pid or pid in seen:
                    continue
                seen.add(pid)
                products.append(item_to_row(item, base, label, crawled_at))

            if on_progress:
                on_progress(len(products), page_num)

            if len(items) < PAGE_SIZE:
                break
            page_num += 1
            time.sleep(REQUEST_DELAY_SEC)

        return products
