from datetime import datetime
from inspect import signature
from pathlib import Path
from typing import Callable

from app.brands.registry import PROJECT_ROOT, get_brand_meta, get_crawler, resolve_crawler_id
from app.core.csv_writer import save_simple_csv

ProgressCallback = Callable[[int, int], None]


def brand_output_path(brand_id: str) -> Path:
    return PROJECT_ROOT / "data" / "output" / brand_id / f"{brand_id}_products.csv"


def run_brand_crawl(
    brand_id: str,
    url: str | None = None,
    headless: bool = True,
    on_progress: ProgressCallback | None = None,
) -> dict:
    brand = get_brand_meta(brand_id)
    if not brand:
        return {
            "brand_id": brand_id,
            "success": False,
            "count": 0,
            "output_path": "",
            "message": "브랜드를 찾을 수 없습니다.",
        }

    crawler_id = resolve_crawler_id(brand)
    if not crawler_id:
        return {
            "brand_id": brand_id,
            "success": False,
            "count": 0,
            "output_path": "",
            "message": (
                "지원하지 않는 사이트이거나 크롤러가 등록되지 않았습니다. "
                "백엔드 서버를 최신 코드로 재시작한 뒤 다시 시도해주세요."
            ),
        }
    if brand.get("crawl_type") == "unsupported":
        return {
            "brand_id": brand_id,
            "success": False,
            "count": 0,
            "output_path": "",
            "message": "아직 지원하지 않는 사이트입니다.",
        }

    target_url = url or brand.get("default_url")
    crawler = get_crawler(crawler_id)
    crawl_kwargs: dict = {
        "url": target_url,
        "headless": headless,
        "brand_name": brand.get("group") or brand.get("name"),
    }
    if on_progress is not None:
        crawl_kwargs["on_progress"] = on_progress

    params = signature(crawler.crawl).parameters
    filtered = {k: v for k, v in crawl_kwargs.items() if k in params}
    products = crawler.crawl(**filtered)

    if not products:
        return {
            "brand_id": brand_id,
            "success": False,
            "count": 0,
            "output_path": "",
            "message": "수집된 상품이 없습니다.",
        }

    output_path = brand_output_path(brand_id)
    save_simple_csv(products, output_path)

    return {
        "brand_id": brand_id,
        "success": True,
        "count": len(products),
        "output_path": str(output_path),
        "crawled_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "message": f"{len(products)}개 상품 수집 완료",
    }
