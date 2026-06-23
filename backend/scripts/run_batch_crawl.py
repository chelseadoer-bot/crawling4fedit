"""브랜드 카탈로그 등록 + 일괄 크롤."""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_ROOT))

from app.brands.registry import PROJECT_ROOT, load_brands_config, save_brands_config
from app.services.crawler_service import run_brand_crawl
from scripts.brand_catalog_entries import CATALOG_ENTRIES, entry_to_brand


REMOVED_BRAND_IDS = {
    "realcoco-51",
    "beidelli-446",
    "mixxo",
    "mixxo-47",
    "mixxo-3547",
    "mixxo-59",
    "mixxo-60",
    "mixxo-49",
    "mixxo-2414",
    "mixxo-50",
    "massimo-dutti",
    "arket",
    "topten",
    "general-idea",
    "mango",
}


def sync_catalog() -> int:
    existing = {b["id"]: b for b in load_brands_config()}
    added = 0
    updated = 0
    removed = 0
    for bid in list(existing):
        if bid in REMOVED_BRAND_IDS:
            del existing[bid]
            removed += 1
    for entry in CATALOG_ENTRIES:
        brand = entry_to_brand(entry)
        bid = brand["id"]
        if bid in existing:
            existing[bid].update(
                {
                    "category": brand["category"],
                    "group": brand["group"],
                    "name": brand["name"],
                    "enabled": brand["enabled"],
                    "crawl_type": brand["crawl_type"],
                    "crawler_id": brand["crawler_id"],
                    "default_url": brand["default_url"],
                    "source_site": brand["source_site"],
                }
            )
            updated += 1
        else:
            existing[bid] = brand
            added += 1
    save_brands_config(list(existing.values()))
    backend_cfg = PROJECT_ROOT / "backend" / "config" / "brands.json"
    if backend_cfg.parent.exists():
        with backend_cfg.open("w", encoding="utf-8") as f:
            json.dump({"brands": list(existing.values())}, f, ensure_ascii=False, indent=2)
    print(f"카탈로그 동기화: 추가 {added}, 갱신 {updated}, 삭제 {removed}, 총 {len(existing)}")
    return len(CATALOG_ENTRIES)


def run_batch(only_ids: list[str] | None = None, headless: bool = True) -> dict:
    catalog_ids = {e[0] for e in CATALOG_ENTRIES}
    brands = [b for b in load_brands_config() if b["id"] in catalog_ids]
    if only_ids:
        brands = [b for b in brands if b["id"] in only_ids]

    results = {"success": [], "failed": [], "skipped": []}
    for brand in brands:
        bid = brand["id"]
        if not brand.get("enabled") or brand.get("crawl_type") == "unsupported":
            results["skipped"].append({"id": bid, "reason": "크롤러 미지원"})
            print(f"[SKIP] {bid}")
            continue
        print(f"[CRAWL] {bid} ...", flush=True)
        try:
            out = run_brand_crawl(bid, headless=headless)
            if out.get("success"):
                results["success"].append(
                    {
                        "id": bid,
                        "count": out.get("count"),
                        "new_count": out.get("new_count"),
                        "updated_count": out.get("updated_count"),
                        "unchanged_count": out.get("unchanged_count"),
                        "period": out.get("period"),
                        "message": out.get("message"),
                    }
                )
                print(f"  OK {out.get('message')}")
            else:
                results["failed"].append({"id": bid, "message": out.get("message")})
                print(f"  FAIL {out.get('message')}")
        except Exception as exc:
            results["failed"].append({"id": bid, "message": str(exc)})
            print(f"  ERR {exc}")

    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    report_path = PROJECT_ROOT / "data" / f"batch_crawl_{stamp}.json"
    report_path.parent.mkdir(parents=True, exist_ok=True)
    with report_path.open("w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2)
    print(f"리포트: {report_path}")
    print(f"성공 {len(results['success'])} / 실패 {len(results['failed'])} / 스킵 {len(results['skipped'])}")
    return results


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--sync-only", action="store_true")
    parser.add_argument("--ids", nargs="*", help="특정 brand id만 크롤")
    parser.add_argument("--no-headless", action="store_true")
    args = parser.parse_args()

    sync_catalog()
    if not args.sync_only:
        run_batch(only_ids=args.ids, headless=not args.no_headless)


if __name__ == "__main__":
    main()
