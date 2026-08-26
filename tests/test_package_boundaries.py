"""Import and build checks for the portable-engine/local-application boundary."""

from __future__ import annotations

import ast
import importlib
import pkgutil
from pathlib import Path

from scripts import build_web

REPO = Path(__file__).resolve().parent.parent


def test_local_application_modules_import_cleanly():
    """Import every local module to catch cycles and eager optional dependencies."""
    import gaitlab_local

    names = [
        module.name
        for module in pkgutil.walk_packages(
            gaitlab_local.__path__, prefix="gaitlab_local."
        )
    ]
    assert names, "gaitlab_local package contains no importable modules"
    for name in names:
        importlib.import_module(name)


def test_portable_engine_does_not_import_local_application():
    forbidden = {"gaitlab_local", "server", "extractor"}
    violations = []

    for path in sorted((REPO / "gaitlab").rglob("*.py")):
        tree = ast.parse(path.read_text(), filename=str(path))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                modules = [alias.name for alias in node.names]
            elif isinstance(node, ast.ImportFrom) and node.module:
                modules = [node.module]
            else:
                continue
            for module in modules:
                if module.split(".", 1)[0] in forbidden:
                    violations.append(f"{path.relative_to(REPO)} imports {module}")

    assert not violations, "portable engine crosses local boundary:\n" + "\n".join(violations)


def test_pages_builder_selects_only_the_portable_engine(monkeypatch):
    written: list[tuple[Path, str]] = []

    class RecordingZipFile:
        def __init__(self, path, *_args):
            assert path == build_web.OUT

        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return False

        def write(self, path, arcname):
            written.append((Path(path), arcname))

    # Exercise the production selection loop without writing a generated artifact into
    # either the repository or pytest's temporary directory.
    monkeypatch.setattr(build_web, "OUT", REPO / "unused-gaitlab.zip")
    monkeypatch.setattr(build_web.zipfile, "ZipFile", RecordingZipFile)

    build_web.build_zip()

    assert written, "portable engine bundle is empty"
    assert all(path.is_relative_to(REPO / "gaitlab") for path, _ in written)
    assert all(Path(arcname).parts[0] == "gaitlab" for _, arcname in written)
    assert not any("gaitlab_local" in Path(arcname).parts for _, arcname in written)
