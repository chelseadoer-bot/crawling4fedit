import json
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.brands.registry import load_brands_config, save_brands_config

ROOT = Path(__file__).resolve().parents[2]
brands = load_brands_config()
now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

for brand in brands:
    csv_path = ROOT / "data" / "output" / brand["id"] / f"{brand['id']}_products.csv"
    if csv_path.exists() and csv_path.stat().st_size > 100:
        brand["last_crawled_at"] = now
        brand["last_status"] = "success"
        print(brand["id"], "OK")
    else:
        brand["last_status"] = brand.get("last_status") or "pending"
        print(brand["id"], "skip")

save_brands_config(brands)
