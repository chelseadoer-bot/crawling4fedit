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
from app.core.csv_schema import _clean, format_price

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

# ── ZARA 카테고리 → 한글 대분류/소분류 매핑 ─────────────────────────────────
# key: ZARA familyName (대문자)
# value: (main_category, category_ko)
_CATEGORY_MAP: dict[str, tuple[str, str]] = {
    "SHIRT":              ("상의", "셔츠/블라우스"),
    "T-SHIRT":            ("상의", "티셔츠"),
    "SWEATER":            ("상의", "니트"),
    "CARDIGAN":           ("상의", "가디건"),
    "TOPS AND OTHERS":    ("상의", "탑"),
    "BLOUSE":             ("상의", "블라우스"),
    "TANK TOP":           ("상의", "탱크탑"),
    "BLAZER":             ("아우터", "블레이저"),
    "JACKET":             ("아우터", "자켓"),
    "COAT":               ("아우터", "코트"),
    "LEATHER JACKET":     ("아우터", "레더자켓"),
    "TROUSERS":           ("바지", "슬랙스"),
    "BERMUDA":            ("바지", "버뮤다 팬츠"),
    "JEANS":              ("바지", "청바지"),
    "SHORTS":             ("바지", "반바지"),
    "LEGGINGS":           ("바지", "레깅스"),
    "SKIRT":              ("치마", "스커트"),
    "MINISKIRT":          ("치마", "미니스커트"),
    "DRESS":              ("원피스", "원피스"),
    "OVERALL":            ("원피스", "오버롤"),
    "JUMPSUIT":           ("원피스", "점프수트"),
    "FLAT SANDAL":        ("신발", "플랫 샌들"),
    "HEELED SANDAL":      ("신발", "힐 샌들"),
    "FLAT SHOES":         ("신발", "플랫슈즈"),
    "HEELED SHOES":       ("신발", "힐"),
    "ATHLETIC FOOTWEAR":  ("신발", "운동화"),
    "BOOTS":              ("신발", "부츠"),
    "HAND BAG-RUCKSACK":  ("가방", "핸드백/백팩"),
    "EAU DE PARFUM":      ("기타", "향수"),
    "ACCESSORIES":        ("기타", "액세서리"),
    "JEWELLERY":          ("기타", "주얼리"),
    "BELT":               ("기타", "벨트"),
    "SCARF":              ("기타", "스카프"),
}


