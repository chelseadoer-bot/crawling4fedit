"""등록된 전 브랜드 크롤링 실행"""
from __future__ import annotations

import json
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.brands.registry import load_brands_config, save_brands_config
from app.core.csv_writer import save_simple_csv
from app.services.crawler_service import brand_output_path, run_brand_crawl

PLAYWRIGHT_BRANDS = {"zara", "dior", "hm", "cos", "balenciaga", "chanel", "moncler"}


def main() -> None:
    brands = load_brands_config()
    results = []

    for brand in brands:
        brand_id = brand["id"]
        print(f"\n=== [{brand.get('group')} · {brand.get('name')}] {brand_id} ===")
        headless = brand.get("crawler_id") not in PLAYWRIGHT_BRANDS
        try:
            result = run_brand_crawl(brand_id, headless=headless)
            if result["success"]:
                print(f"OK {result['count']} items")
                for item in brands:
                    if item["id"] == brand_id:
                        item["last_crawled_at"] = result.get("crawled_at") or datetime.now().strftime(
                            "%Y-%m-%d %H:%M:%S"
                        )
                        item["last_status"] = "success"
                        break
            else:
                print(f"FAIL {result['message']}")
                for item in brands:
                    if item["id"] == brand_id:
                        item["last_status"] = "failed"
                        break
            results.append(result)
        except Exception as exc:
            print(f"ERROR {exc}")
            for item in brands:
                if item["id"] == brand_id:
                    item["last_status"] = "failed"
                    break
            results.append({"brand_id": brand_id, "success": False, "message": str(exc)})

    save_brands_config(brands)
    print("\n=== SUMMARY ===")
    for r in results:
        status = "OK" if r.get("success") else "FAIL"
        count = r.get("count", 0)
        print(f"{status} {r.get('brand_id')}: {count} - {r.get('message', '')}")


if __name__ == "__main__":
    main()
