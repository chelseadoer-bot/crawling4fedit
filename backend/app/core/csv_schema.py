"""CSV 컬럼 명세 — 표준 26컬럼 스키마"""

import re
from datetime import datetime

# ── 통화 감지 및 포맷 ─────────────────────────────────────────────────────────
_CURRENCY_SYMBOLS = {
    "KRW": "₩", "USD": "$", "EUR": "€", "GBP": "£", "JPY": "¥", "CNY": "¥",
}
_SYMBOL_TO_CURRENCY = {"₩": "KRW", "$": "USD", "€": "EUR", "£": "GBP", "¥": "JPY"}
_CURRENCY_KW = {
    "krw": "KRW", "won": "KRW", "원": "KRW",
    "usd": "USD", "dollar": "USD",
    "eur": "EUR", "euro": "EUR",
    "gbp": "GBP", "pound": "GBP",
    "jpy": "JPY", "yen": "JPY", "엔": "JPY",
}


def detect_currency(raw: str) -> str:
    """가격 문자열에서 통화 코드 감지. 기본값 KRW."""
    if not raw:
        return "KRW"
    s = raw.strip()
    if s and s[0] in _SYMBOL_TO_CURRENCY:
        return _SYMBOL_TO_CURRENCY[s[0]]
    sl = s.lower()
    for kw, code in _CURRENCY_KW.items():
        if kw in sl:
            return code
    return "KRW"


def format_price(raw, currency: str = "KRW") -> str:
    """가격 → 통화 기호 + 천단위 구분 (예: ₩89,900 / $89.90 / ¥9,900).
    raw가 이미 기호를 포함하면 통화를 재감지해서 재포맷."""
    if raw is None or raw == "":
        return ""
    s = str(raw).strip()
    if not s:
        return ""
    # 기호 포함 입력이면 통화 재감지
    detected = detect_currency(s)
    if detected != "KRW" or s[0] in _SYMBOL_TO_CURRENCY:
        currency = detected
    sym = _CURRENCY_SYMBOLS.get(currency, "₩")
    digits = re.sub(r"[^\d.]", "", s)
    if not digits:
        return s
    try:
        # 소수점 포함 여부
        if "." in digits:
            amount = float(digits)
            return f"{sym}{amount:,.2f}"
        else:
            return f"{sym}{int(digits):,}"
    except ValueError:
        return s

