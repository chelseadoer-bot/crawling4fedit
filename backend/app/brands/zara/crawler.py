"""ZARA 브랜드 크롤러 — spec v3 (26컬럼)"""

from __future__ import annotations

import csv
import json
import random
import re
import time
from datetime import datetime
from pathlib import Path
from typing import Callable

from playwright.sync_api import sync_playwright

from app.brands.base import BaseBrandCrawler
from app.core.csv_schema import _clean

CONFIG_PATH = Path(__file__).parent / "config.json"

# ── 스펙 v3: 26컬럼 순서 ─────────────────────────────────────────────────────
SPEC_COLUMNS = [
    "platform",
    "is_ranking",
    "rank",
    "brand",
    "brand_likes",
    "main_category",
    "category",
    "gender",
    "product_detail_url",
    "product_name",
    "color",
    "color_chip",
    "thumbnail",
    "likes",
    "views",
    "details",
    "material",
    "current_price",
    "regular_price",
    "discount_rate",
    "rating",
    "reviews",
    "sales",
    "manufacture_date",
    "crawled_at",
    "reorder",
]

USER_AGENTS = [
    (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/131.0.0.0 Safari/537.36"
    ),
    (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/130.0.0.0 Safari/537.36"
    ),
    (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/129.0.0.0 Safari/537.36 Edg/129.0.0.0"
    ),
]

# 한국어 수량 파싱 (만, 천)
_KO_NUM_RE = re.compile(r"(\d+(?:\.\d+)?)\s*([만천]?)")
_SALES_RE = re.compile(r"\[([0-9]+(?:\.[0-9]+)?[만천]?)장?\s*판매\]", re.IGNORECASE)
_REORDER_RE = re.compile(r"\[([0-9]+)차\s*재입고\]", re.IGNORECASE)


def parse_ko_number(s: str) -> int:
    s = s.strip()
    m = _KO_NUM_RE.fullmatch(s)
    if not m:
        return 0
    num = float(m.group(1))
    unit = m.group(2)
    if unit == "만":
        return int(num * 10000)
    if unit == "천":
        return int(num * 1000)
    return int(num)


def parse_product_name(raw_name: str) -> tuple[str, str, str]:
    """(cleaned_name, sales_str, reorder_str)"""
    name = raw_name or ""
    sales = ""
    reorder = ""

    m_sales = _SALES_RE.search(name)
    if m_sales:
        sales = str(parse_ko_number(m_sales.group(1)))
        name = _SALES_RE.sub("", name)

    m_reorder = _REORDER_RE.search(name)
    if m_reorder:
        reorder = m_reorder.group(1)
        name = _REORDER_RE.sub("", name)

    name = re.sub(r"\s{2,}", " ", name).strip()
    return name, sales, reorder


def crawled_at_yymmdd() -> str:
    return datetime.now().strftime("%y%m%d")


def normalize_price(price_val) -> str:
    if price_val is None or price_val == "":
        return ""
    raw = str(price_val).replace(",", "").replace("₩", "").strip()
    digits = re.sub(r"[^0-9]", "", raw)
    if not digits:
        return ""
    val = int(digits)
    # ZARA API 가끔 센트 단위(×100)로 오는 경우 보정
    if val > 1_000_000 and val % 100 == 0:
        val = val // 100
    return str(val)


def calc_discount_rate(current: str, regular: str) -> str:
    try:
        c, r = int(current), int(regular)
        if r > 0 and c < r:
            return str(round((r - c) / r * 100))
    except (ValueError, ZeroDivisionError):
        pass
    return ""


def upgrade_image_url(url: str) -> str:
    if not url:
        return ""
    if "{width}" in url:
        url = url.replace("{width}", "1280")
    if "msscdn.net" in url and "?w=" not in url:
        url = url + "?w=1280"
    if "imagedelivery.net" in url:
        url = re.sub(r"/w=\d+", "/w=1920", url)
        url = re.sub(r"/h=\d+", "/h=1920", url)
    if url.startswith("//"):
        url = "https:" + url
    return url


def load_config() -> dict:
    with CONFIG_PATH.open(encoding="utf-8") as f:
        return json.load(f)


def extract_category_id(url: str) -> str | None:
    m = re.search(r"[?&]v1=(\d+)", url)
    return m.group(1) if m else None


def dismiss_popups(page) -> None:
    for selector in [
        "#onetrust-accept-btn-handler",
        "button:has-text('동의')",
        "button:has-text('Accept')",
        "button:has-text('닫기')",
    ]:
        btn = page.locator(selector).first
        try:
            if btn.count() and btn.is_visible(timeout=1000):
                btn.click()
                page.wait_for_timeout(500)
                break
        except Exception:
            pass


