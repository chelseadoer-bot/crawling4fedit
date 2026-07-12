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

# ── 목록 HTML 폴백(할인가 보강)용 패턴 ────────────────────────────────────────
# 상품 블록: <li id="anchorBoxId_{product_no}" ...> ... (다음 anchorBoxId 직전까지)
_PRODUCT_BLOCK_RE = re.compile(r'<li id="anchorBoxId_(\d+)"(.*?)(?=<li id="anchorBoxId_|\Z)', re.S)
# "(1,590원 할인)" 같은 할인액 표기는 가격 후보에서 제외해야 오탐(min이 할인액이 되는 사고)이 없음
_DISCOUNT_AMOUNT_RE = re.compile(r"\([\d,]+\s*원\s*할인\)")
_PRICE_WON_RE = re.compile(r"([\d,]{3,})\s*원")
_PRICE_KRW_SYM_RE = re.compile(r"₩\s*([\d,]{3,})")


def extract_html_price_map(html: str) -> dict[str, tuple[str, str, str]]:
    """목록 HTML에서 상품 블록별 (정가, 할인가, 할인율) 후보를 추출.

    블록 안의 원화 가격을 모두 모아 서로 다른 값이 2개 이상이면
    최대값=정가, 최소값=할인가로 간주한다. 할인율은 두 값으로 직접 계산한다
    (블록 내 "NN%" 텍스트는 쿠폰/한정수량 등 무관한 값과 섞여 신뢰할 수 없음).
    """
    result: dict[str, tuple[str, str, str]] = {}
    for product_no, block in _PRODUCT_BLOCK_RE.findall(html):
        cleaned = _DISCOUNT_AMOUNT_RE.sub("", block)
        nums: set[int] = set()
        for m in _PRICE_WON_RE.findall(cleaned):
            nums.add(int(m.replace(",", "")))
        for m in _PRICE_KRW_SYM_RE.findall(cleaned):
            nums.add(int(m.replace(",", "")))
        if len(nums) < 2:
            continue
        hi, lo = max(nums), min(nums)
        if hi <= lo or lo <= 0:
            continue
        discount_rate = str(round((hi - lo) / hi * 100))
        result[product_no] = (str(hi), str(lo), discount_rate)
    return result


def fetch_list_html(base: str, cate_no: str, page: int, referer: str | None = None) -> str:
    url = f"{list_page_url(base, cate_no)}&page={page}"
    headers = {**UA, "Referer": referer or list_page_url(base, cate_no)}
    req = urllib.request.Request(url, headers=headers)
    with urllib.request.urlopen(req, timeout=30) as resp:
        return resp.read().decode("utf-8", "ignore")