# ── 표준 26컬럼 (출력 순서 고정) ────────────────────────────────────────────
SIMPLE_COLUMNS = [
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

# 한글 레이블 (UI 헤더)
SIMPLE_COLUMN_LABELS = {
    "platform":           "플랫폼",
    "is_ranking":         "랭킹여부",
    "rank":               "순위",
    "brand":              "브랜드",
    "brand_likes":        "브랜드좋아요",
    "main_category":      "메인카테고리",
    "category":           "카테고리",
    "gender":             "성별",
    "product_detail_url": "상품링크",
    "product_name":       "상품명",
    "color":              "컬러",
    "color_chip":         "컬러칩",
    "thumbnail":          "이미지",
    "likes":              "좋아요",
    "views":              "조회수",
    "details":            "상세설명",
    "material":           "소재",
    "current_price":      "판매가",
    "regular_price":      "정상가",
    "discount_rate":      "할인율",
    "rating":             "평점",
    "reviews":            "리뷰수",
    "sales":              "판매량",
    "manufacture_date":   "제조일",
    "crawled_at":         "수집일",
    "reorder":            "재입고차수",
}

# ── CSV 출력 컬럼 (파일 저장용) ──────────────────────────────────────────────
STANDARD_COLUMNS = [
    "brand",
    "product_name",
    "category",
    "gender",
    "regular_price",
    "current_price",
    "discount_rate",
    "color_text",
    "color_chip",
    "color_classification_url",
    "front_images_url",
    "material",
    "details",
    "rating",
    "reviews",
    "product_detail_url",
    # 확장 속성
    "sizes_available",
    "fit",
    "length",
    "sleeve_length",
    "style",
    "lining",
    "thickness",
    "season",
    "transparency",
    "elasticity",
    "crawled_at",
    "source_site",
]

# ── alias → 표준 컬럼명 역방향 매핑 ─────────────────────────────────────────
ALIAS_MAP: dict[str, list[str]] = {
    "product_name":               ["product_name", "제품명", "상품명", "name", "상품이름"],
    "category":                   ["category", "카테고리", "category_name", "category_large", "category_small"],
    "color_text":                 ["color_text", "색상", "색상명", "color", "colors", "color(text)", "colour"],
    "color_chip":                 ["color_chip", "색상칩"],
    "color_classification_url":   ["color_classification_url", "색상구분이미지", "색상분류이미지URL", "색상분류이미지url", "색상분류이미지"],
    "front_images_url":           ["front_images_url", "대표이미지", "대표이미지URL", "대표이미지url", "이미지", "이미지URL", "이미지url", "image", "image_url"],
    "regular_price":              ["regular_price", "정상가", "price_original"],
    "current_price":              ["current_price", "할인가", "판매가", "가격", "price_sale", "price"],
    "discount_rate":              ["discount_rate", "할인율"],
    "material":                   ["material", "소재"],
    "details":                    ["details", "상세설명", "설명", "상세", "description"],
    "rating":                     ["rating", "평점"],
    "reviews":                    ["reviews", "리뷰수", "리뷰", "후기수"],
    "product_detail_url":         ["product_detail_url", "상세페이지url", "상세페이지URL", "상세url", "detail_url", "detail_page_url", "product_url"],
    "gender":                     ["gender", "성별"],
    "brand":                      ["brand", "브랜드"],
    "sizes_available":            ["sizes_available", "사이즈", "size"],
    "fit":                        ["fit", "핏"],
    "length":                     ["length", "기장"],
    "sleeve_length":              ["sleeve_length", "소매길이", "소매"],
    "style":                      ["style", "스타일"],
    "lining":                     ["lining", "안감"],
    "thickness":                  ["thickness", "두께감", "두께"],
    "season":                     ["season", "계절감", "계절"],
    "transparency":               ["transparency", "비침"],
    "elasticity":                 ["elasticity", "신축성"],
}

# alias → standard 역방향 딕셔너리 (빠른 조회)
_ALIAS_TO_STANDARD: dict[str, str] = {}
for _std, _aliases in ALIAS_MAP.items():
    for _a in _aliases:
        _ALIAS_TO_STANDARD[_a.lower()] = _std


def normalize_column_name(col: str) -> str:
    """어떤 컬럼명이든 표준 스키마 이름으로 변환"""
    return _ALIAS_TO_STANDARD.get(col.lower(), col)


def normalize_row(row: dict) -> dict:
    """row의 컬럼명을 표준화하고 빈 행 형식으로 반환"""
    result = empty_row()
    for k, v in row.items():
        std = normalize_column_name(k)
        if std in result:
            result[std] = _clean(v)
    return result


def _clean(v) -> str:
    """null/None/nan 을 빈 문자열로 변환"""
    if v is None:
        return ""
    s = str(v).strip()
    if s.lower() in ("none", "null", "nan", "n/a", "-"):
        return ""
    return s


_GENDER_KO = {
    "women": "여성", "woman": "여성", "female": "여성", "ladies": "여성",
    "men": "남성", "man": "남성", "male": "남성", "mens": "남성",
    "kids": "공용", "unisex": "공용", "공용": "공용",
    "여성": "여성", "남성": "남성",
}


def normalize_gender(v: str) -> str:
    if not v:
        return ""
    return _GENDER_KO.get(v.strip().lower(), v.strip())


def empty_row() -> dict:
    return {col: "" for col in SIMPLE_COLUMNS}


def today_yymmdd() -> str:
    """크롤링 날짜 YYMMDD (예: 260617)"""
    return datetime.now().strftime("%y%m%d")


def now_timestamp() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def today_str() -> str:
    return datetime.now().strftime("%Y%m%d")


def make_product_row(currency: str = "KRW", **kwargs) -> dict:
    """표준 26컬럼 행 생성.
    - gender 한글 변환
    - discount_rate 자동 계산 (current < regular 일 때)
    - current_price / regular_price → 통화 기호 + 천단위 포맷 (예: ₩89,900)
    """
    row = empty_row()
    row["is_ranking"] = "false"
    for k, v in kwargs.items():
        if k in row:
            row[k] = _clean(v)
    if row["gender"]:
        row["gender"] = normalize_gender(row["gender"])

    # discount_rate 자동 계산 (포맷 전 숫자 상태에서)
    if not row["discount_rate"] and row["current_price"] and row["regular_price"]:
        try:
            c = int(re.sub(r"[^\d]", "", row["current_price"]))
            r = int(re.sub(r"[^\d]", "", row["regular_price"]))
            if r > 0 and c < r:
                row["discount_rate"] = str(round((r - c) / r * 100))
        except (ValueError, ZeroDivisionError):
            pass

    # 가격 통화 포맷 적용
    for field in ("current_price", "regular_price"):
        if row[field]:
            row[field] = format_price(row[field], currency)

    return row


def format_price_krw(price) -> str:
    return format_price(price, "KRW")
