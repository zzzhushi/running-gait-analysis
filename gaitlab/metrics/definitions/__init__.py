"""One module per metric — the single source of truth.

Every file in this package defines exactly one metric: its bands, coaching
copy, exercises, and its `compute()` formula, in one `register(MetricDef(...))`
call. To add a metric, drop a new file here; nothing else needs editing — this
package auto-imports every module so its `register()` call runs.

To verify nothing was silently skipped (e.g. a copy-pasted file where the
author forgot to change the key), see tests/test_registry.py.
"""

from __future__ import annotations

import importlib
import pkgutil

for _mod in pkgutil.iter_modules(__path__):
    if _mod.name != "composites":
        importlib.import_module(f"{__name__}.{_mod.name}")

from . import composites  # noqa: E402  (composites/__init__.py auto-discovers its own files)