def enrich_discounts_from_html(
    products: list[dict], base: str, cate_no: str, referer: str | None = None
) -> int:
    """목록 HTML을 다시 훑어 product_no 매칭으로 regular_price/current_price를 보강.
    make_product_row는 재호출하지 않고 기존 행의 값만 교체한다."""
    by_pid: dict[str, dict] = {}
    for row in products:
        m = re.search(r"product_no=(\d+)", row.get("product_detail_url") or "")
        if m:
            by_pid.setdefault(m.group(1), row)
    if not by_pid:
        return 0

    remaining = set(by_pid.keys())
    # 목록 HTML 페이지 크기가 API(PAGE_SIZE)와 다를 수 있어 넉넉히 상한만 둔다.
    max_pages = min(60, max(5, (len(products) // 15) + 3))
    matched = 0
    page = 1
    while remaining and page <= max_pages:
        html = fetch_list_html(base, cate_no, page, referer=referer)
        price_map = extract_html_price_map(html)
        if not price_map:
            break  # 더 이상 상품 블록이 없는 마지막 페이지
        for product_no, (regular, sale, discount_rate) in price_map.items():
            row = by_pid.get(product_no)
            if not row or product_no not in remaining:
                continue
            row["regular_price"] = regular
            row["current_price"] = sale
            row["discount_rate"] = discount_rate
            remaining.discard(product_no)
            matched += 1
        page += 1
        time.sleep(REQUEST_DELAY_SEC)
    return matched


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


def price_pair(item: dict) -> tuple[str, str]:
    regular = str(item.get("product_price") or item.get("price") or "").split(".")[0]
    sale = str(item.get("sale_price") or "").split(".")[0]
    if regular and sale:
        try:
            if int(sale) < int(regular):
                return regular, sale
        except (TypeError, ValueError):
            pass
    if regular:
        return regular, ""
    return sale, ""


def list_page_url(base: str, cate_no: str) -> str:
    return f"{base}/product/list.html?cate_no={cate_no}"


def _url_ok(url: str) -> bool:
    try:
        req = urllib.request.Request(url, headers=UA)
        with urllib.request.urlopen(req, timeout=8) as resp:
            return resp.status == 200
    except Exception:
        return False


def resolve_image_cdn_prefix(detail_url: str) -> str | None:
    """일부 몰은 자체 도메인 /web/product/ 이미지가 404 (cafe24img CDN으로 이전).
    상품 페이지 og:image에서 CDN 프리픽스(…/web/product/ 앞부분)를 추출."""
    try:
        req = urllib.request.Request(detail_url, headers=UA)
        html = urllib.request.urlopen(req, timeout=15).read().decode("utf-8", "ignore")
    except Exception:
        return None
    m = re.search(r'og:image"\s+content="([^"]+)"', html) or re.search(r'content="([^"]+)"[^>]*og:image', html)
    if not m:
        return None
    og = m.group(1)
    idx = og.find("/web/product/")
    return og[:idx] if idx > 0 else None


def fix_broken_thumbnails(products: list[dict]) -> None:
    """첫 썸네일이 404면 CDN 프리픽스로 전체 썸네일 경로 재작성."""
    first = next((p for p in products if (p.get("thumbnail") or "").startswith("http")), None)
    if not first or "/web/product/" not in first["thumbnail"]:
        return
    if _url_ok(first["thumbnail"]):
        return
    cdn = resolve_image_cdn_prefix(first.get("product_detail_url") or "")
    if not cdn:
        return
    for p in products:
        t = p.get("thumbnail") or ""
        idx = t.find("/web/product/")
        if t.startswith("http") and idx > 0:
            p["thumbnail"] = cdn + t[idx:]


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


def item_to_row(item: dict, base: str, brand_name: str, crawled_at: str, category: str = "") -> dict:
    name = strip_html(item.get("product_name") or item.get("product_name_tag") or "")
    regular, current = price_pair(item)
    product_no = str(item.get("product_no") or "")
    image = item.get("image_medium") or item.get("image_big") or item.get("image_small") or ""
    if image.startswith("//"):
        image = "https:" + image
    elif image.startswith("/"):
        image = base + image
    if " " in image:
        image = urllib.parse.quote(image, safe=":/?&=%")

    detail_url = f"{base}/product/detail.html?product_no={product_no}" if product_no else ""

    return make_product_row(
        brand=brand_name,
        platform="",
        product_name=name,
        category=category,
        regular_price=regular,
        current_price=current,
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
        category_name: str | None = None,
        **_,
    ) -> list[dict]:
        if not url:
            raise ValueError("Cafe24 크롤 URL이 필요합니다.")
        base = site_base(url)
        cate_no = parse_cate_no(url)
        label = brand_label_from_url(url, brand_name or "")
        category = category_name or ""
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
                products.append(item_to_row(item, base, label, crawled_at, category))

            if on_progress:
                on_progress(len(products), page_num)

            if len(items) < PAGE_SIZE:
                break
            page_num += 1
            time.sleep(REQUEST_DELAY_SEC)

        fix_broken_thumbnails(products)

        # API가 sale_price를 안 내려주는 몰 대응: 할인 수집이 0건이면 목록 HTML을 다시 훑어 보강
        if products and not any(p.get("current_price") for p in products):
            try:
                enrich_discounts_from_html(products, base, cate_no, referer=referer)
            except Exception:
                pass

        return products
