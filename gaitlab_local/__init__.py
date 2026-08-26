"""Local application boundary for GaitLab.

The portable analysis engine lives in :mod:`gaitlab`.  This sibling package owns the
machine-local concerns that must not be bundled into the Pyodide build: SQLite storage,
filesystem pose caching, extractor subprocesses, and the HTTP adapter. Public objects
are imported from their defining modules so importing a leaf such as ``repository``
does not eagerly load the analysis engine.
"""
