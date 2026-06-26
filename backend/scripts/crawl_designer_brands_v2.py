"""2차 신규 디자이너 브랜드 일괄 크롤"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.services.crawler_service import run_brand_crawl

NEW_IDS = [
    "deinet-43",
    "matinkim-26",
    "matinkim-27",
    "matinkim-28",
    "matinkim-42",
    "instantfunk-24",
    "orr-clothing-all",
    "cerric-100",
    "thebarnnet-416",
    "mangomanyplease-50",
    "brendabrenden-191",
    "poev-26",
    "nicknicole-25",
    "safarispot-288",
    "safarispot-98",
    "safarispot-290",
    "safarispot-289",
]


def main() -> None:
    ok, fail = 0, 0
    for bid in NEW_IDS:
        print(f"\n=== {bid} ===", flush=True)
        try:
            r = run_brand_crawl(bid, headless=True)
            if r.get("success"):
                ok += 1
                print(f"OK count={r.get('count')}", flush=True)
            else:
                fail += 1
                print(f"FAIL {r.get('message')}", flush=True)
        except Exception as exc:
            fail += 1
            print(f"ERR {exc}", flush=True)
    print(f"\nDONE ok={ok} fail={fail}", flush=True)


if __name__ == "__main__":
    main()
