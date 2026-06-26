"""신규 디자이너 브랜드 일괄 크롤"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.services.crawler_service import run_brand_crawl

NEW_IDS = [
    "lemaire-women-rtw",
    "ohne-viewall-26",
    "tildeseoul-91",
    "grove-204",
    "eenk-womens",
    "diagonal-71",
    "diagonal-44",
    "diagonal-84",
    "diagonal-58",
    "diagonal-59",
    "notyourrose-63",
    "lowclassic-527",
    "howus-outwears",
    "howus-tops",
    "howus-bottoms",
    "howus-dresses",
    "sculptor-779",
    "aftermonday-033-003",
    "aftermonday-033-013",
    "aftermonday-033-004",
    "aftermonday-033-014",
    "lowtide-45",
]

PLAYWRIGHT_IDS = {"eenk-womens"}


def main() -> None:
    ok, fail = 0, 0
    for bid in NEW_IDS:
        headless = bid not in PLAYWRIGHT_IDS
        print(f"\n=== {bid} ===", flush=True)
        try:
            r = run_brand_crawl(bid, headless=headless)
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
