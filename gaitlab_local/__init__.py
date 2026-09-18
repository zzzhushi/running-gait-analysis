"""Local application boundary for GaitLab.

The portable analysis engine lives in :mod:`gaitlab`.  This sibling package owns the
machine-local concerns that must not be bundled into the Pyodide build: SQLite storage,
filesystem pose caching, extractor subprocesses, and the HTTP adapter. This package
deliberately re-exports nothing: importing a leaf pulls in only what that leaf needs,
so ``repository`` stays free of the analysis engine entirely, while ``cache``,
``ingest``, and ``application`` import ``gaitlab`` because they operate on its types.
"""
