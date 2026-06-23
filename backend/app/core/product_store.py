"""상품 데이터 적치: 증분(delta) 저장 + 6개월(H1/H2) 단위 보관."""

from __future__ import annotations

import csv
import hashlib
import json
import shutil
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from urllib.parse import parse_qsl, urlencode, urlparse, urlunparse

from app.brands.registry import PROJECT_ROOT
from app.core.csv_schema import SIMPLE_COLUMNS, _clean, today_str
from app.core.csv_writer import _write_csv, col_exists_as_standard, standard_to_simple

_TRACK_FIELDS = (
    "product_name",
    "current_price",
    "regular_price",
    "discount_rate",
    "thumbnail",
    "color",
    "category",
    "rating",
    "reviews",
    "sales",
)


def period_key(dt: datetime | None = None) -> str:
    dt = dt or datetime.now()
    half = "H1" if dt.month <= 6 else "H2"
    return f"{dt.year}{half}"


def brand_output_dir(brand_id: str) -> Path:
    return PROJECT_ROOT / "data" / "output" / brand_id


def store_root(brand_id: str) -> Path:
    return brand_output_dir(brand_id) / "store"


def period_dir(brand_id: str, period: str) -> Path:
    return store_root(brand_id) / "periods" / period


def archive_dir(brand_id: str) -> Path:
    return store_root(brand_id) / "archive"


def index_path(brand_id: str) -> Path:
    return store_root(brand_id) / "index.json"


def product_key(url: str) -> str:
    raw = _clean(url)
    if not raw:
        return ""
    parsed = urlparse(raw)
    query = [(k, v) for k, v in parse_qsl(parsed.query, keep_blank_values=True) if not k.lower().startswith("utm_")]
    query.sort()
    return urlunparse((parsed.scheme, parsed.netloc.lower(), parsed.path.rstrip("/"), "", urlencode(query), ""))


def row_fingerprint(row: dict) -> str:
    payload = "|".join(_clean(row.get(field, "")) for field in _TRACK_FIELDS)
    return hashlib.sha1(payload.encode("utf-8")).hexdigest()


def normalize_rows(products: list[dict]) -> list[dict]:
    rows: list[dict] = []
    for row in products:
        if col_exists_as_standard(row):
            rows.append({col: _clean(row.get(col, "")) for col in SIMPLE_COLUMNS})
        else:
            rows.append(standard_to_simple(row))
    return rows


def _read_csv_rows(path: Path) -> list[dict]:
    if not path.exists():
        return []
    with path.open(encoding="utf-8-sig") as f:
        return list(csv.DictReader(f))


def _load_index(brand_id: str) -> dict:
    path = index_path(brand_id)
    if path.exists():
        with path.open(encoding="utf-8") as f:
            return json.load(f)
    return {"version": 1, "period": period_key(), "products": {}}


def _save_index(brand_id: str, index: dict) -> None:
    path = index_path(brand_id)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        json.dump(index, f, ensure_ascii=False, indent=2)


def bootstrap_index_from_latest(brand_id: str) -> dict:
    out_dir = brand_output_dir(brand_id)
    latest = out_dir / f"{brand_id}_latest.csv"
    legacy = out_dir / f"{brand_id}_products.csv"
    source = latest if latest.exists() else legacy
    index = _load_index(brand_id)
    if index.get("products"):
        return index
    rows = _read_csv_rows(source)
    if not rows:
        return index
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    period = period_key()
    for row in rows:
        key = product_key(row.get("product_detail_url", ""))
        if not key:
            continue
        index["products"][key] = {
            "fingerprint": row_fingerprint(row),
            "first_seen": now,
            "last_seen": now,
            "period": period,
        }
    index["period"] = period
    _save_index(brand_id, index)
    return index


def load_known_product_keys(brand_id: str) -> set[str]:
    index = bootstrap_index_from_latest(brand_id)
    return set(index.get("products", {}).keys())


def _period_catalog_path(brand_id: str, period: str) -> Path:
    return period_dir(brand_id, period) / "catalog.csv"


def _read_catalog_map(path: Path) -> dict[str, dict]:
    rows = _read_csv_rows(path)
    catalog: dict[str, dict] = {}
    for row in rows:
        key = product_key(row.get("product_detail_url", ""))
        if key:
            catalog[key] = row
    return catalog


def _write_catalog(path: Path, rows: list[dict]) -> None:
    _write_csv(rows, SIMPLE_COLUMNS, path)


def _update_manifest(brand_id: str, period: str, *, delta_count: int, catalog_count: int) -> None:
    manifest_path = period_dir(brand_id, period) / "manifest.json"
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    manifest = {}
    if manifest_path.exists():
        with manifest_path.open(encoding="utf-8") as f:
            manifest = json.load(f)
    manifest.update(
        {
            "brand_id": brand_id,
            "period": period,
            "updated_at": now,
            "last_delta_count": delta_count,
            "catalog_count": catalog_count,
            "delta_runs": int(manifest.get("delta_runs", 0)) + 1,
        }
    )
    if "created_at" not in manifest:
        manifest["created_at"] = now
    with manifest_path.open("w", encoding="utf-8") as f:
        json.dump(manifest, f, ensure_ascii=False, indent=2)


