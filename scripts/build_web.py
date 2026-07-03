#!/usr/bin/env python3
"""Bundle the gaitlab/ engine into web/py/gaitlab.zip for the static (Pyodide) build.

Single source of truth: gaitlab/ is never committed under web/. This copies it at build
time — locally via `make web-static`, in CI via .github/workflows/pages.yml. Pyodide
unpacks the zip into its virtual FS; the package tree must stay intact for the dynamic
metric registration (pkgutil.iter_modules) to work.
"""
from __future__ import annotations

import pathlib
import zipfile

ROOT = pathlib.Path(__file__).resolve().parent.parent
SRC = ROOT / "gaitlab"
OUT = ROOT / "web" / "py" / "gaitlab.zip"


def main() -> None:
    OUT.parent.mkdir(parents=True, exist_ok=True)
    n = 0
    with zipfile.ZipFile(OUT, "w", zipfile.ZIP_DEFLATED) as z:
        for path in sorted(SRC.rglob("*.py")):
            if "__pycache__" in path.parts:
                continue
            z.write(path, path.relative_to(ROOT).as_posix())  # arcname -> gaitlab/...
            n += 1
    print(f"wrote {n} files -> {OUT.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
