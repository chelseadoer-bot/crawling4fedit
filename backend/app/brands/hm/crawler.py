"""H&M 브랜드 크롤러 — PLP DOM + PDP JSON-LD 보강"""

import json
import os
import re
import time
from pathlib import Path
from urllib.parse import urlparse

from playwright.sync_api import Page, sync_playwright

from app.brands.base import BaseBrandCrawler
from app.brands.browser_utils import dismiss_popups, launch_browser, new_stealth_context
from app.core.csv_schema import make_product_row, today_yymmdd

HM_PLATFORM = "www2.hm.com"
BASE_URL = f"https://{HM_PLATFORM}/ko_kr"

EXTRACT_LISTING_JS = """() => {
  const links = Array.from(document.querySelectorAll('a[href*="productpage"]'));
  const seen = new Set();
  const out = [];
  for (const a of links) {
    const href = a.href || '';
    const m = href.match(/productpage\\.(\\d+)\\.html/);
    if (!m) continue;
    const articleId = m[1];
    if (seen.has(articleId)) continue;
    const card = a.closest('article') || a.closest('li') || a.parentElement?.parentElement || a;
    const img = a.querySelector('img') || card?.querySelector('img');
    const alt = (img?.alt || '').trim();
    let name = (a.querySelector('h2,h3,h4')?.innerText || a.getAttribute('aria-label') || '').trim();
    if (!name || name.includes('즐겨찾기')) {
      name = alt.split(' - ')[0]?.trim() || '';
    }
    const colorRaw = alt.includes(' - ') ? alt.split(' - ').slice(1).join(' - ').trim() : '';
    const color = colorRaw.split('/')[0]?.trim() || colorRaw;
    const priceMatch = (card?.innerText || '').match(/₩[\\d,]+/);
    const price = priceMatch ? priceMatch[0].replace(/[^\\d]/g, '') : '';
    const imgSrc = img?.currentSrc || img?.src || img?.getAttribute('data-src') || '';
    if (!name) continue;
    seen.add(articleId);
    out.push({ href, articleId, name, color, price, img: imgSrc });
  }
  return out;
}"""

def _parse_json_ld_product_group(html: str) -> dict | None:
    for match in re.finditer(
        r'<script[^>]*type="application/ld\+json"[^>]*>(.*?)</script>',
        html,
        re.DOTALL | re.IGNORECASE,
    ):
        try:
            data = json.loads(match.group(1))
        except json.JSONDecodeError:
            continue
        nodes = data if isinstance(data, list) else [data]
        for node in nodes:
            if isinstance(node, dict) and node.get("@type") == "ProductGroup":
                return node
    return None


def _parse_pdp_product_group(page: Page) -> dict | None:
    return page.evaluate(
        """() => {
          for (const s of document.querySelectorAll('script[type="application/ld+json"]')) {
            try {
              const j = JSON.parse(s.textContent);
              const nodes = Array.isArray(j) ? j : [j];
              for (const n of nodes) {
                if (n && n['@type'] === 'ProductGroup') return n;
              }
            } catch (e) {}
          }
          return null;
        }"""
    )


def _upgrade_hm_image(url: str) -> str:
    if not url:
        return ""
    if url.startswith("//"):
        url = "https:" + url
    if "imwidth=" in url:
        url = re.sub(r"imwidth=\d+", "imwidth=768", url)
    return url


def _color_hint_tokens(color: str) -> list[str]:
    if not color:
        return []
    return [p.strip().lower() for p in re.split(r"[/,]", color) if p.strip()]


def _variants_for_article(
    product_group: dict,
    article_id: str,
    listing_color: str = "",
) -> list[dict]:
    variants = product_group.get("hasVariant") or []
    if not variants:
        return []

    if article_id:
        matched = [
            v for v in variants
            if article_id in (v.get("offers", {}).get("url") or "")
        ]
        if matched:
            return matched
        matched = [
            v for v in variants
            if str(v.get("sku", "")).startswith(article_id)
        ]
        if matched:
            return matched

    hints = _color_hint_tokens(listing_color)
    if hints:
        by_color: list[dict] = []
        for v in variants:
            vc = (v.get("color") or "").lower()
            if any(h in vc or vc.startswith(h) for h in hints):
                by_color.append(v)
        if by_color:
            return by_color

    if article_id and len(article_id) >= 7:
        group_prefix = article_id[:7]
        matched = [
            v for v in variants
            if group_prefix in (v.get("offers", {}).get("url") or "")
            or str(v.get("sku", "")).startswith(group_prefix)
        ]
        if matched:
            return matched

    return variants if not article_id else []


