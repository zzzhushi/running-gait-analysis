#!/usr/bin/env python3
"""Report which test layers this machine can actually run.

CI runs three layers (see .github/workflows/pages.yml). A dev box missing one of them
runs the others and looks green, so a regression in the missing layer ships. This makes
that visible instead of silent.

    python3 scripts/check_env.py          # report
    python3 scripts/check_env.py --strict # non-zero exit if a required layer can't run
"""

from __future__ import annotations

import argparse
import importlib.util
import shutil
import subprocess
import sys

OK, MISSING = "\033[32m ok \033[0m", "\033[31mMISS\033[0m"
OPT = "\033[33mopt \033[0m"


def has_module(name: str) -> bool:
    try:
        return importlib.util.find_spec(name) is not None
    except (ImportError, ValueError):
        return False


def has_binary(name: str) -> bool:
    return shutil.which(name) is not None


def version_of(binary: str, *args: str) -> str:
    try:
        out = subprocess.run([binary, *args], capture_output=True, text=True, timeout=10)
        return out.stdout.strip().splitlines()[0] if out.stdout.strip() else ""
    except (OSError, subprocess.SubprocessError, IndexError):
        return ""


# (label, present?, required?, what it unlocks, how to install)
def build_checks():
    return [
        ("python >= 3.12", sys.version_info >= (3, 12), True,
         "the engine suite", "https://www.python.org/downloads/"),
        ("pytest", has_module("pytest"), True,
         "`make test` — the numeric source of truth", "pip install -r requirements-dev.txt"),
        ("pyyaml", has_module("yaml"), True,
         "spec-conformance tests (docs/spec/metrics.yaml)", "pip install -r requirements-dev.txt"),
        ("node", has_binary("node"), True,
         "`make test-web` — Pyodide==Python parity + BlazePose mapping unit",
         "https://nodejs.org (v20+), or: brew install node"),
        ("npm", has_binary("npm"), True,
         "installs vitest + pyodide for the web tests", "ships with node"),
        ("ffmpeg", has_binary("ffmpeg"), False,
         "regenerating cadence ground truth from a clip", "brew install ffmpeg"),
        ("ffprobe", has_binary("ffprobe"), False,
         "real per-frame timestamps during pose extraction", "ships with ffmpeg"),
        ("opencv (cv2)", has_module("cv2"), False,
         "pose extraction from video", "pip install -r requirements.txt"),
        ("rtmlib", has_module("rtmlib"), False,
         "the default RTMPose extractor", "pip install -r requirements.txt"),
        ("onnxruntime", has_module("onnxruntime"), False,
         "runs the RTMPose model", "pip install -r requirements.txt"),
    ]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--strict", action="store_true",
                    help="exit non-zero if a required tool is missing")
    args = ap.parse_args()

    checks = build_checks()
    width = max(len(c[0]) for c in checks)

    print("Test-environment check\n")
    missing_required = []
    for label, present, required, unlocks, install in checks:
        mark = OK if present else (MISSING if required else OPT)
        print(f"  [{mark}] {label:<{width}}  {unlocks}")
        if not present:
            print(f"         {'':<{width}}  -> {install}")
            if required:
                missing_required.append(label)

    if has_binary("node"):
        print(f"\n  node {version_of('node', '--version')}")

    print()
    if missing_required:
        print(f"Cannot run every test layer locally — missing: {', '.join(missing_required)}.")
        print("CI will still run them, so a green local suite is NOT proof the branch is green.")
    else:
        print("All required layers can run locally: `make test-all`.")
    print("Optional entries only gate pose extraction and ground-truth regeneration;")
    print("the test suite itself runs from committed pose fixtures.")

    return 1 if (args.strict and missing_required) else 0


if __name__ == "__main__":
    sys.exit(main())
