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
    "front_images_url",
    "color_classification_url",
    "color_chip",
    "product_detail_url",
}


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
    """STANDARD_COLUMNS row → SIMPLE_COLUMNS row (UI 표시용)"""
    price = _clean(row.get("current_price") or row.get("regular_price") or row.get("가격", ""))
    # 기존 한글 키 호환
    result = {}
    for col in SIMPLE_COLUMNS:
        # 기존 파일에서 읽어온 경우 한글 키로 들어올 수 있음
        label = SIMPLE_COLUMN_LABELS.get(col, col)
        val = (
            _clean(row.get(col))
            or _clean(row.get(label))
        )
        result[col] = val
    # 가격 포맷
    if not result.get("current_price"):
        result["current_price"] = format_price_krw(price) if price else ""
    return result


def save_simple_csv(products: list[dict], output_path: Path) -> None:
    """SIMPLE_COLUMNS 순서로 저장. 날짜 파일 + latest 파일."""
    # output_path 예: data/output/zara/zara_products.csv
    # → 날짜 파일: data/output/zara/zara_20260616.csv
    stem = output_path.stem  # e.g. "zara_products"
    brand_id = stem.split("_")[0]  # "zara"
    dated_name = f"{brand_id}_{today_str()}.csv"
    dated_path = output_path.parent / dated_name

    simple_rows = []
    for row in products:
        if col_exists_as_standard(row):
            simple_rows.append(_clean_row(row, SIMPLE_COLUMNS))
        else:
            simple_rows.append(standard_to_simple(row))

    _write_csv(simple_rows, SIMPLE_COLUMNS, dated_path)

    # latest (기존 코드가 읽는 경로 유지)
    latest_path = output_path.parent / f"{brand_id}_latest.csv"
    _write_csv(simple_rows, SIMPLE_COLUMNS, latest_path)

    # 기존 경로에도 저장 (main.py가 brand_id_products.csv 를 읽으므로 유지)
    _write_csv(simple_rows, SIMPLE_COLUMNS, output_path)


def col_exists_as_standard(row: dict) -> bool:
    """row가 SIMPLE_COLUMNS 키를 이미 갖고 있는지 확인"""
    return any(k in row for k in ("front_images_url", "product_name", "current_price"))