def _sizes_from_variants(variants: list[dict]) -> list[str]:
    in_stock = [
        v.get("size")
        for v in variants
        if v.get("size")
        and "InStock" in (v.get("offers", {}).get("availability") or "")
    ]
    sizes = in_stock or [v.get("size") for v in variants if v.get("size")]
    return sorted({s for s in sizes if s})


def _extract_pdp_dom_sizes(page: Page) -> list[str]:
    try:
        return page.evaluate(
            """() => {
              const btns = Array.from(document.querySelectorAll('button'))
                .map(b => (b.innerText || '').trim());
              return btns.filter(t => /^(XXS|XS|S|M|L|XL|XXL|2XL|3XL|\\d{2})$/.test(t));
            }"""
        ) or []
    except Exception:
        return []


def _row_from_product_group(
    product_group: dict,
    article_id: str,
    listing_name: str,
    listing_color: str,
    listing_price: str,
    listing_img: str,
    url: str,
    crawled_at: str,
    dom_sizes: list[str] | None = None,
) -> dict:
    name = product_group.get("name") or listing_name
    material = product_group.get("material") or ""
    details = product_group.get("description") or ""
    color = listing_color.split("/")[0].strip() if listing_color else ""
    price = re.sub(r"[^\d]", "", listing_price) if listing_price else ""
    image = _upgrade_hm_image(listing_img)

    color_variants = _variants_for_article(product_group, article_id, listing_color)
    sizes = _sizes_from_variants(color_variants) if color_variants else []
    if not sizes and dom_sizes:
        sizes = sorted(set(dom_sizes))

    if color_variants:
        first = color_variants[0]
        if first.get("color"):
            color = first["color"]
        if first.get("image"):
            image = _upgrade_hm_image(first["image"])
        offer = first.get("offers") or {}
        if offer.get("price"):
            price = str(offer["price"])

    if sizes:
        details = f"사이즈: {', '.join(sizes)}" + (f" | {details}" if details else "")

    return make_product_row(
        platform=HM_PLATFORM,
        brand="H&M",
        product_name=name,
        gender="women",
        regular_price=price,
        current_price=price,
        color=color,
        thumbnail=image,
        material=material,
        details=details,
        product_detail_url=url,
        crawled_at=crawled_at,
    )


def _listing_fallback_row(row: dict, crawled_at: str) -> dict:
    url = row.get("product_detail_url", "")
    listing_color = row.get("color", "")
    return make_product_row(
        platform=HM_PLATFORM,
        brand="H&M",
        product_name=row.get("product_name", ""),
        gender="women",
        regular_price=row.get("regular_price", "") or row.get("current_price", ""),
        current_price=row.get("current_price", "") or row.get("regular_price", ""),
        color=listing_color.split("/")[0].strip() if listing_color else "",
        thumbnail=_upgrade_hm_image(row.get("thumbnail", "")),
        product_detail_url=url,
        crawled_at=crawled_at,
    )


def parse_hm_product(prod: dict, crawled_at: str) -> dict | None:
    """search-services API 응답 파싱 (캡처 시 사용)."""
    title = (
        prod.get("title")
        or prod.get("productName")
        or prod.get("name")
        or prod.get("defaultName")
        or ""
    )
    if not title:
        return None
    pid = str(
        prod.get("articleCode")
        or prod.get("productId")
        or prod.get("id")
        or prod.get("code")
        or ""
    )
    price = ""
    prices = prod.get("prices") or prod.get("price") or {}
    if isinstance(prices, dict):
        price = str(
            prices.get("price")
            or prices.get("value")
            or prices.get("formatted")
            or ""
        )
    elif prices:
        price = str(prices)
    image = ""
    images = prod.get("images") or prod.get("image") or prod.get("modelImage") or []
    if isinstance(images, list) and images:
        first = images[0]
        image = first.get("url") or first.get("src") if isinstance(first, dict) else str(first)
    elif isinstance(images, dict):
        image = images.get("url") or images.get("src") or ""
    elif isinstance(images, str):
        image = images
    url = prod.get("url") or prod.get("link") or prod.get("productUrl") or ""
    if pid and not url:
        url = f"{BASE_URL}/productpage.{pid}.html"
    img = _upgrade_hm_image(
        image if str(image).startswith("http") else (
            "https:" + str(image) if str(image).startswith("//") else str(image)
        )
    )
    color = (
        prod.get("colorName")
        or prod.get("color")
        or prod.get("mainCatName")
        or ""
    )
    price_clean = re.sub(r"[^\d]", "", price) or price
    return make_product_row(
        platform=HM_PLATFORM,
        brand="H&M",
        product_name=title,
        gender="women",
        regular_price=price_clean,
        current_price=price_clean,
        color=color,
        thumbnail=img,
        product_detail_url=url,
        crawled_at=crawled_at,
    )


