"""ZARA 브랜드 크롤러"""

import json
import re
from pathlib import Path

from playwright.sync_api import sync_playwright

from app.brands.base import BaseBrandCrawler
from app.core.csv_schema import empty_row, now_timestamp

CONFIG_PATH = Path(__file__).parent / "config.json"
USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/131.0.0.0 Safari/537.36"
)


def load_config() -> dict:
    with CONFIG_PATH.open(encoding="utf-8") as f:
        return json.load(f)


def dismiss_popups(page) -> None:
    for selector in [
        "#onetrust-accept-btn-handler",
        "button:has-text('동의')",
        "button:has-text('Accept')",
        "button:has-text('닫기')",
    ]:
        btn = page.locator(selector).first
        try:
            if btn.count() and btn.is_visible(timeout=1000):
                btn.click()
                page.wait_for_timeout(500)
                break
        except Exception:
            pass


def auto_scroll_to_bottom(page, max_rounds: int = 60, pause_ms: int = 700) -> int:
    prev_count = 0
    stable_rounds = 0

    for _ in range(max_rounds):
        page.evaluate("window.scrollBy(0, window.innerHeight * 0.85)")
        page.wait_for_timeout(pause_ms)

        current_count = page.locator(
            ".product-grid-product-info, li.product-grid-product"
        ).count()
        scroll_height = page.evaluate("document.body.scrollHeight")
        scroll_y = page.evaluate("window.scrollY + window.innerHeight")
        at_bottom = scroll_y >= scroll_height - 50

        if current_count == prev_count and at_bottom:
            stable_rounds += 1
        else:
            stable_rounds = 0
            prev_count = current_count

        if stable_rounds >= 3:
            break

    page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
    page.wait_for_timeout(1000)
    return page.locator(".product-grid-product-info, li.product-grid-product").count()


def get_image_url(component: dict) -> str:
    for color in component.get("detail", {}).get("colors", []):
        for media in color.get("xmedia", []):
            delivery_url = media.get("extraInfo", {}).get("deliveryUrl")
            if delivery_url:
                return delivery_url
            url = media.get("url", "")
            if url and "{width}" in url:
                return url.replace("{width}", "633")
            if url:
                return url

    for media in component.get("xmedia", []):
        delivery_url = media.get("extraInfo", {}).get("deliveryUrl")
        if delivery_url:
            return delivery_url

    return ""


def get_colors(component: dict) -> str:
    colors = []
    for color in component.get("detail", {}).get("colors", []):
        name = (color.get("name") or "").strip()
        if name and name not in colors:
            colors.append(name)
    return ", ".join(colors)


def get_sizes(component: dict) -> str:
    sizes = []
    for color in component.get("detail", {}).get("colors", []):
        for size in color.get("sizes", []):
            label = size.get("name") or size.get("value") or ""
            if label and label not in sizes:
                sizes.append(label)
    return ", ".join(sizes)


def get_material(component: dict) -> str:
    desc = component.get("description") or ""
    if isinstance(desc, list):
        desc = " ".join(str(d) for d in desc)
    detail = component.get("detail", {})
    comp_text = detail.get("composition") or detail.get("material") or ""
    if isinstance(comp_text, list):
        comp_text = " / ".join(str(c) for c in comp_text)
    return (str(comp_text) or str(desc)).strip()


def get_stock_status(component: dict) -> str:
    statuses = []
    for color in component.get("detail", {}).get("colors", []):
        status = color.get("availability", "")
        if status and status not in statuses:
            statuses.append(status)

    if not statuses:
        return "unknown"
    if all(s == "out_of_stock" for s in statuses):
        return "out_of_stock"
    if any(s == "in_stock" for s in statuses):
        return "in_stock"
    return statuses[0]


def extract_category_id(url: str) -> str | None:
    match = re.search(r"[?&]v1=(\d+)", url)
    return match.group(1) if match else None


