"""기존 ZARA CSV의 잘못된 product_detail_url을 API seo 필드 기준으로 수정."""
import csv
import json
import re
import sys
import urllib.request
from pathlib import Path

from app.brands.zara.crawler import build_zara_product_url, extract_category_id, load_config

PROJECT_ROOT = Path(__file__).resolve().parents[2]


def collect_components(data: dict) -> list[dict]:
    comps: list[dict] = []
    for g in data.get("productGroups", []):
        for el in g.get("elements", []):
            if el.get("commercialComponents"):
                comps.extend(el["commercialComponents"])
            elif el.get("reference") or el.get("id"):
                comps.append(el)
    return comps


def fetch_url_maps(category_ids: set[str]) -> tuple[dict[str, str], dict[str, str]]:
    by_name: dict[str, str] = {}
    by_ref: dict[str, str] = {}
    for cid in category_ids:
        if not cid:
            continue
        api = f"https://www.zara.com/kr/ko/category/{cid}/products?ajax=true"
        req = urllib.request.Request(
            api,
            headers={
                "User-Agent": "Mozilla/5.0",
                "Accept": "application/json",
                "Referer": "https://www.zara.com/kr/",
            },
        )
        try:
            data = json.loads(urllib.request.urlopen(req, timeout=30).read())
        except Exception as exc:
            print(f"category {cid} fetch failed: {exc}")
            continue
        for comp in collect_components(data):
            url = build_zara_product_url(comp)
            if not url:
                continue
            name = (comp.get("name") or "").strip()
            ref = (comp.get("reference") or "").strip()
            if name:
                by_name[name] = url
            if ref:
                by_ref[ref] = url
                base_ref = re.sub(r"-[VI]\d{4}$", "", ref)
                if base_ref:
                    by_ref[base_ref] = url
    return by_name, by_ref


def needs_fix(url: str) -> bool:
    if not url:
        return False
    return bool(re.search(r"-p\d+-[VI]\d{4}\.html", url))


def repair_file(csv_path: Path) -> int:
    config = load_config()
    category_ids = {
        str(config.get("default_category_id") or ""),
        str(extract_category_id(config.get("default_url", "")) or ""),
    }
    for extra in config.get("extra_urls", []):
        cid = extract_category_id(extra)
        if cid:
            category_ids.add(str(cid))

    by_name, by_ref = fetch_url_maps(category_ids)
    rows = list(csv.DictReader(csv_path.open(encoding="utf-8-sig")))
    if not rows:
        return 0

    fixed = 0
    for row in rows:
        old = (row.get("product_detail_url") or "").strip()
        if not needs_fix(old):
            continue
        name = (row.get("product_name") or "").strip()
        m = re.search(r"-p([^./]+)\.html", old)
        ref_key = m.group(1) if m else ""
        new_url = by_name.get(name) or by_ref.get(ref_key)
        if ref_key and not new_url:
            new_url = by_ref.get(re.sub(r"-[VI]\d{4}$", "", ref_key))
        if new_url and new_url != old:
            row["product_detail_url"] = new_url
            fixed += 1

    if fixed:
        fieldnames = list(rows[0].keys())
        with csv_path.open("w", newline="", encoding="utf-8-sig") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames, lineterminator="\n")
            writer.writeheader()
            writer.writerows(rows)
    return fixed


def main() -> None:
    targets = [
        PROJECT_ROOT / "data" / "output" / "zara" / "zara_latest.csv",
        PROJECT_ROOT / "data" / "output" / "zara" / "zara_products.csv",
    ]
    total = 0
    for path in targets:
        if not path.exists():
            continue
        count = repair_file(path)
        print(f"{path.name}: {count} URLs fixed")
        total += count
    if total == 0:
        print("No URLs needed fixing.")
    sys.exit(0)


if __name__ == "__main__":
    main()