def auto_scroll_to_bottom(page, max_rounds: int = 60, pause_ms: int = 800) -> None:
    prev_count = 0
    stable = 0
    for _ in range(max_rounds):
        page.evaluate("window.scrollBy(0, window.innerHeight * 0.85)")
        page.wait_for_timeout(pause_ms)
        cnt = page.locator(
            ".product-grid-product-info, li.product-grid-product"
        ).count()
        at_bottom = page.evaluate(
            "window.scrollY + window.innerHeight >= document.body.scrollHeight - 50"
        )
        if cnt == prev_count and at_bottom:
            stable += 1
        else:
            stable = 0
            prev_count = cnt
        if stable >= 3:
            break
    page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
    page.wait_for_timeout(800)


def parse_composition(comp) -> str:
    """ZARA API 소재 구성 → 문자열"""
    if not comp:
        return ""
    if isinstance(comp, str):
        return comp.strip()
    if isinstance(comp, list):
        parts = []
        for item in comp:
            if isinstance(item, dict):
                part_name = item.get("part", "")
                comps = item.get("components", [])
                if comps:
                    pieces = []
                    for c in comps:
                        name = c.get("name", "")
                        pct = c.get("percentage", "")
                        if name and pct:
                            pieces.append(f"{name} {pct}%")
                        elif name:
                            pieces.append(name)
                    joined = ", ".join(pieces)
                    parts.append(f"{part_name}: {joined}" if part_name else joined)
            else:
                parts.append(str(item))
        return " / ".join(parts)
    return str(comp).strip()


def extract_colors(component: dict) -> tuple[str, str, str]:
    """(color_names, color_chip_url, thumbnail_url)"""
    colors_detail = component.get("detail", {}).get("colors", [])
    names: list[str] = []
    chip_url = ""
    thumb_url = ""

    for i, color in enumerate(colors_detail):
        name = (color.get("name") or "").strip()
        if name and name not in names:
            names.append(name)

        for media in color.get("xmedia", []):
            raw_url = (
                media.get("extraInfo", {}).get("deliveryUrl")
                or media.get("url", "")
            )
            if not raw_url:
                continue
            hq = upgrade_image_url(raw_url)
            if i == 0 and not thumb_url:
                thumb_url = hq
            if not chip_url:
                chip_url = hq

    if not chip_url:
        chip_url = thumb_url

    if not thumb_url:
        for media in component.get("xmedia", []):
            raw_url = (
                media.get("extraInfo", {}).get("deliveryUrl")
                or media.get("url", "")
            )
            if raw_url:
                thumb_url = upgrade_image_url(raw_url)
                chip_url = thumb_url
                break

    return ", ".join(names), chip_url, thumb_url


def extract_detail_info(component: dict) -> tuple[str, str]:
    """(details, material)"""
    detail = component.get("detail", {})
    material = parse_composition(
        detail.get("composition") or detail.get("material") or ""
    )
    if not material:
        desc = component.get("description") or ""
        if isinstance(desc, list):
            desc = " ".join(str(d) for d in desc)
        material = str(desc).strip()

    info_parts: list[str] = []
    for key in ("fit", "season", "thickness", "washing", "care"):
        val = detail.get(key) or ""
        if val:
            if isinstance(val, list):
                val = ", ".join(str(v) for v in val)
            info_parts.append(str(val).strip())

    desc_text = component.get("description") or ""
    if isinstance(desc_text, list):
        desc_text = " ".join(str(d) for d in desc_text)
    desc_text = str(desc_text).strip()
    if desc_text and desc_text not in info_parts:
        info_parts.append(desc_text)

    details = " | ".join(p for p in info_parts if p)
    return details, material


