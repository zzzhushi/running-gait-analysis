"""One evaluate() over the browsers this suite can drive.

Playwright cannot drive Safari itself, only its own WebKit build, whose media stack is
not Safari's — and media presentation is precisely what these tests measure. Safari is
therefore driven through safaridriver instead, at the cost of being macOS-only and
needing a one-off `safaridriver --enable`.
"""

from __future__ import annotations

from contextlib import contextmanager

# Selenium runs scripts to completion and has no await; an async body reports back
# through the callback it appends to the argument list.
_ASYNC_WRAPPER = """
const done = arguments[arguments.length - 1];
const arg = arguments[0];
(%s)(arg).then(v => done({ ok: v })).catch(e => done({ err: String(e && e.stack || e) }));
"""


class _Playwright:
    def __init__(self, page):
        self._page = page

    def evaluate(self, js: str, arg):
        return self._page.evaluate(js, arg)


class _Selenium:
    def __init__(self, driver):
        self._driver = driver

    def evaluate(self, js: str, arg):
        out = self._driver.execute_async_script(_ASYNC_WRAPPER % js, arg)
        if out.get("err"):
            raise RuntimeError(out["err"])
        return out["ok"]


@contextmanager
def open_browser(engine: str, url: str, script_timeout_s: int = 1800):
    """Yield a driver exposing evaluate(js, arg), with `url` loaded."""
    if engine == "safari":
        from selenium import webdriver

        driver = webdriver.Safari()
        driver.set_script_timeout(script_timeout_s)
        try:
            driver.get(url)
            yield _Selenium(driver)
        finally:
            driver.quit()
        return

    from playwright.sync_api import sync_playwright

    with sync_playwright() as pw:
        if engine == "webkit":
            browser = pw.webkit.launch(headless=False)
        else:
            browser = pw.chromium.launch(
                channel="chrome", headless=False,
                args=["--autoplay-policy=no-user-gesture-required"],
            )
        try:
            page = browser.new_page()
            page.set_default_timeout(0)
            page.goto(url)
            page.bring_to_front()
            yield _Playwright(page)
        finally:
            browser.close()
