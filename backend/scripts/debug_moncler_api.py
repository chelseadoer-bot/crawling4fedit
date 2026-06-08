import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from playwright.sync_api import sync_playwright

from app.brands.browser_utils import dismiss_popups, launch_browser, new_stealth_context

URL = "https://www.moncler.com/ko-kr/women/ready-to-wear"
search_payloads = []


def main():
    with sync_playwright() as p:
        browser = launch_browser(p, headless=False)
        context, page = new_stealth_context(browser)

        def on_response(response):
            u = response.url
            if "SearchApi-Search" in u and response.status == 200:
                try:
                    search_payloads.append((u, response.json()))
                except Exception:
                    pass

        page.on("response", on_response)
        page.goto(URL, wait_until="domcontentloaded", timeout=120000)
        dismiss_popups(page)
        page.wait_for_timeout(8000)
        for _ in range(8):
            page.evaluate("window.scrollBy(0, 900)")
            page.wait_for_timeout(1500)

        browser.close()

    for u, data in search_payloads[:3]:
        print("URL", u)
        inner = data.get("data") or data
        print("top keys", list(data.keys())[:12])
        if isinstance(inner, dict):
            print("data keys", list(inner.keys())[:15])
            for k in ("products", "productSearch", "hits", "results", "plp"):
                if k in inner:
                    v = inner[k]
                    print(f"  {k} type", type(v))
                    if isinstance(v, dict):
                        print(f"    subkeys", list(v.keys())[:12])
                        for sk in ("products", "hits", "productIds"):
                            if sk in v:
                                arr = v[sk]
                                if isinstance(arr, list) and arr:
                                    print("    sample", json.dumps(arr[0], ensure_ascii=False)[:500])
                    elif isinstance(v, list) and v:
                        print("    sample", json.dumps(v[0], ensure_ascii=False)[:500])
        Path(__file__).resolve().parents[2].joinpath("data/debug_moncler_search.json").write_text(
            json.dumps(data, ensure_ascii=False, indent=2)[:80000],
            encoding="utf-8",
        )
        print("saved data/debug_moncler_search.json")


if __name__ == "__main__":
    main()
