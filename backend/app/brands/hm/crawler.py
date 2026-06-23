"""H&M 브랜드 크롤러 (search-services API 캡처)"""

import json
import os
import re
import time
from pathlib import Path

from playwright.sync_api import sync_playwright

from app.brands.base import BaseBrandCrawler
from app.brands.browser_utils import dismiss_popups, launch_browser, new_stealth_context
from app.core.csv_schema import make_product_row, today_yymmdd


def parse_hm_product(prod: dict, crawled_at: str) -> dict | None:
    title = prod.get("title") or prod.get("productName") or prod.get("name") or ""
    if not title:
        return None
    pid = str(prod.get("articleCode") or prod.get("productId") or prod.get("id") or prod.get("code") or "")
    price = ""
    prices = prod.get("prices") or prod.get("price") or {}
    if isinstance(prices, dict):
        price = str(prices.get("price") or prices.get("value") or "")
    elif prices:
        price = str(prices)
    image = ""
    images = prod.get("images") or prod.get("image") or []
    if isinstance(images, list) and images:
        image = images[0].get("url") or images[0].get("src") or (images[0] if isinstance(images[0], str) else "")
    elif isinstance(images, dict):
        image = images.get("url") or images.get("src") or ""
    url = prod.get("url") or prod.get("link") or ""
    if pid and not url:
        url = f"https://www2.hm.com/ko_kr/productpage.{pid}.html"
    img = image if str(image).startswith("http") else ("https:" + str(image) if str(image).startswith("//") else "")
    price_clean = re.sub(r"[^\d]", "", price) or price
    return make_product_row(
        brand="H&M",
        product_name=title,
        gender="women",
        regular_price=price_clean,
        current_price=price_clean,
        color=prod.get("colorName") or prod.get("color") or "",
        thumbnail=img,
        rating=str(prod.get("rating") or prod.get("averageRating") or ""),
        reviews=str(prod.get("numberOfReviews") or prod.get("reviewCount") or ""),
        product_detail_url=url,
        crawled_at=crawled_at,
    )


def extract_hits(payload) -> list[dict]:
    hits: list[dict] = []
    if isinstance(payload, list):
        return [x for x in payload if isinstance(x, dict)]
    if not isinstance(payload, dict):
        return hits
    for key in ("results", "hits", "products", "items", "content"):
        val = payload.get(key)
        if isinstance(val, list):
            hits.extend(val)
        elif isinstance(val, dict):
            for sub in ("hits", "products", "items"):
                if isinstance(val.get(sub), list):
                    hits.extend(val[sub])
    plp = payload.get("plpList") or payload.get("productList")
    if isinstance(plp, dict):
        for sub in ("productList", "products", "hits"):
            if isinstance(plp.get(sub), list):
                hits.extend(plp[sub])
    return hits


def _storage_state_path() -> Path | None:
    raw = os.environ.get("HM_STORAGE_STATE", "").strip()
    if not raw:
        default = Path(__file__).resolve().parents[4] / "data" / "hm_storage_state.json"
        if default.is_file():
            return default
        return None
    path = Path(raw)
    return path if path.is_file() else None


LISTING_API = (
    "https://api.hm.com/search-services/v1/ko_kr/listing/resultpage"
    "?pageSource=PLP&page={page}&sort=RELEVANCE"
    "&pageId=/ladies/shop-by-product/view-all&page-size=36"
)


def fetch_listing_via_api(context, page_num: int, referer: str) -> dict | None:
    url = LISTING_API.format(page=page_num)
    try:
        resp = context.request.get(
            url,
            headers={"Accept": "application/json", "Referer": referer},
            timeout=60000,
        )
        if resp.ok:
            return resp.json()
    except Exception:
        pass
    return None


