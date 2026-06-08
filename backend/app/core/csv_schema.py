"""CSV 컬럼 명세"""

from datetime import datetime

# 사용자 출력 형식 (엑셀/미리보기용)
SIMPLE_COLUMNS = ["이미지", "상품명", "가격", "컬러"]

STANDARD_COLUMNS = [
    "brand",
    "product_id",
    "product_name",
    "category_large",
    "category_small",
    "price_original",
    "price_sale",
    "discount_rate",
    "color",
    "sizes_available",
    "stock_status",
    "product_url",
    "image_url",
    "crawled_at",
    "source_site",
]

COLUMN_LABELS_KO = {
    "brand": "브랜드명",
    "product_id": "상품코드",
    "product_name": "상품명",
    "category_large": "대분류",
    "category_small": "소분류",
    "price_original": "정가",
    "price_sale": "할인가",
    "discount_rate": "할인율(%)",
    "color": "색상",
    "sizes_available": "가용 사이즈",
    "stock_status": "재고상태",
    "product_url": "상품 URL",
    "image_url": "대표 이미지 URL",
    "crawled_at": "수집일시",
    "source_site": "수집 출처 도메인",
}


def empty_row() -> dict:
    return {col: "" for col in STANDARD_COLUMNS}


def now_timestamp() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


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
