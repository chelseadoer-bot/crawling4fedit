"""브랜드별 백그라운드 크롤 작업 (장시간 29CM 등)"""

from __future__ import annotations

import threading
from dataclasses import dataclass, field
from datetime import datetime
from typing import Callable

from app.brands.registry import load_brands_config, save_brands_config
from app.services.crawler_service import run_brand_crawl

ProgressCallback = Callable[[int, int], None]


@dataclass
class CrawlJobState:
    brand_id: str
    status: str = "idle"  # idle | running | success | failed
    message: str = ""
    count: int = 0
    page: int = 0
    started_at: str | None = None
    finished_at: str | None = None


_lock = threading.Lock()
_jobs: dict[str, CrawlJobState] = {}


def get_job(brand_id: str) -> CrawlJobState:
    with _lock:
        if brand_id not in _jobs:
            _jobs[brand_id] = CrawlJobState(brand_id=brand_id)
        return _jobs[brand_id]


def job_to_dict(state: CrawlJobState) -> dict:
    return {
        "brand_id": state.brand_id,
        "status": state.status,
        "message": state.message,
        "count": state.count,
        "page": state.page,
        "started_at": state.started_at,
        "finished_at": state.finished_at,
    }


def _set_running(state: CrawlJobState) -> None:
    state.status = "running"
    state.message = "크롤링 시작…"
    state.count = 0
    state.page = 0
    state.started_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    state.finished_at = None


def _run_crawl(brand_id: str, url: str | None, headless: bool) -> None:
    state = get_job(brand_id)

    def on_progress(count: int, page: int) -> None:
        with _lock:
            state.count = count
            state.page = page
            state.message = f"수집 중… {count:,}개 (페이지 {page})"

    try:
        result = run_brand_crawl(
            brand_id, url=url, headless=headless, on_progress=on_progress
        )
        with _lock:
            if result["success"]:
                state.status = "success"
                state.count = result["count"]
                state.message = result["message"]
                state.finished_at = result.get("crawled_at") or datetime.now().strftime(
                    "%Y-%m-%d %H:%M:%S"
                )
                brands = load_brands_config()
                for item in brands:
                    if item["id"] == brand_id:
                        item["last_crawled_at"] = state.finished_at
                        item["last_status"] = "success"
                        break
                save_brands_config(brands)
            else:
                state.status = "failed"
                state.message = result["message"]
                state.finished_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    except Exception as exc:
        with _lock:
            state.status = "failed"
            state.message = str(exc)
            state.finished_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    finally:
        with _lock:
            if state.status == "running":
                state.status = "failed"
                state.message = state.message or "크롤링이 중단되었습니다."


def start_crawl_job(
    brand_id: str, url: str | None = None, headless: bool = True
) -> dict:
    with _lock:
        state = get_job(brand_id)
        if state.status == "running":
            return {**job_to_dict(state), "already_running": True}

        _set_running(state)

    thread = threading.Thread(
        target=_run_crawl,
        args=(brand_id, url, headless),
        daemon=True,
        name=f"crawl-{brand_id}",
    )
    thread.start()
    return {**job_to_dict(get_job(brand_id)), "already_running": False}
