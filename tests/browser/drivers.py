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


# page.set_default_timeout() does not bound evaluate(): that setting only applies to
# actions like goto/click/waitFor*, and an evaluate() call runs to completion (or hangs)
# regardless of it. The only way to bound one is to make the awaited JS promise itself
# settle in time, via a race against a JS-side setTimeout.
_TIMEOUT_WRAPPER = """
(arg) => Promise.race([
  (%s)(arg),
  new Promise((_, reject) => setTimeout(
    () => reject(new Error('evaluate() exceeded %ss')), %d)),
])
"""


class _Playwright:
    def __init__(self, page, timeout_s: int):
        self._page = page
        self._timeout_s = timeout_s

    def evaluate(self, js: str, arg):
        wrapped = _TIMEOUT_WRAPPER % (js, self._timeout_s, self._timeout_s * 1000)
        return self._page.evaluate(wrapped, arg)


class _Selenium:
    def __init__(self, driver):
        self._driver = driver

    def evaluate(self, js: str, arg):
        out = self._driver.execute_async_script(_ASYNC_WRAPPER % js, arg)
        if out.get("err"):
            raise RuntimeError(out["err"])
        return out["ok"]


# Bounds every individual browser call so a hang -- GPU init, a network fetch, anything --
# fails with a diagnosable timeout instead of consuming an entire CI job's time budget
# silently. Generous because a WebKit extraction on a shared CI runner is several times
# slower than the same work on developer hardware, and a bound close to the real duration
# turns ordinary runner variance into a failure.
DEFAULT_TIMEOUT_S = 450

@contextmanager
def open_browser(engine: str, url: str, script_timeout_s: int = DEFAULT_TIMEOUT_S):
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

    # Printed with flush, not logged: a hang here has no other signal, and pytest -s
    # still buffers stdout enough in some CI log viewers that an unflushed print can be
    # lost along with the process that never got further than this line.
    def _progress(msg: str) -> None:
        print(f"[drivers] {msg}", flush=True)

    with sync_playwright() as pw:
        _progress(f"launching {engine}")
        if engine == "webkit":
            browser = pw.webkit.launch(headless=False)
        else:
            browser = pw.chromium.launch(
                channel="chrome", headless=False,
                args=["--autoplay-policy=no-user-gesture-required"],
            )
        try:
            _progress("browser launched, opening page")
            page = browser.new_page()
            page.set_default_timeout(script_timeout_s * 1000)
            page.goto(url)
            page.bring_to_front()
            _progress(f"page ready at {url}")
            yield _Playwright(page, script_timeout_s)
        finally:
            browser.close()