def component_to_spec_row(component: dict, config: dict, crawled_at: str) -> dict:
    ref = component.get("reference") or f"ZR-{component.get('id', '')}"
    product_url = f"https://www.zara.com/kr/ko/-p{ref}.html" if ref else ""

    raw_name = (component.get("name") or "").strip()
    product_name, sales, reorder = parse_product_name(raw_name)

    color, color_chip, thumbnail = extract_colors(component)
    details, material = extract_detail_info(component)

    current_price = normalize_price(component.get("price"))
    regular_price = normalize_price(component.get("oldPrice")) or current_price
    discount_rate = calc_discount_rate(current_price, regular_price)

    gender_hint = config.get("gender", "women")
    url_lower = config.get("default_url", "").lower()
    # "woman"에 "man"이 포함되므로 /man/ 또는 /men/ 패턴으로 체크
    if re.search(r"[/-](man|men|hombre)[/-]", url_lower):
        gender_hint = "men"
    elif re.search(r"[/-](kid|kids|bebe|nino)[/-]", url_lower):
        gender_hint = "kids"

    sub_category = (
        component.get("familyName")
        or component.get("sectionName")
        or component.get("kindName")
        or ""
    )

    return {
        "platform": "",
        "is_ranking": "false",
        "rank": "",
        "brand": "ZARA",
        "brand_likes": "",
        "main_category": config.get("main_category", "SPA해외"),
        "category": sub_category,
        "gender": gender_hint,
        "product_detail_url": product_url,
        "product_name": product_name,
        "color": color,
        "color_chip": color_chip,
        "thumbnail": thumbnail,
        "likes": "",
        "views": "",
        "details": details,
        "material": material,
        "current_price": current_price,
        "regular_price": regular_price,
        "discount_rate": discount_rate,
        "rating": "",
        "reviews": "",
        "sales": sales,
        "manufacture_date": "",
        "crawled_at": crawled_at,
        "reorder": reorder,
    }


def spec_to_simple(row: dict) -> dict:
    """spec row → SIMPLE_COLUMNS 호환 dict (프론트엔드 미리보기 / save_simple_csv용)"""
    return {
        "front_images_url": row.get("thumbnail", ""),
        "product_name": row.get("product_name", ""),
        "brand": row.get("brand", "ZARA"),
        "category": row.get("category", ""),
        "gender": row.get("gender", ""),
        "regular_price": row.get("regular_price", ""),
        "current_price": row.get("current_price", ""),
        "discount_rate": row.get("discount_rate", ""),
        "color_text": row.get("color", ""),
        "color_chip": row.get("color_chip", ""),
        "color_classification_url": "",
        "material": row.get("material", ""),
        "details": row.get("details", ""),
        "rating": row.get("rating", ""),
        "reviews": row.get("reviews", ""),
        "product_detail_url": row.get("product_detail_url", ""),
        "sizes_available": "",
        "fit": "",
        "length": "",
        "sleeve_length": "",
        "style": "",
        "lining": "",
        "thickness": "",
        "season": "",
        "transparency": "",
        "elasticity": "",
        "crawled_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "source_site": "zara.com",
    }


def parse_products_from_api(
    data: dict, config: dict, crawled_at: str, seen: set
) -> list[dict]:
    rows = []
    for group in data.get("productGroups", []):
        for element in group.get("elements", []):
            for comp in element.get("commercialComponents", []):
                if comp.get("type") != "Product":
                    continue
                pid = comp.get("id")
                if pid in seen:
                    continue
                seen.add(pid)
                rows.append(component_to_spec_row(comp, config, crawled_at))
    return rows


def extract_products_from_dom(page, config: dict, crawled_at: str) -> list[dict]:
    raw_items = page.evaluate(
        """() => {
        const blocks = document.querySelectorAll('.product-grid-product-info');
        return Array.from(blocks).map(block => {
            const nameEl = block.querySelector('.product-grid-product-info__name h3, .product-grid-product-info__name');
            const linkEl = nameEl?.closest('a') || block.querySelector('a.product-link');
            const name = nameEl?.innerText?.trim() || '';
            const priceText = block.querySelector('.money-amount__main, .price-current__amount')?.innerText?.trim() || '';
            const price = priceText.replace(/[^0-9]/g, '');
            const colors = Array.from(block.querySelectorAll('[aria-label][class*="color"]'))
                .map(el => el.getAttribute('aria-label') || '')
                .filter(Boolean);
            const img = block.closest('li')?.querySelector('img')?.src || '';
            const url = linkEl?.href || '';
            return { name, price, colors, img, url };
        }).filter(item => item.name);
    }"""
    )

    rows = []
    seen: set = set()
    for item in raw_items:
        key = item.get("name", "")
        if key in seen:
            continue
        seen.add(key)

        product_name, sales, reorder = parse_product_name(key)
        thumbnail = upgrade_image_url(item.get("img", ""))
        current_price = re.sub(r"[^0-9]", "", item.get("price", ""))

        rows.append({
            "platform": "",
            "is_ranking": "false",
            "rank": "",
            "brand": "ZARA",
            "brand_likes": "",
            "main_category": config.get("main_category", "SPA해외"),
            "category": "",
            "gender": config.get("gender", "women"),
            "product_detail_url": item.get("url", ""),
            "product_name": product_name,
            "color": ", ".join(item.get("colors", [])),
            "color_chip": "",
            "thumbnail": thumbnail,
            "likes": "",
            "views": "",
            "details": "",
            "material": "",
            "current_price": current_price,
            "regular_price": current_price,
            "discount_rate": "",
            "rating": "",
            "reviews": "",
            "sales": sales,
            "manufacture_date": "",
            "crawled_at": crawled_at,
            "reorder": reorder,
        })

    return rows


