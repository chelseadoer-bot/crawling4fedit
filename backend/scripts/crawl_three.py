import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.brands.registry import load_brands_config, save_brands_config
from app.services.crawler_service import run_brand_crawl

for brand_id in ("cos", "hm", "balenciaga"):
    print(f"\n=== {brand_id} ===")
    try:
        r = run_brand_crawl(brand_id, headless=False)
        print("OK" if r["success"] else "FAIL", r.get("count"), r.get("message", "")[:80])
        if r["success"]:
            brands = load_brands_config()
            for b in brands:
                if b["id"] == brand_id:
                    b["last_crawled_at"] = r.get("crawled_at") or datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                    b["last_status"] = "success"
                    break
            save_brands_config(brands)
    except Exception as e:
        print("ERROR", e)
