"""Moncler SearchApi-Search 크롤러 (여성 ready-to-wear)"""

import re
from urllib.parse import parse_qs, urlparse

from playwright.sync_api import sync_playwright

from app.brands.base import BaseBrandCrawler
from app.brands.browser_utils import dismiss_popups, launch_browser, new_stealth_context
from app.core.csv_schema import make_product_row, today_yymmdd

BASE = "https://www.moncler.com"
DEFAULT_URL = "https://www.moncler.com/ko-kr/women/ready-to-wear"
CGID = "women-ready-to-wear"
PAGE_SIZE = 16
SCROLL_ROUNDS = 25

COUNTRY_NAMES = {
    "australia", "austria", "belgium", "bulgaria", "croatia", "cyprus",
    "czech", "denmark", "estonia", "finland", "france", "germany", "greece",
    "hungary", "ireland", "italy", "japan", "korea", "latvia", "lithuania",
    "luxembourg", "malta", "netherlands", "norway", "poland", "portugal",
    "romania", "slovakia", "slovenia", "spain", "sweden", "switzerland",
    "united kingdom", "united states",
}


def extract_cgid(url: str) -> str:
    parsed = urlparse(url)
    qs = parse_qs(parsed.query)
    if qs.get("cgid"):
        return qs["cgid"][0]

    path = parsed.path.strip("/").lower()
    if "view-all-new-arrivals" in path:
        return "view-all-new-arrivals"
    if "ready-to-wear" in path:
        return CGID
    if "outerwear" in path:
        return "women-outerwear"
    parts = [p for p in path.split("/") if p and p not in ("ko-kr", "en-us", "en-gb")]
    if parts:
        return parts[-1]
    return CGID


def parse_price(prod: dict) -> str:
    price = prod.get("price") or {}
    if isinstance(price, dict):
        sales = price.get("sales") or {}
        if isinstance(sales, dict):
            if sales.get("formatted"):
                return str(sales["formatted"])
            if sales.get("value") is not None:
                return str(int(sales["value"]))
        listed = price.get("list") or {}
        if isinstance(listed, dict) and listed.get("formatted"):
            return str(listed["formatted"])
    return ""


def parse_color(prod: dict) -> str:
    for attr in prod.get("variationAttributes") or []:
        if attr.get("attributeId") == "color":
            return str(attr.get("displayValue") or "")
    return ""


def parse_image(prod: dict) -> str:
    imgs = prod.get("imgs") or {}
    urls = imgs.get("urls") if isinstance(imgs, dict) else None
    if isinstance(urls, list) and urls:
        return urls[0]
    for attr in prod.get("variationAttributes") or []:
        if attr.get("attributeId") != "color":
            continue
        for val in attr.get("values") or []:
            if val.get("selected") and val.get("swatchImg"):
                return val["swatchImg"]
    return ""


def parse_product(prod: dict, crawled_at: str) -> dict | None:
    if prod.get("type") not in (None, "tile", "product"):
        return None
    name = (prod.get("productName") or "").strip()
    if not name or name.lower() in COUNTRY_NAMES:
        return None
    pid = str(prod.get("id") or prod.get("masterId") or "")
    if not pid or not re.match(r"^L\d", pid):
        return None

    rel_url = prod.get("productUrl") or prod.get("route") or ""
    if not rel_url:
        return None
    product_url = rel_url if rel_url.startswith("http") else BASE + rel_url

    price = parse_price(prod)
    price_digits = re.sub(r"[^\d]", "", price)

    return make_product_row(
        brand="MONCLER",
        main_category="명품",
        category="여성 RTW",
        gender="여성",
        product_name=name,
        regular_price=price_digits or price,
        current_price=price_digits or price,
        color=parse_color(prod),
        thumbnail=parse_image(prod),
        product_detail_url=product_url,
        crawled_at=crawled_at,
    )


