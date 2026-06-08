"""신규 브랜드 추가 및 크롤링 실행"""
import json
import sys
import urllib.error
import urllib.request

API = "http://127.0.0.1:8000/api"

BRANDS = [
    ("UNIQLO 여성 상의", "https://www.uniqlo.com/kr/ko/women/tops"),
    ("29CM 상의", "https://www.29cm.co.kr/store/category/list?categoryLargeCode=268100100&categoryMediumCode=268103100&sort=RECOMMENDED&defaultSort=RECOMMENDED&page=1"),
    ("DIOR", "https://www.dior.com/ko_kr/fashion/womens-fashion/ready-to-wear/all-ready-to-wear"),
]


def request(method: str, path: str, body: dict | None = None) -> dict:
    data = json.dumps(body).encode() if body else None
    headers = {"Content-Type": "application/json"} if body else {}
    req = urllib.request.Request(f"{API}{path}", data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=7200) as resp:
            return json.loads(resp.read())
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode()
        try:
            detail = json.loads(detail).get("detail", detail)
        except Exception:
            pass
        raise RuntimeError(detail) from exc


def main():
    existing = {b["name"]: b["id"] for b in request("GET", "/brands")["brands"]}
    brand_ids = []

    for name, url in BRANDS:
        if name in existing:
            brand_id = existing[name]
            print(f"[skip add] {name} -> {brand_id}")
        else:
            brand = request("POST", "/brands", {"name": name, "url": url})
            brand_id = brand["id"]
            print(f"[added] {name} -> {brand_id} (crawlable={brand.get('crawlable')})")
        brand_ids.append((name, brand_id))

    for name, brand_id in brand_ids:
        print(f"\n[crawl] {name} ({brand_id}) ...")
        try:
            result = request("POST", f"/brands/{brand_id}/crawl")
            print(f"  OK: {result.get('message')} -> {result.get('output_path')}")
        except Exception as exc:
            print(f"  FAIL: {exc}")


if __name__ == "__main__":
    main()
