"""Playwright 공통 유틸"""

USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/131.0.0.0 Safari/537.36"
)

STEALTH_INIT_SCRIPT = (
    "Object.defineProperty(navigator, 'webdriver', { get: () => undefined });"
)


def launch_browser(playwright, headless: bool = True, channel: str | None = None):
    args = ["--disable-blink-features=AutomationControlled"]
    if channel:
        return playwright.chromium.launch(
            headless=headless,
            channel=channel,
            args=args,
        )
    try:
        return playwright.chromium.launch(
            headless=headless,
            channel="chrome",
            args=args,
        )
    except Exception:
        return playwright.chromium.launch(headless=headless, args=args)


def new_stealth_context(browser, locale: str = "ko-KR"):
    context = browser.new_context(
        viewport={"width": 1280, "height": 900},
        user_agent=USER_AGENT,
        locale=locale,
    )
    page = context.new_page()
    page.add_init_script(STEALTH_INIT_SCRIPT)
    return context, page


def dismiss_popups(page) -> None:
    for selector in [
        "#onetrust-accept-btn-handler",
        "button:has-text('동의')",
        "button:has-text('Accept')",
        "button:has-text('확인')",
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
