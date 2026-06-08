import csv
import json
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from pydantic import BaseModel

from app.brands.registry import (
    PROJECT_ROOT,
    add_brand,
    delete_brand,
    get_brand_meta,
    group_key,
    load_brands_config,
    save_brands_config,
    update_brand,
)
from app.core.csv_schema import SIMPLE_COLUMNS
from app.core.csv_writer import standard_to_simple
from app.services.crawl_job import get_job, job_to_dict, start_crawl_job

app = FastAPI(
    title="Fashion Crawling Service",
    description="패션 MD 크롤링 자동화 서비스",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


SITE_DIR = PROJECT_ROOT / "site"


def csv_path_for(brand_id: str) -> Path:
    return PROJECT_ROOT / "data" / "output" / brand_id / f"{brand_id}_products.csv"


def normalize_rows(rows: list[dict]) -> list[dict]:
    if not rows:
        return []
    if "이미지" in rows[0]:
        return rows
    return [standard_to_simple(row) for row in rows]


def read_csv_rows(path: Path, limit: int | None = None) -> list[dict]:
    if not path.exists():
        return []
    with path.open(encoding="utf-8-sig") as f:
        rows = normalize_rows(list(csv.DictReader(f)))
    return rows[:limit] if limit else rows


@app.get("/")
def root():
    index = SITE_DIR / "index.html"
    if index.exists():
        return FileResponse(index)
    return {
        "service": "Fashion Crawling Service",
        "docs": "/docs",
        "brands": "/brands",
    }


@app.get("/stats")
def get_stats():
    brands = load_brands_config()
    total_products = 0
    brand_stats = []

    for brand in brands:
        path = csv_path_for(brand["id"])
        rows = read_csv_rows(path)
        count = len(rows)
        total_products += count
        last_crawled = brand.get("last_crawled_at")
        brand_stats.append(
            {
                "id": brand["id"],
                "name": brand["name"],
                "enabled": brand.get("enabled", True),
                "product_count": count,
                "last_crawled_at": last_crawled,
                "has_csv": path.exists(),
            }
        )

    return {
        "total_brands": len(brands),
        "active_brands": sum(1 for b in brands if b.get("enabled", True)),
        "total_products": total_products,
        "brands": brand_stats,
    }


class BrandCreateRequest(BaseModel):
    name: str
    url: str
    group: str | None = None


class BrandUpdateRequest(BaseModel):
    name: str | None = None
    url: str | None = None
    group: str | None = None


@app.post("/brands")
def create_brand(body: BrandCreateRequest):
    try:
        brand = add_brand(body.name, body.url, group=body.group)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    path = csv_path_for(brand["id"])
    crawl_started = False
    if brand.get("crawler_id"):
        start_crawl_job(brand["id"])
        crawl_started = True
    return {
        **brand,
        "product_count": 0,
        "has_csv": path.exists(),
        "crawlable": bool(brand.get("crawler_id")),
        "crawl_started": crawl_started,
    }


@app.patch("/brands/{brand_id}")
def patch_brand(brand_id: str, body: BrandUpdateRequest):
    try:
        brand = update_brand(brand_id, name=body.name, url=body.url, group=body.group)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    path = csv_path_for(brand_id)
    rows = read_csv_rows(path)
    return {
        **brand,
        "product_count": len(rows),
        "last_crawled_at": brand.get("last_crawled_at"),
        "has_csv": path.exists(),
        "crawlable": bool(brand.get("crawler_id")),
    }


@app.delete("/brands/{brand_id}")
def remove_brand(brand_id: str):
    try:
        delete_brand(brand_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return {"ok": True}


@app.get("/brands")
def list_brands():
    brands = load_brands_config()
    enriched = []
    for brand in brands:
        path = csv_path_for(brand["id"])
        rows = read_csv_rows(path)
        enriched.append(
            {
                **brand,
                "group": brand.get("group") or brand.get("name", ""),
                "product_count": len(rows),
                "last_crawled_at": brand.get("last_crawled_at"),
                "has_csv": path.exists(),
                "crawlable": bool(brand.get("crawler_id")),
            }
        )
    return {"brands": enriched}


@app.get("/groups/{group_slug}/preview")
def preview_group_csv(group_slug: str, limit: int = 50):
    brands = load_brands_config()
    matched = [
        b for b in brands if group_key(b.get("group") or b.get("name", "")) == group_slug
    ]
    if not matched:
        raise HTTPException(status_code=404, detail="그룹을 찾을 수 없습니다.")

    all_rows: list[dict] = []
    categories = []
    for brand in matched:
        path = csv_path_for(brand["id"])
        rows = read_csv_rows(path)
        categories.append(
            {
                "id": brand["id"],
                "name": brand.get("name", ""),
                "product_count": len(rows),
                "last_crawled_at": brand.get("last_crawled_at"),
            }
        )
        for row in rows:
            tagged = {**row, "_category": brand.get("name", "")}
            all_rows.append(tagged)

    preview_rows = [{k: v for k, v in r.items() if not k.startswith("_")} for r in all_rows[:limit]]
    group_name = matched[0].get("group") or matched[0].get("name", "")
    return {
        "group": group_name,
        "group_slug": group_slug,
        "columns": SIMPLE_COLUMNS,
        "total_count": len(all_rows),
        "preview_count": len(preview_rows),
        "rows": preview_rows,
        "categories": categories,
    }


@app.get("/brands/{brand_id}")
def get_brand(brand_id: str):
    brand = get_brand_meta(brand_id)
    if not brand:
        raise HTTPException(status_code=404, detail="브랜드를 찾을 수 없습니다.")
    path = csv_path_for(brand_id)
    rows = read_csv_rows(path)
    return {
        **brand,
        "product_count": len(rows),
        "last_crawled_at": brand.get("last_crawled_at"),
        "has_csv": path.exists(),
    }


@app.get("/brands/{brand_id}/preview")
def preview_brand_csv(brand_id: str, limit: int = 50):
    brand = get_brand_meta(brand_id)
    if not brand:
        raise HTTPException(status_code=404, detail="브랜드를 찾을 수 없습니다.")

    path = csv_path_for(brand_id)
    if not path.exists():
        job = job_to_dict(get_job(brand_id))
        return {
            "brand_id": brand_id,
            "columns": SIMPLE_COLUMNS,
            "total_count": 0,
            "preview_count": 0,
            "rows": [],
            "crawl_job": job,
        }

    rows = read_csv_rows(path, limit=limit)
    all_rows = read_csv_rows(path)
    return {
        "brand_id": brand_id,
        "columns": SIMPLE_COLUMNS,
        "total_count": len(all_rows),
        "preview_count": len(rows),
        "rows": rows,
    }


@app.get("/brands/{brand_id}/crawl/status")
def crawl_brand_status(brand_id: str):
    brand = get_brand_meta(brand_id)
    if not brand:
        raise HTTPException(status_code=404, detail="브랜드를 찾을 수 없습니다.")
    return job_to_dict(get_job(brand_id))


@app.post("/brands/{brand_id}/crawl")
def crawl_brand(brand_id: str, url: str | None = None, headless: bool = False):
    brand = get_brand_meta(brand_id)
    if not brand:
        raise HTTPException(status_code=404, detail="브랜드를 찾을 수 없습니다.")
    if not brand.get("enabled", True):
        raise HTTPException(status_code=400, detail="비활성화된 브랜드입니다.")
    if not brand.get("crawler_id"):
        raise HTTPException(status_code=400, detail="아직 지원하지 않는 사이트입니다.")

    crawl_url = url or brand.get("default_url")
    try:
        return start_crawl_job(brand_id, url=crawl_url, headless=headless)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@app.get("/brands/{brand_id}/download")
def download_csv(brand_id: str):
    brand = get_brand_meta(brand_id)
    if not brand:
        raise HTTPException(status_code=404, detail="브랜드를 찾을 수 없습니다.")

    csv_path = csv_path_for(brand_id)
    if not csv_path.exists():
        raise HTTPException(status_code=404, detail="CSV 파일이 없습니다. 먼저 크롤링을 실행하세요.")

    return FileResponse(
        path=csv_path,
        filename=csv_path.name,
        media_type="text/csv",
    )


if SITE_DIR.exists():
    assets_dir = SITE_DIR / "assets"
    if assets_dir.exists():
        app.mount("/assets", StaticFiles(directory=assets_dir), name="assets")
