"""CSV 컬럼 명세 — alias_map 기반 표준 스키마"""

from datetime import datetime

# ── UI 표시 컬럼 (프론트엔드 테이블용) ──────────────────────────────────────
SIMPLE_COLUMNS = [
    "front_images_url",
    "product_name",
    "brand",
    "category",
    "gender",
    "regular_price",
    "current_price",
    "discount_rate",
    "color_text",
    "material",
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
    "rating",
    "reviews",
    "product_detail_url",
    "crawled_at",
]

# 한글 레이블 (UI 헤더)
SIMPLE_COLUMN_LABELS = {
    "front_images_url":  "이미지",
    "product_name":      "상품명",
    "brand":             "브랜드",
    "category":          "카테고리",
    "gender":            "성별",
    "regular_price":     "정상가",
    "current_price":     "판매가",
    "discount_rate":     "할인율",
    "color_text":        "컬러",
    "material":          "소재",
    "sizes_available":   "사이즈",
    "fit":               "핏",
    "length":            "기장",
    "sleeve_length":     "소매길이",
    "style":             "스타일",
    "lining":            "안감",
    "thickness":         "두께감",
    "season":            "계절감",
    "transparency":      "비침",
    "elasticity":        "신축성",
    "rating":            "평점",
    "reviews":           "리뷰수",
    "product_detail_url": "상품링크",
    "crawled_at":        "수집일시",
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


def empty_row() -> dict:
    return {col: "" for col in STANDARD_COLUMNS}


def now_timestamp() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def today_str() -> str:
    return datetime.now().strftime("%Y%m%d")


def format_price_krw(price) -> str:
    if price is None or price == "":
        return ""
    if isinstance(price, str):
        digits = "".join(ch for ch in price if ch.isdigit())
        if not digits:
            return price
        return f"₩ {int(digits):,}"
    if isinstance(price, (int, float)):
        return f"₩ {int(price):,}"
    return str(price)
