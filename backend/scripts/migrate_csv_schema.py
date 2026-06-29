"""기존 출력 CSV를 새 SIMPLE 스키마(필수 필드 강제)로 일괄 변환.

대상: data/output/<brand>/<brand>_latest.csv, <brand>_products.csv
- 컬럼 매핑(standard_to_simple) → 필수 스키마 강제(enforce_schema)
- 가격: regular 항상 / current·discount는 할인 시만, 정수 할인율
- gender: 비면 브랜드 URL·그룹 힌트로 보강
- platform: 멀티브랜드 플랫폼만 표기명, 단일 브랜드는 빈값
- 멱등(여러 번 돌려도 동일 결과)

사용:  python scripts/migrate_csv_schema.py [--dry-run]
"""

from __future__ import annotations

import csv
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.brands.registry import PROJECT_ROOT  # noqa: E402
from app.core.csv_schema import SIMPLE_COLUMNS  # noqa: E402
from app.core.csv_writer import _write_csv, standard_to_simple  # noqa: E402
from app.core.product_store import enforce_schema  # noqa: E402

OUTPUT_ROOT = PROJECT_ROOT / "data" / "output"


def _read_rows(path: Path) -> list[dict]:
    with path.open(encoding="utf-8-sig") as f:
        return list(csv.DictReader(f))


def migrate_file(path: Path, brand_id: str, dry_run: bool) -> int:
    raw = _read_rows(path)
    if not raw:
        return 0
    rows = [standard_to_simple(r) for r in raw]
    enforce_schema(brand_id, rows)
    if not dry_run:
        _write_csv(rows, SIMPLE_COLUMNS, path)
    return len(rows)


def main() -> None:
    dry_run = "--dry-run" in sys.argv
    if not OUTPUT_ROOT.exists():
        print(f"출력 폴더 없음: {OUTPUT_ROOT}")
        return

    total_files = 0
    total_rows = 0
    for brand_dir in sorted(OUTPUT_ROOT.iterdir()):
        if not brand_dir.is_dir():
            continue
        brand_id = brand_dir.name
        for name in (f"{brand_id}_latest.csv", f"{brand_id}_products.csv"):
            path = brand_dir / name
            if not path.exists():
                continue
            n = migrate_file(path, brand_id, dry_run)
            total_files += 1
            total_rows += n
            print(f"  {'[dry] ' if dry_run else ''}{path.relative_to(PROJECT_ROOT)}  ({n} rows)")

    print(f"\n완료: 파일 {total_files}개, 행 {total_rows}개{' (dry-run)' if dry_run else ''}")


if __name__ == "__main__":
    main()
