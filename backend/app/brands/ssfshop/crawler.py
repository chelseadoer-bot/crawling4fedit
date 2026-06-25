"""SSF SHOP (에잇세컨즈 등) 카테고리 크롤러"""

from __future__ import annotations

import json
import re
import time
import urllib.request
from urllib.parse import urlparse

from playwright.sync_api import Page, sync_playwright

from app.brands.base import BaseBrandCrawler
from app.brands.browser_utils import dismiss_popups, launch_browser, new_stealth_context
from app.core.csv_schema import make_product_row, today_yymmdd

SKIP_NAMES = {"바로가기", "전체 상품", "신상품순", "인기상품순", "낮은가격순", "높은가격순"}
PAGE_WAIT_MS = 2500
BLOCK_WAIT_MS = 2000
DETAIL_DELAY_SEC = 0.15
DETAIL_API = "https://www.ssfshop.com/public/goods/detail/{god_no}/view"

EXTRACT_PRODUCTS_JS = """() => {
    const out = [];
    const seen = new Set();
    for (const a of document.querySelectorAll('a[href*="/good"]')) {
        const href = a.href || '';
        if (!href.includes('GM00') || seen.has(href)) continue;
        const img = a.querySelector('img');
        let name = (img?.alt || a.getAttribute('aria-label') || '').trim();
        if (name.includes(',')) name = name.split(',')[0].trim();
        const card = a.closest('li, article, div') || a;
        const priceMatch = (card.innerText || '').match(/[\\d,]+\\s*원/);
        const godMatch = href.match(/GM\\d+/);
        seen.add(href);
        out.push({
            name,
            href,
            godNo: godMatch ? godMatch[0] : '',
            image: img?.currentSrc || img?.src || '',
            price: priceMatch ? priceMatch[0] : '',
        });
    }
    return out;
}"""

CLICK_PAGE_JS = """(pageNo) => {
    const el = document.querySelector(`#page_${pageNo}`)
        || document.querySelector(`a.btn_paging[pageno="${pageNo}"]`);
    if (!el || el.classList.contains('disabled')) return false;
    el.click();
    return true;
}"""

ADVANCE_PAGE_JS = """(nextPage) => {
    const direct = document.querySelector(`#page_${nextPage}`)
        || document.querySelector(`a.btn_paging[pageno="${nextPage}"]`);
    if (direct && !direct.classList.contains('disabled')) {
        direct.click();
        return 'direct';
    }
    const next = document.querySelector('#page_next:not(.disabled)');
    if (!next) return '';
    const target = next.getAttribute('pageno');
    if (target === String(nextPage)) {
        next.click();
        return 'next';
    }
    next.click();
    return 'shift';
}"""

_GOD_NO_RE = re.compile(r"(GM\d+)")


def normalize_ssf_url(url: str) -> str:
    parsed = urlparse(url)
    host = parsed.netloc.replace("m.", "www.")
    return f"{parsed.scheme}://{host}{parsed.path}?{parsed.query}" if parsed.query else f"{parsed.scheme}://{host}{parsed.path}"


def extract_god_no(href: str) -> str:
    match = _GOD_NO_RE.search(href or "")
    return match.group(1) if match else ""


def fetch_goods_detail(god_no: str) -> dict | None:
    if not god_no:
        return None
    req = urllib.request.Request(
        DETAIL_API.format(god_no=god_no),
        headers={"User-Agent": "Mozilla/5.0", "Accept": "application/json"},
    )
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except Exception:
        return None


def category_from_detail(detail: dict) -> str:
    goods = detail.get("goods") or {}
    names = [
        c.get("dspCtgryNm", "").strip()
        for c in (goods.get("cateNameList") or [])
        if isinstance(c, dict) and c.get("dspCtgryNm")
    ]
    return " > ".join(names)


def gender_from_detail(detail: dict) -> str:
    goods = detail.get("goods") or {}
    god = goods.get("god") or {}
    sex = (god.get("recomendSexCd") or "").strip()
    mapping = {"WOMEN": "여성", "MEN": "남성", "KIDS": "공용"}
    return mapping.get(sex.upper(), sex)


def material_from_detail(detail: dict) -> str:
    matr_map = detail.get("goodsMatrDscrInfoMap") or {}
    parts: list[str] = []
    for value in matr_map.values():
        if isinstance(value, list):
            parts.extend(str(x).strip() for x in value if x)
        elif value:
            parts.append(str(value).strip())
    return " | ".join(parts)


def rating_reviews_from_detail(detail: dict) -> tuple[str, str]:
    raw = detail.get("productJsonLd")
    if isinstance(raw, str):
        try:
            raw = json.loads(raw)
        except json.JSONDecodeError:
            raw = {}
    if not isinstance(raw, dict):
        raw = {}
    agg = raw.get("aggregateRating") or {}
    rating = agg.get("ratingValue")
    reviews = agg.get("reviewCount")
    if rating in (None, ""):
        goods = detail.get("goods") or {}
        count = goods.get("reviewCount") or 0
        if count:
            score = detail.get("score") or {}
            total = score.get("totalScore")
            if total not in (None, "", 0):
                rating = round(float(total) / 2, 1)
            reviews = count
    return (
        str(rating) if rating not in (None, "") else "",
        str(reviews) if reviews not in (None, "") else "",
    )


