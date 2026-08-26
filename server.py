#!/usr/bin/env python3
"""Run GaitLab's machine-local HTTP application.

The portable analysis engine lives in ``gaitlab``. Local persistence, video
extraction, cache management, and HTTP routing live in ``gaitlab_local``; this module
only selects paths, wires those dependencies, and owns process startup.

    python3 server.py
    python3 server.py --port 9000 --no-open
"""

from __future__ import annotations

import argparse
import webbrowser
from http.server import ThreadingHTTPServer
from pathlib import Path

from gaitlab_local.application import LocalApplication
from gaitlab_local.cache import PoseCache
from gaitlab_local.http import make_handler
from gaitlab_local.ingest import VideoIngestor
from gaitlab_local.repository import SQLiteRepository

ROOT = Path(__file__).resolve().parent
WEB_DIR = ROOT / "web"
DATA_DIR = ROOT / "data"
DB_PATH = DATA_DIR / "gaitlab.db"
VIDEO_DIR = DATA_DIR / "video"
POSE_DIR = DATA_DIR / "pose"
EXTRACTOR = ROOT / "extractor" / "extract_pose.py"
INGEST_TIMEOUT = 600


def build_application(
    *,
    db_path: str | Path = DB_PATH,
    video_dir: str | Path = VIDEO_DIR,
    pose_dir: str | Path = POSE_DIR,
    extractor_path: str | Path = EXTRACTOR,
    ingest_timeout: float = INGEST_TIMEOUT,
) -> LocalApplication:
    """Construct the application without starting a server or seeding data.

    Explicit paths make the composition testable with temporary directories and avoid
    import-time filesystem or database mutations.
    """
    repository = SQLiteRepository(db_path)
    repository.initialize()
    ingestor = VideoIngestor(
        video_dir,
        PoseCache(pose_dir),
        extractor_path,
        timeout_seconds=ingest_timeout,
    )
    return LocalApplication(repository, ingestor)


def main() -> None:
    parser = argparse.ArgumentParser(description="GaitLab local server")
    parser.add_argument("--port", type=int, default=8000)
    parser.add_argument("--no-open", action="store_true", help="don't open a browser")
    args = parser.parse_args()

    application = build_application()
    application.seed_demo_runs(only_if_empty=True)
    handler = make_handler(application, WEB_DIR)

    # config.js defaults to the static (Pages) runtime. Local development opts into
    # the persisted server adapter explicitly so Library/Trends/Combine see SQLite.
    url = f"http://localhost:{args.port}/?runtime=server"
    print(f"GaitLab running at {url}  (Ctrl-C to stop)")
    if not args.no_open:
        try:
            webbrowser.open(url)
        except Exception:
            pass

    with ThreadingHTTPServer(("127.0.0.1", args.port), handler) as server:
        server.serve_forever()


if __name__ == "__main__":
    main()
