"""유니클로·스파오·에잇세컨즈 재크롤"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.services.crawler_service import run_brand_crawl

BRANDS = ("uniqlo-tops", "spao-2605000015", "eightseconds-women")


def main() -> None:
    results = []
    for brand_id in BRANDS:
        print(f"\n=== START {brand_id} ===", flush=True)
        headless = brand_id != "eightseconds-women"
        try:
            result = run_brand_crawl(brand_id, headless=headless)
            results.append(result)
            ok = result.get("success")
            count = result.get("count")
            msg = (result.get("message") or "")[:120]
            print(f"=== DONE {brand_id}: success={ok} count={count} ===", flush=True)
            print(msg, flush=True)
        except Exception as exc:
            results.append({"brand_id": brand_id, "success": False, "error": str(exc)})
            print(f"=== ERROR {brand_id}: {exc} ===", flush=True)

    out = Path(__file__).resolve().parents[2] / "data" / "recrawl_results.json"
    out.write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\nResults saved: {out}", flush=True)


if __name__ == "__main__":
    main()
