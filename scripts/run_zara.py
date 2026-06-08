"""ZARA 크롤러 CLI 실행 스크립트"""

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "backend"
sys.path.insert(0, str(BACKEND))

from app.services.crawler_service import run_brand_crawl  # noqa: E402


def main():
    parser = argparse.ArgumentParser(description="ZARA 상품 크롤러")
    parser.add_argument(
        "--url",
        default=None,
        help="크롤링할 ZARA 카테고리 URL (미지정 시 config 기본값)",
    )
    parser.add_argument("--headless", action="store_true", help="헤드리스 모드")
    args = parser.parse_args()

    print("ZARA 크롤링 시작...")
    result = run_brand_crawl("zara", url=args.url, headless=args.headless)

    if result["success"]:
        print(f"완료: {result['count']}개 → {result['output_path']}")
    else:
        print(f"실패: {result['message']}")
        sys.exit(1)


if __name__ == "__main__":
    main()
