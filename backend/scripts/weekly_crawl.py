"""
주간 자동 크롤링 스크립트
매일 오전 9시 Windows 작업 스케줄러에 의해 실행됨.

사용법:
  python weekly_crawl.py          # 오늘 요일에 해당하는 브랜드 자동 크롤링
  python weekly_crawl.py monday   # 강제로 특정 요일 그룹 실행
  python weekly_crawl.py all      # 전체 브랜드 실행
"""

import json
import logging
import sys
from datetime import datetime
from pathlib import Path

# 프로젝트 루트를 Python path에 추가
PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT_ROOT / "backend"))

from app.brands.registry import load_brands_config, get_brand_meta
from app.services.crawler_service import run_brand_crawl

SCHEDULE_FILE = PROJECT_ROOT / "config" / "schedule.json"
LOG_DIR = PROJECT_ROOT / "data" / "logs"

WEEKDAY_NAMES = {
    0: "monday",
    1: "tuesday",
    2: "wednesday",
    3: "thursday",
    4: "friday",
    5: "saturday",
    6: "sunday",
}


def setup_logger():
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    today = datetime.now().strftime("%Y%m%d")
    log_file = LOG_DIR / f"crawl_{today}.log"
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
        handlers=[
            logging.FileHandler(log_file, encoding="utf-8"),
            logging.StreamHandler(sys.stdout),
        ],
    )
    return logging.getLogger("weekly_crawl")


def load_schedule() -> dict:
    with SCHEDULE_FILE.open(encoding="utf-8") as f:
        return json.load(f)


def get_today_brand_ids(schedule: dict, weekday_override: str | None = None) -> tuple[str, list[str]]:
    today_key = weekday_override or WEEKDAY_NAMES[datetime.now().weekday()]
    day_config = schedule.get("weekly", {}).get(today_key, {})
    label = day_config.get("label", today_key)

    # daily 그룹(플랫폼 랭킹 등)은 매일, 요일 그룹에 앞서 실행
    daily_config = schedule.get("daily", {})
    daily_ids = daily_config.get("brand_ids", [])
    day_ids = day_config.get("brand_ids", [])
    brand_ids = daily_ids + [b for b in day_ids if b not in daily_ids]

    if daily_ids:
        daily_label = daily_config.get("label", "daily")
        label = f"{daily_label} + {label}" if day_ids else daily_label
    return label, brand_ids


def run_crawls(brand_ids: list[str], logger: logging.Logger) -> dict:
    results = {"success": [], "failed": [], "skipped": []}

    for brand_id in brand_ids:
        brand = get_brand_meta(brand_id)
        if not brand:
            logger.warning(f"브랜드 없음: {brand_id} — brands.json에 등록되어 있는지 확인")
            results["skipped"].append(brand_id)
            continue

        if not brand.get("enabled", True):
            logger.info(f"비활성화됨, 건너뜀: {brand_id}")
            results["skipped"].append(brand_id)
            continue

        logger.info(f"▶ 크롤링 시작: {brand.get('group', '')} / {brand.get('name', brand_id)}")

        try:
            result = run_brand_crawl(brand_id)
            if result["success"]:
                logger.info(f"  ✓ 완료: {result['count']}개 수집 → {result['output_path']}")
                results["success"].append(brand_id)
            else:
                logger.error(f"  ✗ 실패: {result['message']}")
                results["failed"].append(brand_id)
        except Exception as e:
            logger.exception(f"  ✗ 예외 발생: {e}")
            results["failed"].append(brand_id)

    return results


def main():
    logger = setup_logger()
    schedule = load_schedule()

    # CLI 인자 처리
    weekday_arg = sys.argv[1].lower() if len(sys.argv) > 1 else None

    if weekday_arg == "all":
        brand_ids = [b["id"] for b in load_brands_config() if b.get("enabled", True)]
        label = "전체 브랜드"
    else:
        label, brand_ids = get_today_brand_ids(schedule, weekday_arg)

    if not brand_ids:
        logger.info(f"오늘({label}) 실행할 브랜드가 없습니다.")
        return

    logger.info(f"═══ {label} 크롤링 시작 ({len(brand_ids)}개 브랜드) ═══")
    logger.info(f"대상: {', '.join(brand_ids)}")

    start = datetime.now()
    results = run_crawls(brand_ids, logger)
    elapsed = (datetime.now() - start).seconds

    logger.info(f"═══ 완료 ({elapsed}초) ══")
    logger.info(f"  성공: {len(results['success'])}  실패: {len(results['failed'])}  건너뜀: {len(results['skipped'])}")
    if results["failed"]:
        logger.warning(f"  실패 목록: {results['failed']}")


if __name__ == "__main__":
    main()