def extract_hits(payload) -> list[dict]:
    hits: list[dict] = []
    if isinstance(payload, list):
        return [x for x in payload if isinstance(x, dict)]
    if not isinstance(payload, dict):
        return hits
    for key in ("results", "hits", "products", "items", "content", "articles"):
        val = payload.get(key)
        if isinstance(val, list):
            hits.extend(val)
        elif isinstance(val, dict):
            for sub in ("hits", "products", "items"):
                if isinstance(val.get(sub), list):
                    hits.extend(val[sub])
    plp = payload.get("plpList") or payload.get("productList")
    if isinstance(plp, dict):
        for sub in ("productList", "products", "hits"):
            if isinstance(plp.get(sub), list):
                hits.extend(plp[sub])
    return hits


def _storage_state_path() -> Path | None:
    raw = os.environ.get("HM_STORAGE_STATE", "").strip()
    if not raw:
        default = Path(__file__).resolve().parents[4] / "data" / "hm_storage_state.json"
        if default.is_file():
            return default
        return None
    path = Path(raw)
    return path if path.is_file() else None


def _page_id_from_url(url: str) -> str:
    parsed = urlparse(url)
    path = parsed.path.replace(".html", "")
    if "/ko_kr" in path:
        path = path.split("/ko_kr", 1)[-1]
    return path or "/ladies/shop-by-product/view-all"


def _is_blocked(page: Page) -> bool:
    title = page.title().lower()
    if "access denied" in title:
        return True
    try:
        body = page.locator("body").inner_text(timeout=3000)[:400].lower()
        return "access denied" in body
    except Exception:
        return False


def _new_context(browser, storage: Path | None):
    if storage:
        context = browser.new_context(
            viewport={"width": 1280, "height": 900},
            locale="ko-KR",
            storage_state=str(storage),
        )
        page = context.new_page()
        page.add_init_script(
            "Object.defineProperty(navigator, 'webdriver', { get: () => undefined });"
        )
        return context, page
    return new_stealth_context(browser)


def _extract_listing_dom(page: Page) -> list[dict]:
    raw = page.evaluate(EXTRACT_LISTING_JS)
    products: list[dict] = []
    seen: set[str] = set()
    for item in raw:
        article_id = item.get("articleId", "")
        if not article_id or article_id in seen:
            continue
        seen.add(article_id)
        img = item.get("img", "")
        products.append({
            "product_detail_url": item.get("href", ""),
            "product_name": item.get("name", ""),
            "color": item.get("color", ""),
            "thumbnail": _upgrade_hm_image(img),
            "regular_price": item.get("price", ""),
            "current_price": item.get("price", ""),
            "article_id": article_id,
        })
    return products


def _enrich_from_pdp_page(
    context,
    page: Page,
    row: dict,
    crawled_at: str,
    listing_url: str = "",
) -> dict:
    """PDP JSON-LD로 상세 보강 — API 요청 우선, 실패 시 브라우저 탭."""
    url = row.get("product_detail_url", "")
    if not url:
        return row

    listing_name = row.get("product_name", "")
    listing_price = row.get("current_price", "") or row.get("regular_price", "")
    listing_img = row.get("thumbnail", "")
    listing_color = row.get("color", "")

    article_m = re.search(r"productpage\.(\d+)", url)
    article_id = article_m.group(1) if article_m else ""
    referer = listing_url or url

    try:
        resp = context.request.get(
            url,
            headers={"Accept": "text/html", "Referer": referer},
            timeout=60000,
        )
        if resp.ok:
            html = resp.text()
            if "access denied" not in html.lower():
                product_group = _parse_json_ld_product_group(html)
                if product_group:
                    return _row_from_product_group(
                        product_group,
                        article_id,
                        listing_name,
                        listing_color,
                        listing_price,
                        listing_img,
                        url,
                        crawled_at,
                    )
    except Exception:
        pass

    pdp_page = context.new_page()
    try:
        pdp_page.goto(url, wait_until="domcontentloaded", timeout=90000, referer=referer)
        dismiss_popups(pdp_page)
        try:
            pdp_page.wait_for_selector('script[type="application/ld+json"]', timeout=8000)
        except Exception:
            pass
        pdp_page.wait_for_timeout(3000)

        if _is_blocked(pdp_page):
            return _listing_fallback_row(row, crawled_at)

        product_group = _parse_pdp_product_group(pdp_page)
        if not product_group:
            return _listing_fallback_row(row, crawled_at)

        dom_sizes = _extract_pdp_dom_sizes(pdp_page)
        return _row_from_product_group(
            product_group,
            article_id,
            listing_name,
            listing_color,
            listing_price,
            listing_img,
            url,
            crawled_at,
            dom_sizes=dom_sizes,
        )
    except Exception:
        return _listing_fallback_row(row, crawled_at)
    finally:
        pdp_page.close()