def map_category(family_name: str) -> tuple[str, str]:
    """ZARA familyName → (main_category, category_ko). 매핑 없으면 원본 반환."""
    key = (family_name or "").upper().strip()
    if key in _CATEGORY_MAP:
        return _CATEGORY_MAP[key]
    return ("기타", family_name) if family_name else ("", "")


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
        c = int(re.sub(r"[^\d]", "", str(current)))
        r = int(re.sub(r"[^\d]", "", str(regular)))
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
    """(color_names, color_chip_url, thumbnail_url)

    ZARA API는 별도 컬러칩 이미지가 없으므로 color_chip은 빈값.
    thumbnail은 originalName='p' (메인 상품 이미지) 우선.
    """
    colors_detail = component.get("detail", {}).get("colors", [])
    names: list[str] = []
    thumb_url = ""

    for i, color in enumerate(colors_detail):
        name = (color.get("name") or "").strip()
        if name and name not in names:
            names.append(name)

        if i == 0 and not thumb_url:
            # originalName='p' 인 메인 이미지 우선, 없으면 첫 번째
            first_url = ""
            for media in color.get("xmedia", []):
                raw_url = (
                    media.get("extraInfo", {}).get("deliveryUrl")
                    or media.get("url", "")
                )
                if not raw_url:
                    continue
                original_name = media.get("extraInfo", {}).get("originalName", "")
                hq = upgrade_image_url(raw_url)
                if not first_url:
                    first_url = hq
                if original_name == "p":
                    thumb_url = hq
                    break
            if not thumb_url:
                thumb_url = first_url

    # 최종 폴백: component 최상위 xmedia
    if not thumb_url:
        for media in component.get("xmedia", []):
            raw_url = (
                media.get("extraInfo", {}).get("deliveryUrl")
                or media.get("url", "")
            )
            if raw_url:
                thumb_url = upgrade_image_url(raw_url)
                break

    # 색상명 " / " → "," (ZARA 색상 구분자 통일)
    color_str = ",".join(
        n.replace(" / ", ",").replace("/", ",").strip() for n in names
    )
    # ZARA API는 별도 칩 이미지 없음 → color_chip 빈값
    return color_str, "", thumb_url


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

    current_price_raw = normalize_price(component.get("price"))
    regular_price_raw = normalize_price(component.get("oldPrice")) or current_price_raw
    discount_rate = calc_discount_rate(current_price_raw, regular_price_raw)
    current_price = format_price(current_price_raw, "KRW")
    regular_price = format_price(regular_price_raw, "KRW")

    gender_hint = config.get("gender", "women")
    url_lower = config.get("default_url", "").lower()
    # "woman"에 "man"이 포함되므로 /man/ 또는 /men/ 패턴으로 체크
    if re.search(r"[/-](man|men|hombre)[/-]", url_lower):
        gender_hint = "men"
    elif re.search(r"[/-](kid|kids|bebe|nino)[/-]", url_lower):
        gender_hint = "kids"

    family_name = (
        component.get("familyName")
        or component.get("sectionName")
        or component.get("kindName")
        or ""
    )
    main_cat, sub_category = map_category(family_name)

    return {
        "platform": "",
        "is_ranking": "false",
        "rank": "",
        "brand": "ZARA",
        "brand_likes": "",
        "main_category": main_cat,
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


_GENDER_KO = {
    "women": "여성", "woman": "여성", "female": "여성",
    "men": "남성", "man": "남성", "male": "남성",
    "kids": "공용", "unisex": "공용",
}


def spec_to_simple(row: dict) -> dict:
    """spec v3 row → 표준 26컬럼 dict"""
    current = row.get("current_price", "")
    regular = row.get("regular_price", "") or current
    discount = row.get("discount_rate", "")
    if not discount:
        discount = calc_discount_rate(current, regular)

    gender_raw = (row.get("gender") or "").strip().lower()
    gender = _GENDER_KO.get(gender_raw, row.get("gender", ""))

    return {
        "platform":           row.get("platform", ""),
        "is_ranking":         row.get("is_ranking", "false"),
        "rank":               row.get("rank", ""),
        "brand":              row.get("brand", "ZARA"),
        "brand_likes":        row.get("brand_likes", ""),
        "main_category":      row.get("main_category", ""),
        "category":           row.get("category", ""),
        "gender":             gender,
        "product_detail_url": row.get("product_detail_url", ""),
        "product_name":       row.get("product_name", ""),
        "color":              row.get("color", ""),
        "color_chip":         row.get("color_chip", ""),
        "thumbnail":          row.get("thumbnail", ""),
        "likes":              row.get("likes", ""),
        "views":              row.get("views", ""),
        "details":            row.get("details", ""),
        "material":           row.get("material", ""),
        "current_price":      current,
        "regular_price":      regular,
        "discount_rate":      discount,
        "rating":             row.get("rating", ""),
        "reviews":            row.get("reviews", ""),
        "sales":              row.get("sales", ""),
        "manufacture_date":   row.get("manufacture_date", ""),
        "crawled_at":         row.get("crawled_at", ""),
        "reorder":            row.get("reorder", ""),
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
            const imgEl = block.closest('li')?.querySelector('img');
            const img = imgEl?.currentSrc || imgEl?.src || imgEl?.dataset?.src || imgEl?.getAttribute('data-src') || '';
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
        current_price = format_price(re.sub(r"[^0-9]", "", item.get("price", "")), "KRW")

        rows.append({
            "platform": "",
            "is_ranking": "false",
            "rank": "",
            "brand": "ZARA",
            "brand_likes": "",
            "main_category": "",
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
