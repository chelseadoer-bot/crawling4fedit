import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from playwright.sync_api import sync_playwright

from app.brands.browser_utils import dismiss_popups, launch_browser, new_stealth_context

URL = "https://www.moncler.com/ko-kr/women/ready-to-wear"
api_urls = []


def main():
    with sync_playwright() as p:
        browser = launch_browser(p, headless=False)
        context, page = new_stealth_context(browser)

        def on_response(response):
            u = response.url
            if response.status != 200:
                return
            if any(x in u for x in ("api", "product", "catalog", "search", "graphql")):
                try:
                    body = response.json()
                    api_urls.append((u[:120], type(body), list(body.keys())[:8] if isinstance(body, dict) else len(body)))
                except Exception:
                    if "json" in response.headers.get("content-type", ""):
                        api_urls.append((u[:120], "non-json", ""))

        page.on("response", on_response)
        page.goto(URL, wait_until="domcontentloaded", timeout=120000)
        dismiss_popups(page)
        page.wait_for_timeout(5000)
        for _ in range(5):
            page.evaluate("window.scrollBy(0, 800)")
            page.wait_for_timeout(1000)

        samples = page.evaluate(
            """() => {
              const links = Array.from(document.querySelectorAll('a[href]'))
                .map(a => ({ href: a.href, text: (a.innerText||'').trim().slice(0,80), aria: a.getAttribute('aria-label')||'' }))
                .filter(x => x.href.includes('moncler.com') && x.text.length > 2);
              const productish = links.filter(x =>
                /\\/p\\/|\\/product|ready-to-wear\\/[^/]+\\/|cod/i.test(x.href) ||
                (x.text.length > 5 && !/^(Australia|Korea|Japan)/i.test(x.text))
              );
              return {
                title: document.title,
                productLinks: productish.slice(0, 15),
                allPatterns: [...new Set(links.map(x => {
                  try { const u = new URL(x.href); return u.pathname.split('/').filter(Boolean).slice(0,4).join('/'); } catch(e) { return ''; }
                }))].slice(0, 25),
              };
            }"""
        )
        print("TITLE", samples.get("title"))
        print("PATH PATTERNS", samples.get("allPatterns"))
        print("SAMPLE LINKS", json.dumps(samples.get("productLinks"), ensure_ascii=False, indent=2)[:3000])
        print("API CAPTURES", len(api_urls))
        for u in api_urls[:15]:
            print(" ", u)
        browser.close()


if __name__ == "__main__":
    main()
