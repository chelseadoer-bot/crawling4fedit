"""29CM listing API 요청/응답 구조 확인"""
import json
from playwright.sync_api import sync_playwright

URL = "https://www.29cm.co.kr/store/category/list?categoryLargeCode=268100100&categoryMediumCode=268103100&sort=RECOMMENDED&defaultSort=RECOMMENDED&page=1"
USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"

requests_log = []
responses_log = []

with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    context = browser.new_context(user_agent=USER_AGENT, locale="ko-KR")
    page = context.new_page()

    def on_request(request):
        if "listing/items" in request.url and "count" not in request.url:
            try:
                requests_log.append({"url": request.url, "method": request.method, "post": request.post_data})
            except Exception:
                pass

    def on_response(response):
        if "listing/items" in response.url and "count" not in response.url:
            try:
                body = response.json()
                responses_log.append({"url": response.url, "body": body})
            except Exception:
                pass

    page.on("request", on_request)
    page.on("response", on_response)
    page.goto(URL, wait_until="networkidle", timeout=90000)
    browser.close()

print("REQUESTS:")
for r in requests_log:
    print(json.dumps(r, ensure_ascii=False, indent=2)[:2000])

print("\nRESPONSE sample:")
if responses_log:
    data = responses_log[0]["body"]
    print("top keys:", list(data.keys()))
    items = data.get("data", {}).get("items") or data.get("data", {}).get("products") or data.get("data")
    if isinstance(items, dict):
        print("data keys:", list(items.keys()))
        items = items.get("items") or items.get("list") or items.get("content")
    if isinstance(items, list) and items:
        print("item count:", len(items))
        print("first item keys:", list(items[0].keys()))
        print(json.dumps(items[0], ensure_ascii=False, indent=2)[:1500])