class HmCrawler(BaseBrandCrawler):
    brand_id = "hm"
    brand_name = "H&M"
    source_site = "hm.com"

    def crawl(
        self,
        url: str | None = None,
        headless: bool = True,
        on_progress=None,
    ) -> list[dict]:
        target_url = url or f"{BASE_URL}/ladies/shop-by-product/view-all.html"
        for attempt_headless in (headless, False) if headless else (False,):
            try:
                products = self._crawl_once(target_url, attempt_headless, on_progress)
                if products:
                    return products
            except RuntimeError:
                if attempt_headless is False:
                    raise
        raise RuntimeError(
            "H&M 사이트 접근이 차단되었습니다. 일반 Chrome에서 "
            f"{BASE_URL}/ 페이지가 열리는지 확인한 뒤, "
            "backend/scripts/hm_save_session.py 로 쿠키를 저장하거나 "
            "data/hm_storage_state.json 을 준비한 후 다시 시도해주세요."
        )

    def _crawl_once(
        self,
        target_url: str,
        headless: bool,
        on_progress=None,
    ) -> list[dict]:
        crawled_at = today_yymmdd()
        captured: list[dict] = []
        storage = _storage_state_path()

        with sync_playwright() as p:
            browser = launch_browser(p, headless=headless)
            context, page = _new_context(browser, storage)

            def on_response(response):
                u = response.url
                if response.status != 200:
                    return
                if "search-services" not in u and "hmwebservices" not in u:
                    return
                ct = response.headers.get("content-type", "")
                if "json" not in ct:
                    return
                try:
                    captured.append(response.json())
                except Exception:
                    pass

            page.on("response", on_response)
            page.goto(target_url, wait_until="domcontentloaded", timeout=120000)
            dismiss_popups(page)
            page.wait_for_timeout(4000)

            if _is_blocked(page):
                browser.close()
                raise RuntimeError("H&M access denied")

            for _ in range(20):
                page.evaluate("window.scrollBy(0, window.innerHeight * 0.9)")
                page.wait_for_timeout(1000)
                try:
                    btn = page.locator(
                        "button:has-text('더 보기'), button:has-text('Load more'), "
                        "button:has-text('더보기')"
                    ).first
                    if btn.count() and btn.is_visible(timeout=800):
                        btn.click()
                        page.wait_for_timeout(2000)
                except Exception:
                    pass

            products: list[dict] = []
            seen: set[str] = set()
            by_url: dict[str, dict] = {}

            for payload in captured:
                for hit in extract_hits(payload):
                    row = parse_hm_product(hit, crawled_at)
                    if not row:
                        continue
                    key = row.get("product_detail_url") or row.get("product_name")
                    if not key or key in seen:
                        continue
                    seen.add(key)
                    by_url[key] = row

            listing = _extract_listing_dom(page)
            for item in listing:
                key = item.get("product_detail_url", "")
                if not key:
                    continue
                dom_row = make_product_row(
                    platform=HM_PLATFORM,
                    brand="H&M",
                    product_name=item["product_name"],
                    gender="women",
                    regular_price=item.get("regular_price", ""),
                    current_price=item.get("current_price", ""),
                    color=item.get("color", ""),
                    thumbnail=_upgrade_hm_image(item.get("thumbnail", "")),
                    product_detail_url=item["product_detail_url"],
                    crawled_at=crawled_at,
                )
                if key in by_url:
                    api_row = by_url[key]
                    if not dom_row.get("product_name"):
                        dom_row["product_name"] = api_row.get("product_name", "")
                    if not dom_row.get("thumbnail"):
                        dom_row["thumbnail"] = api_row.get("thumbnail", "")
                by_url[key] = dom_row

            products = list(by_url.values())

            if not products:
                browser.close()
                return []

            enriched: list[dict] = []
            total = len(products)
            blocked_streak = 0
            for idx, row in enumerate(products, start=1):
                if blocked_streak >= 3:
                    enriched.append(_listing_fallback_row(row, crawled_at))
                else:
                    item = _enrich_from_pdp_page(
                        context, page, row, crawled_at, listing_url=target_url
                    )
                    if item.get("product_name", "").lower() == "access denied":
                        blocked_streak += 1
                        item = _listing_fallback_row(row, crawled_at)
                    else:
                        blocked_streak = 0
                    enriched.append(item)
                if on_progress:
                    on_progress(len(enriched), idx)
                time.sleep(1.5)

            browser.close()

        if on_progress:
            on_progress(len(enriched), total)

        if not enriched:
            raise RuntimeError("H&M 상품을 수집하지 못했습니다.")
        return enriched
