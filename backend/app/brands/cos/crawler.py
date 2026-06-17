"""COS 브랜드 크롤러 (categoryProductList API)"""

import json
import re
import time
from urllib.parse import parse_qs, urlparse

from playwright.sync_api import sync_playwright

from app.brands.base import BaseBrandCrawler
from app.brands.browser_utils import dismiss_popups, launch_browser, new_stealth_context
from app.core.csv_schema import make_product_row, today_yymmdd

BASE = "https://www.cos.com"
LIST_API = (
    "https://www.cos.com/ko-kr/proxy/v1/dp/gbModule/categoryProductList"
    "?sectId={sect_id}&pageSize={page_size}&pageNum={page_num}&sectDispGbcd=10"
    "&sectDispSiteCd=&preview=false&searchSort=disp_prty&isFilterYn=0"
)
PAGE_SIZE = 36
VIEW_ALL_SECT_ID = "252012"


def parse_sect_id(url: str) -> str:
    parsed = urlparse(url)
    if "view-all" in parsed.path:
        return VIEW_ALL_SECT_ID
    params = parse_qs(parsed.query)
    return params.get("sectId", [VIEW_ALL_SECT_ID])[0]


def extract_products_from_payload(raw: str, crawled_at: str) -> list[dict]:
    """API 응답(JSON 문자열)에서 상품 추출"""
    products: list[dict] = []
    seen: set[str] = set()

    # 중첩 JSON / HTML 혼합 응답 대응
    blocks = re.findall(r'\{[^{}]*"godNo"\s*:\s*"?(\d+)"?[^{}]*\}', raw)
    if not blocks:
        # godNo 기준으로 청크 분리
        for chunk in re.split(r'(?="godNo")', raw):
            if '"godNo"' not in chunk:
                continue
            god = re.search(r'"godNo"\s*:\s*"?(\d+)"?', chunk)
            if not god:
                continue
            pid = god.group(1)
            if pid in seen:
                continue
            name = re.search(r'"gdasNm"\s*:\s*"([^"\\]+)"', chunk)
            price = re.search(r'"sellPrc"\s*:\s*(\d+)', chunk)
            img = re.search(r'"(?:repImg|imgUrl|imageUrl)"\s*:\s*"([^"\\]+)"', chunk)
            link = re.search(r'"(?:godDetailUrl|productUrl|linkUrl)"\s*:\s*"([^"\\]+)"', chunk)
            if not name:
                continue
            seen.add(pid)
            img_url = img.group(1) if img else ""
            if img_url.startswith("/"):
                img_url = BASE + img_url
            prod_url = link.group(1) if link else f"{BASE}/ko-kr/product/{pid}"
            if prod_url.startswith("/"):
                prod_url = BASE + prod_url
            if img_url and not img_url.startswith("http"):
                img_url = "https:" + img_url if img_url.startswith("//") else ""
            price_val = price.group(1) if price else ""
            products.append(make_product_row(
                brand="COS",
                product_name=name.group(1),
                gender="women",
                regular_price=price_val,
                current_price=price_val,
                thumbnail=img_url,
                product_detail_url=prod_url,
                crawled_at=crawled_at,
            ))
        return products

    return products


def parse_products_from_list(items: list, crawled_at: str) -> list[dict]:
    products: list[dict] = []
    seen: set[str] = set()
    for item in items:
        if not isinstance(item, dict):
            continue
        pid = str(
            item.get("slitmCd") or item.get("godNo") or item.get("productId") or item.get("id") or ""
        )
        name = (
            item.get("slitmNm")
            or item.get("gdasNm")
            or item.get("productName")
            or item.get("name")
            or ""
        )
        if not pid or not name or pid in seen:
            continue
        seen.add(pid)
        price = str(item.get("sellPrc") or item.get("price") or "")
        img = (
            item.get("imgPath")
            or item.get("repImg")
            or item.get("imgUrl")
            or item.get("imageUrl")
            or item.get("itemImgUrl")
            or ""
        )
        if isinstance(img, str) and img.startswith("/"):
            img = BASE + img
        url = (
            item.get("godDetailUrl")
            or item.get("productUrl")
            or item.get("itemUrl")
            or f"{BASE}/ko-kr/product/{pid}"
        )
        if isinstance(url, str) and url.startswith("/"):
            url = BASE + url
        img_str = img if isinstance(img, str) else ""
        if img_str and not img_str.startswith("http"):
            img_str = "https:" + img_str if img_str.startswith("//") else ""
        products.append(make_product_row(
            brand="COS",
            product_name=str(name),
            gender="women",
            regular_price=price,
            current_price=price,
            thumbnail=img_str,
            product_detail_url=url,
            crawled_at=crawled_at,
        ))
    return products


