"""실패 브랜드만 headless=False 로 재시도"""
from __future__ import annotations

import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.brands.registry import load_brands_config, save_brands_config
from app.services.crawler_service import run_brand_crawl

RETRY = ("cos", "hm", "balenciaga", "dior", "chanel")


def main() -> None:
    brands = load_brands_config()
    for brand_id in RETRY:
        print(f"\n=== retry {brand_id} ===", flush=True)
        try:
            result = run_brand_crawl(brand_id, headless=False)
            ok = result.get("success")
            print(f"{'OK' if ok else 'FAIL'} {result.get('count', 0)} {result.get('message', '')}", flush=True)
            for item in brands:
                if item["id"] == brand_id:
                    if ok:
                        item["last_crawled_at"] = result.get("crawled_at") or datetime.now().strftime(
                            "%Y-%m-%d %H:%M:%S"
                        )
                        item["last_status"] = "success"
                    else:
                        item["last_status"] = "failed"
                    break
        except Exception as exc:
            print(f"ERROR {exc}", flush=True)
            for item in brands:
                if item["id"] == brand_id:
                    item["last_status"] = "failed"
                    break
    save_brands_config(brands)


if __name__ == "__main__":
    main()
