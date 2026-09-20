"""Local-only fixtures for driving the static site through a real browser."""

from __future__ import annotations

import os
import socketserver
import threading
from pathlib import Path

import pytest

from tests.browser.drivers import open_browser
from tests.browser.rangeserver import RangeHandler

REPO = Path(__file__).resolve().parents[2]


class _Handler(RangeHandler):
    # Video seeking issues byte-range requests; a server that answers them with the whole
    # file leaves currentTime pinned and every frame identical.
    def __init__(self, *a, **kw):
        super().__init__(*a, directory=str(REPO), **kw)


@pytest.fixture(scope="session")
def site() -> str:
    """Serve the repository over http so web/ and tests/data/ share one origin.

    The extractor builds a <video> from a URL, so the clip must be reachable from the
    page's own origin rather than from the filesystem.
    """
    server = socketserver.ThreadingTCPServer(("127.0.0.1", 0), _Handler)
    server.daemon_threads = True
    threading.Thread(target=server.serve_forever, daemon=True).start()
    yield f"http://127.0.0.1:{server.server_address[1]}"
    server.shutdown()


# Keeps a foreground animation-frame loop running. Only the fallback extraction path
# (used when WebCodecs is unavailable) needs this: it infers from a <video> that is
# never attached to the document, so the frame it reads is only as fresh as the
# compositor. The primary WebCodecs path decodes demuxed samples directly and does not
# depend on presentation, but this costs nothing to leave running for both.
_KEEPALIVE = """
async () => {
  const c = document.createElement('canvas');
  c.width = c.height = 16;
  Object.assign(c.style, { position: 'fixed', top: 0, left: 0, opacity: '0.01' });
  document.body.appendChild(c);
  const ctx = c.getContext('2d');
  let i = 0;
  (function tick() { ctx.fillRect(i++ % 16, 0, 1, 1); requestAnimationFrame(tick); })();
}
"""


@pytest.fixture(scope="session")
def page(site):
    """A driver exposing evaluate(js, arg), on the engine named by GAITLAB_BROWSER.

    `chrome` (default) and `webkit` run through Playwright. `safari` drives the real
    browser via safaridriver -- macOS only, and needs a one-off `sudo safaridriver
    --enable` plus Safari > Develop > Allow Remote Automation -- because Playwright's
    own WebKit build is not Safari's media stack, which is exactly what these tests
    measure; see drivers.py.
    """
    engine = os.environ.get("GAITLAB_BROWSER", "chrome")
    if engine == "safari":
        pytest.importorskip(
            "selenium",
            reason="GAITLAB_BROWSER=safari needs `pip install selenium` and "
                   "`sudo safaridriver --enable`",
        )
    else:
        pytest.importorskip(
            "playwright.sync_api",
            reason="browser extraction tests need `pip install playwright` and a local Chrome",
        )
    with open_browser(engine, f"{site}/web/tests/") as driver:
        driver.evaluate(_KEEPALIVE, None)
        yield driver
