"""One module per composite pattern — see gaitlab/metrics/spec.py's `Composite`
and `Cond` for the shape. Auto-discovered the same way as gaitlab/metrics/definitions/.
"""

from __future__ import annotations

import importlib
import pkgutil

for _mod in pkgutil.iter_modules(__path__):
    importlib.import_module(f"{__name__}.{_mod.name}")
