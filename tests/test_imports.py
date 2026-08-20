"""Every module must import cleanly — the guard against stale first-party imports.

The core/ refactor (289d71a) moved schema.py and events.py into gaitlab/core/ but missed
validate_run.py and extractor/extract_pose_mediapipe.py, which kept importing
`gaitlab.schema`. Both stayed broken for a month because nothing in CI imports them: the
suite only exercises gaitlab/, and the CLIs are invoked as subprocesses or not at all.

Both extractors import their heavy third-party deps (rtmlib, cv2, mediapipe) lazily inside
functions, so importing them here needs nothing installed. A missing *third-party* module
still skips, so this stays green on a bare checkout — but a missing *first-party* module is
exactly the bug this file exists to catch, and fails.
"""

from __future__ import annotations

import importlib
import importlib.util
import pkgutil
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parent.parent

# Scripts outside any package (no __init__.py), so pkgutil can't reach them and a plain
# `import` can't either — they have to be loaded by file path.
STANDALONE = [
    REPO / "server.py",
    REPO / "validate_run.py",
    REPO / "extractor" / "extract_pose.py",
    REPO / "extractor" / "extract_pose_mediapipe.py",
    REPO / "scripts" / "build_web.py",
    REPO / "scripts" / "gen_spec.py",
    REPO / "scripts" / "gen_test_fixture.py",
    REPO / "scripts" / "gen_web_fixtures.py",
]


def _gaitlab_modules() -> list[str]:
    import gaitlab
    return ["gaitlab"] + [
        m.name for m in pkgutil.walk_packages(gaitlab.__path__, prefix="gaitlab.")
    ]


@pytest.mark.parametrize("name", _gaitlab_modules())
def test_engine_module_imports(name):
    importlib.import_module(name)


@pytest.mark.parametrize("path", STANDALONE, ids=lambda p: p.name)
def test_standalone_script_imports(path):
    """Import by file path. Each guards its entry point behind __main__, so this runs only
    module-level constants — no server starts and no database is created."""
    spec = importlib.util.spec_from_file_location(f"_smoke_{path.stem}", path)
    module = importlib.util.module_from_spec(spec)
    try:
        spec.loader.exec_module(module)
    except ModuleNotFoundError as exc:
        missing = exc.name or ""
        if missing == "gaitlab" or missing.startswith("gaitlab."):
            raise AssertionError(
                f"{path.name} imports a first-party module that doesn't exist: {missing}"
            ) from exc
        pytest.skip(f"optional dependency not installed: {missing}")
