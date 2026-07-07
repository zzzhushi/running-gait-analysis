#!/usr/bin/env python3
"""Bundle the gaitlab/ engine into web/py/gaitlab.zip for the static (Pyodide) build,
and (optionally) cache-bust the static asset URLs.

Single source of truth: gaitlab/ is never committed under web/. This copies it at build
time — locally via `make web-static`, in CI via .github/workflows/pages.yml. Pyodide
unpacks the zip into its virtual FS; the package tree must stay intact for the dynamic
metric registration (pkgutil.iter_modules) to work.

Cache-busting (CI only): GitHub Pages serves every asset with a 10-minute max-age and no
way to set headers, so after a redeploy a returning browser can keep running stale JS or
a stale engine zip. Passing `--version <sha>` stamps `?v=<sha>` onto every local module
import, the engine-zip URL, and index.html's entry script/stylesheet, so a new deploy is
always fetched fresh. Run without `--version` for local dev (localhost hard-refreshes
fine and unversioned imports keep the working tree clean).
"""
from __future__ import annotations

import argparse
import pathlib
import re
import zipfile

ROOT = pathlib.Path(__file__).resolve().parent.parent
SRC = ROOT / "gaitlab"
WEB = ROOT / "web"
OUT = WEB / "py" / "gaitlab.zip"


def build_zip() -> None:
    OUT.parent.mkdir(parents=True, exist_ok=True)
    n = 0
    with zipfile.ZipFile(OUT, "w", zipfile.ZIP_DEFLATED) as z:
        for path in sorted(SRC.rglob("*.py")):
            if "__pycache__" in path.parts:
                continue
            z.write(path, path.relative_to(ROOT).as_posix())  # arcname -> gaitlab/...
            n += 1
    print(f"wrote {n} files -> {OUT.relative_to(ROOT)}")


def _bust(url: str, version: str) -> str:
    return url if "?v=" in url else f"{url}?v={version}"


def cache_bust(version: str) -> None:
    """Append ?v=<version> to local module imports, the engine zip, and index.html."""
    # relative `from "./x.js"` / `from "../x.js"` specifiers in every module
    imp = re.compile(r'(from\s+["\'])(\.\.?/[^"\']+?\.js)(["\'])')
    n = 0
    for js in sorted(WEB.rglob("*.js")):
        if "py" in js.relative_to(WEB).parts:
            continue
        text = js.read_text()
        new = imp.sub(lambda m: m.group(1) + _bust(m.group(2), version) + m.group(3), text)
        if new != text:
            js.write_text(new)
            n += 1
    # the engine-zip URL fetched at runtime + the visible build stamp (both in config.js)
    cfg = WEB / "js" / "config.js"
    text = re.sub(r'(["\'])(\.\/py\/gaitlab\.zip)(["\'])',
                  lambda m: m.group(1) + _bust(m.group(2), version) + m.group(3),
                  cfg.read_text())
    text = text.replace('export const BUILD_VERSION = "dev";',
                        f'export const BUILD_VERSION = "{version}";')
    cfg.write_text(text)
    # index.html entry script + stylesheet
    html = WEB / "index.html"
    doc = re.sub(r'((?:src|href)=["\'])(\.\/(?:js\/main\.js|css\/app\.css))(["\'])',
                 lambda m: m.group(1) + _bust(m.group(2), version) + m.group(3),
                 html.read_text())
    html.write_text(doc)
    print(f"cache-busted {n} modules + config.js + index.html with ?v={version}")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--version", help="cache-bust token (e.g. commit sha); omit for local dev")
    args = ap.parse_args()
    build_zip()
    if args.version:
        cache_bust(args.version)


if __name__ == "__main__":
    main()
