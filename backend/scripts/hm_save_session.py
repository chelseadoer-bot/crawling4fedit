"""H&M 수동 로그인 후 Playwright storage state 저장."""
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from playwright.sync_api import sync_playwright

from app.brands.browser_utils import dismiss_popups, launch_browser

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "data" / "hm_storage_state.json"
URL = "https://www2.hm.com/ko_kr/ladies/shop-by-product/view-all.html"
WAIT_SEC = 90


def page_ready(page) -> bool:
    title = (page.title() or "").lower()
    if "access denied" in title:
        return False
    try:
        n = page.locator('a[href*="productpage"]').count()
        return n >= 3
    except Exception:
        return False


def main():
    OUT.parent.mkdir(parents=True, exist_ok=True)
    with sync_playwright() as p:
        browser = launch_browser(p, headless=False)
        context = browser.new_context(viewport={"width": 1280, "height": 900}, locale="ko-KR")
        page = context.new_page()
        page.goto(URL, wait_until="domcontentloaded", timeout=120000)
        dismiss_popups(page)

        if sys.stdin.isatty():
            print("브라우저에서 H&M 페이지·쿠키 설정을 마친 뒤 Enter...")
            input()
        else:
            print(f"터미널 입력 불가 - 최대 {WAIT_SEC}초 대기 (쿠키/목록 확인)...")
            deadline = time.time() + WAIT_SEC
            while time.time() < deadline:
                dismiss_popups(page)
                if page_ready(page):
                    print("목록 감지됨, 세션 저장합니다.")
                    break
                page.wait_for_timeout(2000)
            else:
                print("대기 시간 초과 — 현재 상태로 저장합니다.")

        context.storage_state(path=str(OUT))
        browser.close()
    print("저장 완료:", OUT)


if __name__ == "__main__":
    main()