def finalize_previous_period(brand_id: str, current_period: str) -> str | None:
    root = store_root(brand_id) / "periods"
    if not root.exists():
        return None
    archived: str | None = None
    for old_period_dir in sorted(root.iterdir()):
        if not old_period_dir.is_dir():
            continue
        old_period = old_period_dir.name
        if old_period == current_period:
            continue
        target = archive_dir(brand_id) / old_period
        target.parent.mkdir(parents=True, exist_ok=True)
        if target.exists():
            shutil.rmtree(target)
        shutil.move(str(old_period_dir), str(target))
        archived = old_period
    return archived


@dataclass
class SaveResult:
    total: int
    new_count: int
    updated_count: int
    unchanged_count: int
    removed_count: int
    period: str
    delta_path: str
    catalog_path: str
    archived_period: str | None = None


def save_products(brand_id: str, products: list[dict], output_path: Path) -> SaveResult:
    """전체 스냅샷(latest) + 증분(delta) + 6개월 catalog 저장."""
    rows = normalize_rows(products)
    now_dt = datetime.now()
    now = now_dt.strftime("%Y-%m-%d %H:%M:%S")
    current_period = period_key(now_dt)

    index = bootstrap_index_from_latest(brand_id)
    archived_period = None
    if index.get("period") and index["period"] != current_period:
        archived_period = finalize_previous_period(brand_id, current_period)
        index["period"] = current_period

    known = index.setdefault("products", {})
    current_keys: set[str] = set()

    new_rows: list[dict] = []
    updated_rows: list[dict] = []
    unchanged_count = 0

    for row in rows:
        key = product_key(row.get("product_detail_url", ""))
        if not key:
            continue
        current_keys.add(key)
        fp = row_fingerprint(row)
        prev = known.get(key)
        row["crawled_at"] = row.get("crawled_at") or today_str()

        if not prev:
            known[key] = {"fingerprint": fp, "first_seen": now, "last_seen": now, "period": current_period}
            new_rows.append(row)
            continue

        prev["last_seen"] = now
        if prev.get("fingerprint") != fp:
            prev["fingerprint"] = fp
            prev["period"] = current_period
            updated_rows.append(row)
        else:
            unchanged_count += 1

    removed_count = len(set(known.keys()) - current_keys)

    # UI/조회용 전체 스냅샷은 항상 최신 크롤 결과로 갱신
    _write_csv(rows, SIMPLE_COLUMNS, output_path)
    latest_path = output_path.parent / f"{brand_id}_latest.csv"
    _write_csv(rows, SIMPLE_COLUMNS, latest_path)

    delta_rows = new_rows + updated_rows
    pdir = period_dir(brand_id, current_period)
    delta_dir = pdir / "deltas"
    delta_path_str = ""
    if delta_rows:
        delta_dir.mkdir(parents=True, exist_ok=True)
        delta_file = delta_dir / f"delta_{today_str()}.csv"
        _write_csv(delta_rows, SIMPLE_COLUMNS, delta_file)
        delta_path_str = str(delta_file)

    catalog_path = _period_catalog_path(brand_id, current_period)
    catalog_map = _read_catalog_map(catalog_path)
    for row in rows:
        key = product_key(row.get("product_detail_url", ""))
        if key:
            catalog_map[key] = row
    catalog_rows = list(catalog_map.values())
    _write_catalog(catalog_path, catalog_rows)

    _update_manifest(
        brand_id,
        current_period,
        delta_count=len(delta_rows),
        catalog_count=len(catalog_rows),
    )
    index["period"] = current_period
    _save_index(brand_id, index)

    return SaveResult(
        total=len(rows),
        new_count=len(new_rows),
        updated_count=len(updated_rows),
        unchanged_count=unchanged_count,
        removed_count=removed_count,
        period=current_period,
        delta_path=delta_path_str,
        catalog_path=str(catalog_path),
        archived_period=archived_period,
    )


def storage_summary(brand_id: str) -> dict:
    index = bootstrap_index_from_latest(brand_id)
    current_period = period_key()
    period = index.get("period") or current_period
    pdir = period_dir(brand_id, period)
    manifest_path = pdir / "manifest.json"
    manifest = {}
    if manifest_path.exists():
        with manifest_path.open(encoding="utf-8") as f:
            manifest = json.load(f)
    archive_periods = []
    adir = archive_dir(brand_id)
    if adir.exists():
        archive_periods = sorted(p.name for p in adir.iterdir() if p.is_dir())
    delta_files = []
    deltas = pdir / "deltas"
    if deltas.exists():
        delta_files = sorted(f.name for f in deltas.glob("delta_*.csv"))
    return {
        "brand_id": brand_id,
        "current_period": period,
        "indexed_products": len(index.get("products", {})),
        "manifest": manifest,
        "delta_files": delta_files,
        "catalog_path": str(_period_catalog_path(brand_id, period)),
        "archive_periods": archive_periods,
    }
