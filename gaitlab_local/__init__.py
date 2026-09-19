"""Machine-local persistence, video ingestion, and HTTP concerns for GaitLab.

Keeping these concerns out of the composition root makes their behavior testable with
explicit paths and dependencies instead of module-global state.
"""