def save_spec_csv(rows: list[dict], output_dir: Path) -> Path:
    """spec v3 형식 CSV → data/output/brand/spa_global/zara_{YYYYMMDD}.csv"""
    today = datetime.now().strftime("%Y%m%d")
    out_path = output_dir / "brand" / "spa_global" / f"zara_{today}.csv"
    out_path.parent.mkdir(parents=True, exist_ok=True)

    with out_path.open("w", newline="", encoding="utf-8-sig") as f:
        writer = csv.writer(f, lineterminator="\n", quoting=csv.QUOTE_MINIMAL)
        writer.writerow(SPEC_COLUMNS)
        for row in rows:
            writer.writerow([_clean(row.get(col, "")) for col in SPEC_COLUMNS])

    return out_path


class ZaraCrawler(BaseBrandCrawler):
    brand_id = "zara"
    brand_name = "ZARA"
    source_site = "zara.com"

    def crawl(
        self,
        url: str | None = None,
        headless: bool = True,
        on_progress: Callable[[int, int], None] | None = None,
    ) -> list[dict]:
        config = load_config()
        target_url = url or config.get("default_url", "")
        category_id = extract_category_id(target_url) or config.get(
            "default_category_id", ""
        )
        api_url = (
            f"https://www.zara.com/kr/ko/category/{category_id}/products?ajax=true"
        )
        crawled_at = crawled_at_yymmdd()
        ua = random.choice(USER_AGENTS)

        spec_rows: list[dict] = []

        with sync_playwright() as p:
            browser = p.chromium.launch(
                headless=headless,
                args=["--disable-blink-features=AutomationControlled"],
            )
            context = browser.new_context(
                viewport={"width": 1280, "height": 900},
                user_agent=ua,
                locale="ko-KR",
                extra_http_headers={
                    "Accept-Language": "ko-KR,ko;q=0.9,en-US;q=0.8"
                },
            )
            page = context.new_page()
            page.add_init_script(
                "Object.defineProperty(navigator, 'webdriver', {get:()=>undefined});"
            )

            time.sleep(random.uniform(1.0, 2.5))

            try:
                page.goto(target_url, wait_until="domcontentloaded", timeout=60000)
                page.wait_for_timeout(random.randint(1500, 3000))
                dismiss_popups(page)
                auto_scroll_to_bottom(page)
            except Exception:
                pass

            seen: set = set()

            # 1차: AJAX API
            try:
                time.sleep(random.uniform(0.5, 1.5))
                response = context.request.get(
                    api_url,
                    headers={"Accept": "application/json", "Referer": target_url},
                )
                if response.ok:
                    spec_rows = parse_products_from_api(
                        response.json(), config, crawled_at, seen
                    )
            except Exception:
                pass

            # 2차: DOM fallback
            if not spec_rows:
                spec_rows = extract_products_from_dom(page, config, crawled_at)

            if on_progress:
                on_progress(len(spec_rows), 1)

            # 추가 카테고리 (config.extra_urls)
            for extra_url in config.get("extra_urls", []):
                extra_id = extract_category_id(extra_url)
                if not extra_id:
                    continue
                extra_api = (
                    f"https://www.zara.com/kr/ko/category/{extra_id}/products?ajax=true"
                )
                time.sleep(random.uniform(1.5, 3.5))
                try:
                    res = context.request.get(
                        extra_api, headers={"Referer": extra_url}
                    )
                    if res.ok:
                        spec_rows.extend(
                            parse_products_from_api(
                                res.json(), config, crawled_at, seen
                            )
                        )
                except Exception:
                    pass
                if on_progress:
                    on_progress(len(spec_rows), 1)

            browser.close()

        if on_progress:
            on_progress(len(spec_rows), 1)

        # spec v3 CSV 별도 저장
        try:
            from app.brands.registry import PROJECT_ROOT

            save_spec_csv(spec_rows, PROJECT_ROOT / "data" / "output")
        except Exception:
            pass

        # 기존 인프라용 SIMPLE_COLUMNS 형식으로 반환
        return [spec_to_simple(r) for r in spec_rows]
