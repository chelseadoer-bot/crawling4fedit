"""CSV 저장 유틸리티

규칙:
- 인코딩: UTF-8-SIG
- 구분자: 쉼표(,)
- 첫 행: 헤더
- 개행: \n (lineterminator='\n')
- 빈값: "" (null/None/nan 금지)
- URL 컬럼: 항상 쌍따옴표로 감싸기 (콤마 포함 URL 대응)
- 파일명: {brand_id}_{YYYYMMDD}.csv  +  {brand_id}_latest.csv
"""

import csv
from pathlib import Path

from app.core.csv_schema import (
    SIMPLE_COLUMNS,
    SIMPLE_COLUMN_LABELS,
    STANDARD_COLUMNS,
    _clean,
    format_price_krw,
    today_str,
)

# URL 값을 항상 쌍따옴표로 감싸야 하는 컬럼
_URL_COLUMNS = {
    "thumbnail",
    "color_chip",
    "product_detail_url",
}

_GENDER_KO = {
    "women": "여성", "woman": "여성", "female": "여성", "ladies": "여성",
    "men": "남성", "man": "남성", "male": "남성",
    "kids": "공용", "unisex": "공용", "kids/baby": "공용",
    "여성": "여성", "남성": "남성", "공용": "공용",
}


def _normalize_gender(v: str) -> str:
    return _GENDER_KO.get(v.strip().lower(), v)


def _clean_row(row: dict, fields: list[str]) -> dict:
    """지정 컬럼만 추출하고 null 제거"""
    return {col: _clean(row.get(col, "")) for col in fields}


def _write_csv(rows: list[dict], fields: list[str], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8-sig") as f:
        writer = csv.writer(f, lineterminator="\n", quoting=csv.QUOTE_MINIMAL)
        writer.writerow(fields)
        for row in rows:
            line = []
            for col in fields:
                val = _clean(row.get(col, ""))
                # URL 컬럼이나 값에 콤마 포함 시 강제 쌍따옴표
                if col in _URL_COLUMNS or ("," in val and not val.startswith('"')):
                    line.append(val)  # csv.QUOTE_MINIMAL이 자동으로 감쌈
                else:
                    line.append(val)
            writer.writerow(line)


# ── 표준 컬럼 CSV ─────────────────────────────────────────────────────────────

def save_standard_csv(products: list[dict], output_path: Path) -> None:
    """STANDARD_COLUMNS 순서로 저장. 날짜 파일 + latest 파일 둘 다 저장."""
    rows = [_clean_row(p, STANDARD_COLUMNS) for p in products]
    _write_csv(rows, STANDARD_COLUMNS, output_path)

    # latest 복사본
    latest = output_path.parent / f"{output_path.stem.rsplit('_', 1)[0]}_latest.csv"
    _write_csv(rows, STANDARD_COLUMNS, latest)


# ── 레거시 호환: simple CSV (기존 코드가 save_simple_csv를 호출) ──────────────

def standard_to_simple(row: dict) -> dict:
    """구 포맷 row → 표준 26컬럼 SIMPLE_COLUMNS row"""
    current = _clean(
        row.get("current_price") or row.get("판매가") or row.get("가격") or row.get("price_sale") or ""
    )
    regular = _clean(
        row.get("regular_price") or row.get("정상가") or row.get("price_original") or current
    )
    discount = _clean(row.get("discount_rate") or row.get("할인율") or "")
    if not discount and current and regular:
        try:
            c, r = int(current), int(regular)
            if r > 0 and c < r:
                discount = str(round((r - c) / r * 100))
        except (ValueError, ZeroDivisionError):
            pass

    gender_raw = _clean(row.get("gender") or row.get("성별") or "")

    return {
        "platform":           _clean(row.get("platform") or ""),
        "is_ranking":         _clean(row.get("is_ranking") or "false"),
        "rank":               _clean(row.get("rank") or ""),
        "brand":              _clean(row.get("brand") or row.get("브랜드") or ""),
        "brand_likes":        _clean(row.get("brand_likes") or ""),
        "main_category":      _clean(row.get("main_category") or ""),
        "category":           _clean(row.get("category") or row.get("카테고리") or ""),
        "gender":             _normalize_gender(gender_raw),
        "product_detail_url": _clean(row.get("product_detail_url") or row.get("상품링크") or ""),
        "product_name":       _clean(row.get("product_name") or row.get("상품명") or ""),
        "color":              _clean(row.get("color") or row.get("color_text") or row.get("컬러") or ""),
        "color_chip":         _clean(row.get("color_chip") or ""),
        "thumbnail":          _clean(row.get("thumbnail") or row.get("front_images_url") or row.get("이미지") or ""),
        "likes":              _clean(row.get("likes") or ""),
        "views":              _clean(row.get("views") or ""),
        "details":            _clean(row.get("details") or row.get("상세설명") or ""),
        "material":           _clean(row.get("material") or row.get("소재") or ""),
        "current_price":      current,
        "regular_price":      regular,
        "discount_rate":      discount,
        "rating":             _clean(row.get("rating") or row.get("평점") or ""),
        "reviews":            _clean(row.get("reviews") or row.get("리뷰수") or ""),
        "sales":              _clean(row.get("sales") or ""),
        "manufacture_date":   _clean(row.get("manufacture_date") or ""),
        "crawled_at":         _clean(row.get("crawled_at") or row.get("수집일시") or ""),
        "reorder":            _clean(row.get("reorder") or ""),
    }


def save_simple_csv(products: list[dict], output_path: Path):
    """SIMPLE_COLUMNS 저장 + 증분(delta)/6개월 catalog 적치."""
    from app.core.product_store import save_products

    brand_id = output_path.stem.split("_")[0]
    return save_products(brand_id, products, output_path)


def col_exists_as_standard(row: dict) -> bool:
    """row가 표준 26컬럼 키를 이미 갖고 있는지 확인"""
    return any(k in row for k in ("thumbnail", "platform", "is_ranking"))