def ingest_search_payload(payload: dict, crawled_at: str, seen: set[str], out: list[dict]) -> int:
    data = payload.get("data") if isinstance(payload, dict) else None
    if not isinstance(data, dict):
        return 0
    products = data.get("products") or []
    added = 0
    for prod in products:
        if not isinstance(prod, dict):
            continue
        row = parse_product(prod, crawled_at)
        if not row:
            continue
        key = row.get("product_detail_url") or row.get("product_name")
        if key in seen:
            continue
        seen.add(key)
        out.append(row)
        added += 1
    return added


class MonclerCrawler(BaseBrandCrawler):
    brand_id = "moncler"
    brand_name = "MONCLER"
    source_site = "moncler.com"

    def crawl(
        self,
        url: str | None = None,
        headless: bool = True,
        on_progress=None,
    ) -> list[dict]:
        target_url = url or DEFAULT_URL
        cgid = extract_cgid(target_url)
        crawled_at = today_yymmdd()
        captured: list[dict] = []
        all_products: list[dict] = []
        seen: set[str] = set()

        with sync_playwright() as p:
            browser = launch_browser(p, headless=headless)
            context, page = new_stealth_context(browser)

            def on_response(response):
                u = response.url
                if response.status != 200 or "SearchApi-Search" not in u:
                    return
                try:
                    captured.append(response.json())
                except Exception:
                    pass

            page.on("response", on_response)
            page.goto(target_url, wait_until="domcontentloaded", timeout=120000)
            dismiss_popups(page)
            page.wait_for_timeout(4000)

            for i in range(SCROLL_ROUNDS):
                page.evaluate("window.scrollBy(0, window.innerHeight * 0.9)")
                page.wait_for_timeout(1100)
                for payload in captured:
                    ingest_search_payload(payload, crawled_at, seen, all_products)
                captured.clear()
                if on_progress:
                    on_progress(len(all_products), i + 1)

            start = 0
            total = None
            while True:
                api_url = (
                    f"{BASE}/api/MonclerSouthKorea/storefront/ko_KR/SearchApi-Search"
                    f"?cgid={cgid}&srule=&sz={PAGE_SIZE}&start={start}"
                )
                try:
                    resp = context.request.get(
                        api_url,
                        headers={"Accept": "application/json", "Referer": target_url},
                        timeout=60000,
                    )
                    if not resp.ok:
                        break
                    payload = resp.json()
                    data = payload.get("data") or {}
                    if total is None:
                        total = int(data.get("count") or 0)
                    before = len(all_products)
                    ingest_search_payload(payload, crawled_at, seen, all_products)
                    if len(all_products) == before:
                        break
                    start += PAGE_SIZE
                    if on_progress:
                        on_progress(len(all_products), start // PAGE_SIZE)
                    if total and start >= total:
                        break
                    if start > 2000:
                        break
                except Exception:
                    break

            if not all_products:
                dom = page.evaluate(
                    """() => Array.from(document.querySelectorAll('a[href*=".html"]'))
                    .filter(a => /L\\d{5,}/.test(a.href))
                    .map(a => ({
                      href: a.href,
                      name: (a.innerText||'').trim().split('\\n')[0],
                      img: (() => { const i = a.querySelector('img'); return i?.currentSrc || i?.src || i?.dataset?.src || i?.getAttribute('data-src') || ''; })()
                    })).filter(x => x.name.length > 2)"""
                )
                for item in dom:
                    key = item["href"]
                    if key in seen:
                        continue
                    seen.add(key)
                    all_products.append(make_product_row(
                        brand="MONCLER",
                        main_category="명품",
                        category="여성 RTW",
                        gender="여성",
                        product_name=item["name"],
                        thumbnail=item.get("img", ""),
                        product_detail_url=item["href"],
                        crawled_at=crawled_at,
                    ))

            browser.close()

        if not all_products:
            raise RuntimeError(
                "MONCLER 상품을 수집하지 못했습니다. URL 또는 SearchApi 응답을 확인해주세요."
            )
        return all_products
