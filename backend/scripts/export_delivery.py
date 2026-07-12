# -*- coding: utf-8 -*-
"""AI 전달용 브랜드별 통합 CSV 내보내기.

- 활성 타깃들의 latest CSV를 브랜드(group) 단위로 병합
- product_detail_url 기준 중복 제거 (랭킹 행 우선 — rank 정보 보존)
- 파일명: {브랜드영문슬러그}_{YYYYMMDD}.csv → data/delivery/

사용: python -X utf8 scripts/export_delivery.py
"""
import csv
import json
import re
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app.brands.registry import PROJECT_ROOT  # noqa: E402
from app.core.csv_schema import SIMPLE_COLUMNS  # noqa: E402
from app.core.csv_writer import _write_csv  # noqa: E402

OUT = PROJECT_ROOT / "data" / "delivery"


def slug_of(ids: list[str]) -> str:
    base = ids[0].split("-")[0]
    return re.sub(r"[^a-z0-9]", "", base.lower()) or ids[0]


def main() -> None:
    cfg = json.load(open(PROJECT_ROOT / "config" / "brands.json", encoding="utf-8"))
    groups: dict[str, list[str]] = {}
    for b in cfg["brands"]:
        if b.get("enabled"):
            groups.setdefault(b.get("group") or b["id"], []).append(b["id"])

    OUT.mkdir(parents=True, exist_ok=True)
    date = datetime.now().strftime("%Y%m%d")
    total_files = 0
    total_rows = 0
    for group, ids in sorted(groups.items()):
        merged: dict[str, dict] = {}
        for bid in ids:
            p = PROJECT_ROOT / "data" / "output" / bid / f"{bid}_latest.csv"
            if not p.exists():
                continue
            for r in csv.DictReader(open(p, encoding="utf-8-sig")):
                key = r.get("product_detail_url") or f"{bid}:{r.get('product_name')}"
                prev = merged.get(key)
                if prev is None or (r.get("is_ranking") == "true" and prev.get("is_ranking") != "true"):
                    merged[key] = r
        if not merged:
            continue
        rows = list(merged.values())
        fname = f"{slug_of(ids)}_{date}.csv"
        _write_csv(rows, SIMPLE_COLUMNS, OUT / fname)
        total_files += 1
        total_rows += len(rows)
        print(f"  {fname}: {len(rows)}행 (타깃 {len(ids)}개 병합)")
    print(f"\n완료: {total_files}개 파일 / {total_rows:,}행 → {OUT}")


if __name__ == "__main__":
    main()
