import json
import re
from pathlib import Path
from urllib.parse import urlparse

from app.brands.balenciaga.crawler import BalenciagaCrawler
from app.brands.barnet.crawler import BarnetCrawler
from app.brands.cm29.crawler import Cm29Crawler
from app.brands.cos.crawler import CosCrawler
from app.brands.dior.crawler import DiorCrawler
from app.brands.hm.crawler import HmCrawler
from app.brands.moncler.crawler import MonclerCrawler
from app.brands.playwright_catalog.crawler import ChanelCrawler
from app.brands.uniqlo.crawler import UniqloCrawler
from app.brands.zara.crawler import ZaraCrawler

PROJECT_ROOT = Path(__file__).resolve().parents[3]
CONFIG_DIR = PROJECT_ROOT / "config"
BRANDS_CONFIG = CONFIG_DIR / "brands.json"

CRAWLER_REGISTRY = {
    "zara": ZaraCrawler,
    "29cm": Cm29Crawler,
    "uniqlo": UniqloCrawler,
    "dior": DiorCrawler,
    "hm": HmCrawler,
    "cos": CosCrawler,
    "balenciaga": BalenciagaCrawler,
    "chanel": ChanelCrawler,
    "moncler": MonclerCrawler,
    "barnet": BarnetCrawler,
}

DOMAIN_CRAWLER_MAP = {
    "zara.com": "zara",
    "www.zara.com": "zara",
    "29cm.co.kr": "29cm",
    "www.29cm.co.kr": "29cm",
    "uniqlo.com": "uniqlo",
    "www.uniqlo.com": "uniqlo",
    "dior.com": "dior",
    "www.dior.com": "dior",
    "hm.com": "hm",
    "www.hm.com": "hm",
    "www2.hm.com": "hm",
    "cos.com": "cos",
    "www.cos.com": "cos",
    "balenciaga.com": "balenciaga",
    "www.balenciaga.com": "balenciaga",
    "chanel.com": "chanel",
    "www.chanel.com": "chanel",
    "moncler.com": "moncler",
    "www.moncler.com": "moncler",
    "the-barnnet.com": "barnet",
    "www.the-barnnet.com": "barnet",
}

def load_brands_config() -> list[dict]:
    if not BRANDS_CONFIG.exists():
        return []
    with BRANDS_CONFIG.open(encoding="utf-8") as f:
        data = json.load(f)
    return data.get("brands", [])


def save_brands_config(brands: list[dict]) -> None:
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    with BRANDS_CONFIG.open("w", encoding="utf-8") as f:
        json.dump({"brands": brands}, f, ensure_ascii=False, indent=2)


GROUP_DISPLAY_NAMES = {
    "zara": "ZARA",
    "uniqlo": "UNIQLO",
    "29cm": "29CM",
    "dior": "DIOR",
    "hm": "H&M",
    "cos": "COS",
    "balenciaga": "BALENCIAGA",
    "chanel": "CHANEL",
    "moncler": "MONCLER",
    "barnet": "THE BARNNET",
}


def group_key(group: str) -> str:
    return slugify(group) or "other"


def default_group_name(crawler_id: str | None, source_site: str) -> str:
    if crawler_id and crawler_id in GROUP_DISPLAY_NAMES:
        return GROUP_DISPLAY_NAMES[crawler_id]
    site = source_site.split(".")[0]
    return site.upper() if site else "기타"


def slugify(name: str) -> str:
    slug = name.strip().lower()
    slug = re.sub(r"[^a-z0-9\s-]", "", slug)
    slug = re.sub(r"[\s_]+", "-", slug)
    slug = re.sub(r"-+", "-", slug).strip("-")
    return slug or "brand"


def extract_source_site(url: str) -> str:
    parsed = urlparse(url)
    host = parsed.netloc.lower().replace("www.", "")
    return host or "unknown"


def detect_crawler_id(url: str) -> str | None:
    host = urlparse(url).netloc.lower()
    if host in DOMAIN_CRAWLER_MAP:
        return DOMAIN_CRAWLER_MAP[host]
    bare = host.replace("www.", "")
    return DOMAIN_CRAWLER_MAP.get(bare)