def find_product_list(data) -> list:
    if isinstance(data, list):
        return data
    if not isinstance(data, dict):
        return []
    for key in ("itemList", "productList", "products", "list", "content", "rows"):
        val = data.get(key)
        if isinstance(val, list) and val:
            return val
    for val in data.values():
        if isinstance(val, list) and val and isinstance(val[0], dict):
            if any(k in val[0] for k in ("slitmCd", "godNo", "gdasNm", "slitmNm", "productName")):
                return val
    return []


def get_total_count(data: dict) -> int | None:
    for key in ("totalCount", "slitmCount", "total"):
        val = data.get(key)
        if isinstance(val, int):
            return val
        if isinstance(val, str) and val.isdigit():
            return int(val)
    return None


class CosCrawler(BaseBrandCrawler):
    brand_id = "cos"
    brand_name = "COS"
    source_site = "cos.com"

    def crawl(
        self,
        url: str | None = None,
        headless: bool = True,
        on_progress=None,
    ) -> list[dict]:
        target_url = url or f"{BASE}/ko-kr/women/view-all.html"
        sect_id = parse_sect_id(target_url)
        crawled_at = today_yymmdd()
        all_products: list[dict] = []
        seen: set[str] = set()
        page_num = 1

        with sync_playwright() as p:
            browser = launch_browser(p, headless=headless)
            context, page = new_stealth_context(browser)
            page.goto(target_url, wait_until="domcontentloaded", timeout=120000)
            dismiss_popups(page)
            page.wait_for_timeout(4000)

            while page_num <= 200:
                api_url = LIST_API.format(
                    sect_id=sect_id, page_size=PAGE_SIZE, page_num=page_num
                )
                result = page.evaluate(
                    """async (url) => {
                    try {
                        const res = await fetch(url, { credentials: 'include', headers: { Accept: 'application/json' } });
                        const text = await res.text();
                        return { ok: res.ok, text };
                    } catch (e) {
                        return { ok: false, text: '' };
                    }
                }""",
                    api_url,
                )
                if not result.get("ok") or not result.get("text"):
                    break

                raw = result["text"]
                batch: list[dict] = []
                try:
                    payload = json.loads(raw)
                    data = payload.get("data") or {}
                    items = find_product_list(data)
                    batch = parse_products_from_list(items, crawled_at)
                    total = get_total_count(data)
                except json.JSONDecodeError:
                    batch = []
                    total = None
                if not batch:
                    batch = extract_products_from_payload(raw, crawled_at)

                if not batch:
                    break

                for row in batch:
                    key = row.get("product_detail_url") or row.get("product_name")
                    if key in seen:
                        continue
                    seen.add(key)
                    all_products.append(row)

                if on_progress:
                    on_progress(len(all_products), page_num)

                if len(batch) < PAGE_SIZE:
                    break
                if total is not None and len(all_products) >= total:
                    break
                page_num += 1
                time.sleep(0.3)

            if not all_products:
                # DOM 폴백
                cards = page.evaluate(
                    """() => Array.from(document.querySelectorAll('a[href*="/product/"], a[href*="product"]'))
                    .map(a => ({
                        name: (a.getAttribute('aria-label') || a.innerText || '').trim(),
                        href: a.href,
                        img: a.querySelector('img')?.src || ''
                    })).filter(x => x.name && x.href)"""
                )
                for c in cards:
                    pid = re.search(r"/(\d{5,})", c["href"])
                    pid = pid.group(1) if pid else c["href"]
                    if pid in seen:
                        continue
                    seen.add(pid)
                    dom_img = c.get("img", "")
                    if dom_img and not dom_img.startswith("http"):
                        dom_img = "https:" + dom_img if dom_img.startswith("//") else ""
                    all_products.append(make_product_row(
                        brand="COS",
                        product_name=c["name"],
                        gender="women",
                        thumbnail=dom_img,
                        product_detail_url=c["href"],
                        crawled_at=crawled_at,
                    ))

            browser.close()

        if not all_products:
            raise RuntimeError("COS 상품을 수집하지 못했습니다.")
        return all_products
