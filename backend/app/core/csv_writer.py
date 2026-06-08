import csv
from pathlib import Path

from app.core.csv_schema import SIMPLE_COLUMNS, STANDARD_COLUMNS, format_price_krw


def standard_to_simple(row: dict) -> dict:
    price = row.get("price_sale") or row.get("price_original") or row.get("가격", "")
    return {
        "이미지": row.get("image_url") or row.get("이미지", ""),
        "상품명": row.get("product_name") or row.get("상품명", ""),
        "가격": format_price_krw(price) if price else row.get("가격", ""),
        "컬러": row.get("color") or row.get("컬러", ""),
    }


def save_simple_csv(products: list[dict], output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    simple_rows = []
    for row in products:
        if "이미지" in row and "상품명" in row:
            simple_rows.append({col: row.get(col, "") for col in SIMPLE_COLUMNS})
        else:
            simple_rows.append(standard_to_simple(row))

    with output_path.open("w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=SIMPLE_COLUMNS)
        writer.writeheader()
        writer.writerows(simple_rows)


def save_standard_csv(products: list[dict], output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=STANDARD_COLUMNS, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(products)