def get_crawler(crawler_id: str):
    crawler_cls = CRAWLER_REGISTRY.get(crawler_id)
    if not crawler_cls:
        raise ValueError(f"등록되지 않은 크롤러: {crawler_id}")
    return crawler_cls()


def get_brand_meta(brand_id: str) -> dict | None:
    for brand in load_brands_config():
        if brand["id"] == brand_id:
            return brand
    return None


def resolve_crawler_id(brand: dict) -> str | None:
    """브랜드 설정에서 실제 크롤러 키를 결정 (레지스트리에 있는 값만)."""
    for candidate in (
        brand.get("crawler_id"),
        detect_crawler_id(brand.get("default_url") or ""),
        brand.get("id"),
    ):
        if not candidate:
            continue
        key = str(candidate).strip()
        if key in CRAWLER_REGISTRY:
            return key
    return None


def add_brand(name: str, url: str, group: str | None = None) -> dict:
    name = name.strip()
    url = url.strip()
    group = (group or "").strip()
    if not name:
        raise ValueError("카테고리명을 입력해주세요.")
    if not url.startswith("http"):
        raise ValueError("올바른 URL을 입력해주세요.")

    brands = load_brands_config()
    crawler_id = detect_crawler_id(url)
    source_site = extract_source_site(url)
    group_name = group or default_group_name(crawler_id, source_site)

    if crawler_id:
        base_id = f"{crawler_id}-{slugify(name)}"
    else:
        base_id = slugify(name)
    if not base_id or base_id == "brand":
        base_id = crawler_id or source_site.split(".")[0]

    brand_id = base_id
    counter = 1
    while any(b["id"] == brand_id for b in brands):
        brand_id = f"{base_id}-{counter}"
        counter += 1

    brand = {
        "id": brand_id,
        "group": group_name,
        "name": name,
        "enabled": bool(crawler_id),
        "source_site": source_site,
        "crawl_type": "dynamic" if crawler_id else "unsupported",
        "crawler_id": crawler_id,
        "default_url": url,
        "output_dir": f"data/output/{brand_id}",
        "last_crawled_at": None,
        "last_status": None,
    }

    brands.append(brand)
    save_brands_config(brands)

    output_dir = PROJECT_ROOT / "data" / "output" / brand_id
    output_dir.mkdir(parents=True, exist_ok=True)

    return brand


def update_brand(
    brand_id: str,
    name: str | None = None,
    url: str | None = None,
    group: str | None = None,
    category: str | None = None,
) -> dict:
    brands = load_brands_config()
    brand = None
    for item in brands:
        if item["id"] == brand_id:
            brand = item
            break
    if not brand:
        raise ValueError("브랜드를 찾을 수 없습니다.")

    if name is not None:
        name = name.strip()
        if not name:
            raise ValueError("카테고리명을 입력해주세요.")
        brand["name"] = name

    if url is not None:
        url = url.strip()
        if not url.startswith("http"):
            raise ValueError("올바른 URL을 입력해주세요.")
        brand["default_url"] = url
        brand["source_site"] = extract_source_site(url)
        crawler_id = detect_crawler_id(url)
        brand["crawler_id"] = crawler_id
        brand["crawl_type"] = "dynamic" if crawler_id else "unsupported"
        brand["enabled"] = bool(crawler_id)
        if group is None and crawler_id:
            brand["group"] = default_group_name(crawler_id, brand["source_site"])

    if group is not None:
        group = group.strip()
        if not group:
            raise ValueError("사이트(그룹)명을 입력해주세요.")
        brand["group"] = group

    if category is not None:
        brand["category"] = category.strip()

    save_brands_config(brands)
    return brand


def get_brands_by_group(group_name: str) -> list[dict]:
    key = group_key(group_name)
    result = []
    for brand in load_brands_config():
        g = brand.get("group") or brand.get("name", "")
        if group_key(g) == key:
            result.append(brand)
    return result


def delete_brand(brand_id: str) -> None:
    brands = load_brands_config()
    filtered = [b for b in brands if b["id"] != brand_id]
    if len(filtered) == len(brands):
        raise ValueError("브랜드를 찾을 수 없습니다.")
    save_brands_config(filtered)