def component_to_row(component: dict, config: dict) -> dict:
    row = empty_row()
    crawled_at = now_timestamp()
    product_id = component.get("reference") or f"ZR-{component.get('id', '')}"

    ref = component.get("reference") or product_id
    product_url = f"https://www.zara.com/kr/ko/-p{ref}.html" if ref else ""
    img = get_image_url(component)
    if img and not img.startswith("http"):
        img = "https:" + img if img.startswith("//") else ""

    price = str(component.get("price") or "")
    old_price = str(component.get("oldPrice") or "")
    row.update(
        {
            "brand": "ZARA",
            "product_name": (component.get("name") or "").strip(),
            "category": component.get("sectionName") or component.get("familyName") or "",
            "gender": "women",
            "regular_price": old_price or price,
            "current_price": price,
            "discount_rate": "",
            "color_text": get_colors(component),
            "color_chip": "",
            "color_classification_url": "",
            "front_images_url": img,
            "material": get_material(component),
            "details": "",
            "rating": "",
            "reviews": "",
            "product_detail_url": product_url,
            "sizes_available": get_sizes(component),
            "fit": "",
            "length": "",
            "sleeve_length": "",
            "style": "",
            "crawled_at": crawled_at,
            "source_site": config["source_site"],
        }
    )
    return row


def parse_products_from_api(data: dict, config: dict) -> list[dict]:
    products = []
    seen_ids = set()

    for group in data.get("productGroups", []):
        for element in group.get("elements", []):
            for comp in element.get("commercialComponents", []):
                if comp.get("type") != "Product":
                    continue

                product_id = comp.get("id")
                if product_id in seen_ids:
                    continue
                seen_ids.add(product_id)
                products.append(component_to_row(comp, config))

    return products


def extract_products_from_dom(page, config: dict) -> list[dict]:
    raw_items = page.evaluate(
        """() => {
        const blocks = document.querySelectorAll('.product-grid-product-info');
        return Array.from(blocks).map(block => {
            const nameEl = block.querySelector('.product-grid-product-info__name');
            const linkEl = nameEl?.closest('a') || block.querySelector('a.product-link');
            const name = block.querySelector('.product-grid-product-info__name h3, .product-grid-product-info__name')?.innerText?.trim() || '';
            const priceText = block.querySelector('.money-amount__main, .price-current__amount')?.innerText?.trim() || '';
            const price = priceText.replace(/[^0-9]/g, '');
            const colors = Array.from(block.querySelectorAll('.product-grid-product-info-colors-bubble'))
                .map(el => el.getAttribute('aria-label') || '')
                .filter(Boolean);
            const img = block.closest('li')?.querySelector('img')?.src || '';
            const url = linkEl?.href || '';
            return { name, price, colors, img, url };
        }).filter(item => item.name);
    }"""
    )

    products = []
    seen = set()
    crawled_at = now_timestamp()

    for item in raw_items:
        key = item["name"]
        if key in seen:
            continue
        seen.add(key)

        img = item.get("img", "")
        if img and not img.startswith("http"):
            img = "https:" + img if img.startswith("//") else ""
        row = empty_row()
        row.update(
            {
                "brand": "ZARA",
                "product_name": item.get("name", ""),
                "category": "",
                "gender": "women",
                "regular_price": item.get("price", ""),
                "current_price": item.get("price", ""),
                "discount_rate": "",
                "color_text": ", ".join(item.get("colors", [])),
                "front_images_url": img,
                "product_detail_url": item.get("url", ""),
                "crawled_at": crawled_at,
                "source_site": config["source_site"],
            }
        )
        products.append(row)

    return products


class ZaraCrawler(BaseBrandCrawler):
    brand_id = "zara"
    brand_name = "ZARA"
    source_site = "zara.com"

    def crawl(self, url: str | None = None, headless: bool = False) -> list[dict]:
        config = load_config()
        target_url = url or config["default_url"]
        category_id = extract_category_id(target_url) or config["default_category_id"]
        api_url = f"https://www.zara.com/kr/ko/category/{category_id}/products?ajax=true"

        with sync_playwright() as p:
            browser = p.chromium.launch(
                headless=headless,
                args=["--disable-blink-features=AutomationControlled"],
            )
            context = browser.new_context(
                viewport={"width": 1280, "height": 800},
                user_agent=USER_AGENT,
                locale="ko-KR",
            )
            page = context.new_page()
            page.add_init_script(
                "Object.defineProperty(navigator, 'webdriver', { get: () => undefined });"
            )

            page.goto(target_url, wait_until="domcontentloaded", timeout=60000)
            page.wait_for_timeout(2000)
            dismiss_popups(page)
            auto_scroll_to_bottom(page)

            products: list[dict] = []
            try:
                response = context.request.get(api_url)
                if response.ok:
                    products = parse_products_from_api(response.json(), config)
            except Exception:
                pass

            if not products:
                products = extract_products_from_dom(page, config)

            browser.close()

        return products