def price_pair_from_detail(detail: dict, fallback_price: str = "") -> tuple[str, str]:
    retail = detail.get("retail_price")
    sale = detail.get("sale_price")
    if retail in (None, "") and sale in (None, ""):
        goods = detail.get("goods") or {}
        god = goods.get("god") or {}
        retail = god.get("rtlPrc") or retail
        sale = god.get("lastSalePrc") or sale
    regular = str(int(retail)) if retail not in (None, "") else fallback_price
    current = ""
    if sale not in (None, "") and regular:
        try:
            if int(sale) < int(regular):
                current = str(int(sale))
        except (TypeError, ValueError):
            pass
    elif sale not in (None, "") and not regular:
        regular = str(int(sale))
    return regular, current


def detail_to_row(
    item: dict,
    detail: dict | None,
    label: str,
    crawled_at: str,
    category_fallback: str = "",
) -> dict:
    god_no = item.get("godNo") or extract_god_no(item.get("href", ""))
    fallback_price = re.sub(r"[^\d]", "", item.get("price", ""))
    regular, current = fallback_price, ""
    category = category_fallback
    gender = ""
    material = ""
    rating = ""
    reviews = ""

    if detail:
        regular, current = price_pair_from_detail(detail, fallback_price)
        category = category_from_detail(detail) or category_fallback
        gender = gender_from_detail(detail)
        material = material_from_detail(detail)
        rating, reviews = rating_reviews_from_detail(detail)

    name = (item.get("name") or "").strip()
    if not name and detail:
        goods = detail.get("goods") or {}
        name = (goods.get("godNm") or (goods.get("god") or {}).get("godNm") or "").strip()

    return make_product_row(
        brand=label,
        platform="",
        product_name=name,
        category=category,
        gender=gender,
        regular_price=regular,
        current_price=current,
        material=material,
        rating=rating,
        reviews=reviews,
        thumbnail=item.get("image", ""),
        product_detail_url=item.get("href", ""),
        crawled_at=crawled_at,
    )


def get_total_pages(page: Page) -> int:
    last = page.locator("#page_last")
    if last.count():
        raw = last.get_attribute("pageno") or last.inner_text()
        digits = re.sub(r"[^\d]", "", raw or "")
        if digits:
            return max(1, int(digits))
    match = re.search(r"([\d,]+)\s*개\s*상품", page.inner_text("body"))
    if match:
        total_products = int(re.sub(r"[^\d]", "", match.group(1)))
        return max(1, (total_products + 59) // 60)
    return 1


def advance_to_next_page(page: Page, next_page: int) -> bool:
    moved = page.evaluate(ADVANCE_PAGE_JS, next_page)
    if moved in {"direct", "next"}:
        page.wait_for_timeout(PAGE_WAIT_MS)
        return True
    if moved == "shift":
        page.wait_for_timeout(BLOCK_WAIT_MS)
        if page.evaluate(CLICK_PAGE_JS, next_page):
            page.wait_for_timeout(PAGE_WAIT_MS)
            return True
    return False


def extract_page_products(page: Page) -> list[dict]:
    return page.evaluate(EXTRACT_PRODUCTS_JS)


class SsfshopCrawler(BaseBrandCrawler):
    brand_id = "ssfshop"
    brand_name = "8SECONDS"
    source_site = "ssfshop.com"

    def crawl(
        self,
        url: str | None = None,
        headless: bool = True,
        on_progress=None,
        brand_name: str | None = None,
        category_name: str | None = None,
        **_,
    ) -> list[dict]:
        if not url:
            raise ValueError("SSF SHOP URL이 필요합니다.")
        target = normalize_ssf_url(url)
        label = brand_name or "8SECONDS"
        crawled_at = today_yymmdd()
        category_fallback = category_name or ""
        products: list[dict] = []
        seen: set[str] = set()
        detail_cache: dict[str, dict | None] = {}

        with sync_playwright() as p:
            browser = launch_browser(p, headless=headless)
            _, page = new_stealth_context(browser)
            page.goto(target, wait_until="domcontentloaded", timeout=120000)
            dismiss_popups(page)
            page.wait_for_timeout(3500)

            total_pages = get_total_pages(page)

            for page_no in range(1, total_pages + 1):
                if page_no > 1 and not advance_to_next_page(page, page_no):
                    break

                for item in extract_page_products(page):
                    name = (item.get("name") or "").strip()
                    if not name or name in SKIP_NAMES or len(name) < 3:
                        continue
                    href = item.get("href", "")
                    if not href or href in seen:
                        continue
                    seen.add(href)

                    god_no = item.get("godNo") or extract_god_no(href)
                    if god_no not in detail_cache:
                        detail_cache[god_no] = fetch_goods_detail(god_no)
                        time.sleep(DETAIL_DELAY_SEC)

                    products.append(
                        detail_to_row(
                            item,
                            detail_cache.get(god_no),
                            label,
                            crawled_at,
                            category_fallback,
                        )
                    )

                if on_progress:
                    on_progress(len(products), page_no)

            browser.close()

        if not products:
            raise RuntimeError(f"SSF SHOP 상품을 수집하지 못했습니다: {url}")
        return products