class HmCrawler(BaseBrandCrawler):
    brand_id = "hm"
    brand_name = "H&M"
    source_site = "hm.com"

    def crawl(
        self,
        url: str | None = None,
        headless: bool = True,
        on_progress=None,
    ) -> list[dict]:
        target_url = url or "https://www2.hm.com/ko_kr/ladies/shop-by-product/view-all.html"
        for attempt_headless in (headless, False) if headless else (False,):
            try:
                products = self._crawl_once(target_url, attempt_headless, on_progress)
                if products:
                    return products
            except RuntimeError:
                if attempt_headless is False:
                    raise
        raise RuntimeError(
            "H&M 사이트 접근이 차단되었습니다. 일반 Chrome에서 "
            "https://www2.hm.com/ko_kr/ 페이지가 열리는지 확인한 뒤, "
            "backend/scripts/hm_save_session.py 로 쿠키를 저장하거나 "
            "data/hm_storage_state.json 을 준비한 후 다시 시도해주세요."
        )

    def _crawl_once(
        self,
        target_url: str,
        headless: bool,
        on_progress=None,
    ) -> list[dict]:
        crawled_at = today_yymmdd()
        captured: list[dict] = []
        listing_urls: list[str] = []

        storage = _storage_state_path()

        with sync_playwright() as p:
            browser = launch_browser(p, headless=headless)
            if storage:
                context = browser.new_context(
                    viewport={"width": 1280, "height": 900},
                    locale="ko-KR",
                    storage_state=str(storage),
                )
                page = context.new_page()
                page.add_init_script(
                    "Object.defineProperty(navigator, 'webdriver', { get: () => undefined });"
                )
            else:
                context, page = new_stealth_context(browser)

            def on_response(response):
                u = response.url
                if response.status != 200:
                    return
                if "search-services" not in u and "hmwebservices" not in u:
                    return
                if "json" not in response.headers.get("content-type", ""):
                    return
                try:
                    captured.append(response.json())
                    if "search-services" in u and "page=" in u:
                        listing_urls.append(u.split("?")[0] + "?" + u.split("?")[1].split("&page=")[0].split("page=")[0])
                except Exception:
                    pass

            page.on("response", on_response)
            page.goto(target_url, wait_until="domcontentloaded", timeout=120000)
            dismiss_popups(page)
            page.wait_for_timeout(5000)

            title = page.title().lower()
            if "access denied" in title:
                products_from_api: list[dict] = []
                seen_api = set()
                for pg in range(1, 80):
                    payload = fetch_listing_via_api(context, pg, target_url)
                    if not payload:
                        break
                    batch = []
                    for hit in extract_hits(payload):
                        row = parse_hm_product(hit, crawled_at)
                        if row:
                            batch.append(row)
                    if not batch:
                        break
                    for row in batch:
                        key = row.get("product_detail_url") or row.get("product_name")
                        if key in seen_api:
                            continue
                        seen_api.add(key)
                        products_from_api.append(row)
                    if on_progress:
                        on_progress(len(products_from_api), pg)
                    pagination = payload.get("pagination") or {}
                    total_pages = pagination.get("totalPages") or pagination.get("total_pages")
                    if total_pages and pg >= int(total_pages):
                        break
                    if len(batch) < 36:
                        break
                if products_from_api:
                    browser.close()
                    return products_from_api
                browser.close()
                raise RuntimeError(
                    "H&M 사이트 접근이 차단되었습니다. 일반 Chrome에서 "
                    "https://www2.hm.com/ko_kr/ 페이지가 열리는지 확인한 뒤, "
                    "backend/scripts/hm_save_session.py 로 쿠키를 저장하거나 "
                    "data/hm_storage_state.json 을 준비한 후 다시 시도해주세요."
                )

            for _ in range(15):
                page.evaluate("window.scrollBy(0, window.innerHeight)")
                page.wait_for_timeout(1200)
                try:
                    btn = page.locator("button:has-text('더 보기'), button:has-text('Load more')").first
                    if btn.count() and btn.is_visible(timeout=1000):
                        btn.click()
                        page.wait_for_timeout(2000)
                except Exception:
                    pass

            products: list[dict] = []
            seen = set()
            for payload in captured:
                for hit in extract_hits(payload):
                    row = parse_hm_product(hit, crawled_at)
                    if not row:
                        continue
                    key = row.get("product_detail_url") or row.get("product_name")
                    if key in seen:
                        continue
                    seen.add(key)
                    products.append(row)

            if not products:
                dom = page.evaluate(
                    """() => Array.from(document.querySelectorAll('a[href*="productpage"]'))
                    .map(a => ({
                        href: a.href,
                        name: (a.querySelector('h2,h3,span')?.innerText || a.getAttribute('aria-label') || '').trim(),
                        img: (() => { const i = a.querySelector('img'); return i?.currentSrc || i?.src || i?.dataset?.src || i?.getAttribute('data-src') || ''; })(),
                        price: (a.innerText.match(/[\\d,]+\\s*원/) || [''])[0]
                    })).filter(x => x.name)"""
                )
                for item in dom:
                    m = re.search(r"productpage\.(\d+)", item["href"])
                    pid = m.group(1) if m else item["href"]
                    if pid in seen:
                        continue
                    seen.add(pid)
                    dom_img = item.get("img", "")
                    if dom_img and not dom_img.startswith("http"):
                        dom_img = "https:" + dom_img if dom_img.startswith("//") else ""
                    price_raw = re.sub(r"[^\d]", "", item.get("price", ""))
                    products.append(make_product_row(
                        brand="H&M",
                        product_name=item["name"],
                        gender="women",
                        regular_price=price_raw,
                        current_price=price_raw,
                        thumbnail=dom_img,
                        product_detail_url=item["href"],
                        crawled_at=crawled_at,
                    ))

            browser.close()

        if on_progress:
            on_progress(len(products), 1)

        if not products:
            raise RuntimeError("H&M 상품을 수집하지 못했습니다.")
        return products
