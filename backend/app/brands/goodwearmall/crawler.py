"""굿웨어몰(탑텐) 카테고리 API 크롤러"""

from __future__ import annotations

import json
import re
import time
import urllib.parse
import urllib.request
from urllib.parse import urlparse

from app.brands.base import BaseBrandCrawler
from app.core.csv_schema import make_product_row, today_yymmdd

PAGE_SIZE = 60
REQUEST_DELAY_SEC = 0.2
UA = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/131.0.0.0 Safari/537.36",
    "Accept": "application/json",
}


def site_origin(url: str) -> str:
    parsed = urlparse(url)
    return f"{parsed.scheme}://{parsed.netloc}"


def parse_category_code(url: str) -> str:
    path = urlparse(url).path.strip("/")
    if path.startswith("category/"):
        code = path.split("/")[-1]
        if code:
            return code
    raise ValueError(f"굿웨어몰 카테고리 URL이 아닙니다: {url}")


def fetch_page(origin: str, category_cd: str, page_no: int) -> dict:
    params = {
        "categoryCd": category_cd,
        "categoryType": "GENERAL",
        "godDspUnitCd": "GOD_COLOR",
        "outlet": "false",
        "pageNo": page_no,
        "polhamShop": "false",
        "selectShop": "false",
        "sort": "BST",
        "strategy": "",
    }
    api = f"{origin}/api/category/products?{urllib.parse.urlencode(params)}"
    req = urllib.request.Request(
        api,
        headers={
            **UA,
            "Referer": f"{origin}/category/{category_cd}",
        },
    )
    with urllib.request.urlopen(req, timeout=60) as resp:
        return json.loads(resp.read())


def item_to_row(item: dict, origin: str, brand_name: str, crawled_at: str) -> dict:
    name = (item.get("GOD_NM") or item.get("godNm") or "").strip()
    god_no = str(item.get("GOD_NO") or item.get("godNo") or "")
    sale = str(item.get("LAST_SALE_PRC") or item.get("lastSalePrc") or "").split(".")[0]
    regular = str(item.get("CVR_PRC") or item.get("cvrPrc") or sale).split(".")[0]
    image = item.get("IMG_URL") or item.get("imgUrl") or ""
    if image and not str(image).startswith("http"):
        # display 도메인 이미지는 404 — img CDN 사용
        image = "https://img.goodwearmall.com" + image if str(image).startswith("/") else image
    elif "display-topten10.goodwearmall.com" in str(image):
        image = str(image).replace("display-topten10.goodwearmall.com", "img.goodwearmall.com")
    shop_host = origin.replace("display-", "").replace("display.", "")
    detail = f"{shop_host}/product/{god_no}/detail" if god_no else ""
    discount = str(item.get("GOD_DC_RT") or item.get("godDcRt") or "")
    return make_product_row(
        brand=brand_name or str(item.get("BRND_NM") or item.get("brandNm") or "TOPTEN"),
        platform=urlparse(origin).netloc,
        product_name=name,
        regular_price=regular,
        current_price=sale,
        discount_rate=discount,
        thumbnail=str(image),
        product_detail_url=detail,
        crawled_at=crawled_at,
    )


class GoodwearmallCrawler(BaseBrandCrawler):
    brand_id = "goodwearmall"
    brand_name = "TOPTEN"
    source_site = "goodwearmall.com"

    def crawl(
        self,
        url: str | None = None,
        headless: bool = True,
        on_progress=None,
        brand_name: str | None = None,
        **_,
    ) -> list[dict]:
        if not url:
            raise ValueError("굿웨어몰 URL이 필요합니다.")
        origin = site_origin(url)
        category_cd = parse_category_code(url)
        label = brand_name or "TOPTEN"
        crawled_at = today_yymmdd()
        products: list[dict] = []
        seen: set[str] = set()
        page_no = 1
        total_size = None

        while True:
            data = fetch_page(origin, category_cd, page_no)
            if total_size is None:
                total_size = int(data.get("totalSize") or 0)
            docs = data.get("documents") or []
            if not docs:
                break

            for item in docs:
                god_no = str(item.get("GOD_NO") or item.get("godNo") or "")
                if not god_no or god_no in seen:
                    continue
                seen.add(god_no)
                row = item_to_row(item, origin, label, crawled_at)
                if row.get("product_name"):
                    products.append(row)

            if on_progress:
                on_progress(len(products), page_no)

            if total_size and len(products) >= total_size:
                break
            if len(docs) < PAGE_SIZE:
                break
            page_no += 1
            time.sleep(REQUEST_DELAY_SEC)

        if not products:
            raise RuntimeError(f"굿웨어몰 상품을 수집하지 못했습니다: {url}")
        return products
