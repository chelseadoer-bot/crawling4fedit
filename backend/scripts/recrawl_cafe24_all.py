# -*- coding: utf-8 -*-
"""전체 cafe24 활성 타깃 재크롤 (할인가 HTML 보강 반영)."""
import sys, json, time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app.brands.registry import get_crawler, PROJECT_ROOT  # noqa: E402
from app.core.csv_writer import save_simple_csv  # noqa: E402

SKIP = {"hotping-outer", "hotping-top", "realcoco-24", "gogosing-tops", "grove-kr-shop"}  # 방금 크롤됨

cfg = json.load(open(PROJECT_ROOT / "config" / "brands.json", encoding="utf-8"))
targets = [b for b in cfg["brands"]
           if b.get("enabled") and b.get("crawler_id") == "cafe24" and b["id"] not in SKIP]
print(f"cafe24 재크롤 대상: {len(targets)}개", flush=True)

c = get_crawler("cafe24")
ok = fail = disc_brands = 0
t0 = time.time()
for i, b in enumerate(targets, 1):
    bid = b["id"]
    try:
        rows = c.crawl(url=b["default_url"])
        if not rows:
            print(f"[{i}/{len(targets)}] SKIP {bid}: 0건", flush=True)
            continue
        res = save_simple_csv(rows, PROJECT_ROOT / "data" / "output" / bid / f"{bid}_products.csv")
        d = sum(1 for r in rows if (r.get("current_price") or "").strip())
        if d:
            disc_brands += 1
        ok += 1
        print(f"[{i}/{len(targets)}] OK {bid}: {res.total}건 (할인 {d})", flush=True)
    except Exception as e:
        fail += 1
        print(f"[{i}/{len(targets)}] XX {bid}: {str(e)[:70]}", flush=True)
    time.sleep(0.5)

print(f"\n완료: 성공 {ok} / 실패 {fail} / 할인포함 {disc_brands}브랜드 / {int(time.time()-t0)}초", flush=True)
