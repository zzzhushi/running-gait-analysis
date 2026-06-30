#!/usr/bin/env python3
"""GaitLab local server — stdlib only (http.server + sqlite3), no pip installs.

Serves the browser UI from web/ and a small JSON API that runs the gaitlab analysis
engine and stores runs in a local SQLite file. Everything stays on your machine.

    python3 server.py            # http://localhost:8000  (opens your browser)
    python3 server.py --port 9000 --no-open

The RTMPose video extractor (extractor/extract_pose.py) is the only part that needs
`pip install` — this server and the engine run on a bare Python.
"""

from __future__ import annotations

import argparse
import glob
import json
import mimetypes
import os
import sqlite3
import subprocess
import sys
import threading
import uuid
import webbrowser
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse, parse_qs

from gaitlab import analyze
from gaitlab.schema import PoseSequence
from gaitlab import synthetic

ROOT = os.path.dirname(os.path.abspath(__file__))
WEB_DIR = os.path.join(ROOT, "web")
DATA_DIR = os.path.join(ROOT, "data")
DB_PATH = os.path.join(DATA_DIR, "gaitlab.db")
VIDEO_DIR = os.path.join(DATA_DIR, "video")
POSE_DIR = os.path.join(DATA_DIR, "pose")
EXTRACTOR = os.path.join(ROOT, "extractor", "extract_pose.py")
INGEST_TIMEOUT = 600  # seconds
SCHEMA_VERSION = 2  # bump when the DB schema changes to auto-wipe and recreate

_extract_locks: dict[str, threading.Lock] = {}
_extract_locks_mu = threading.Lock()


def _get_extract_lock(pose_path: str) -> threading.Lock:
    with _extract_locks_mu:
        if pose_path not in _extract_locks:
            _extract_locks[pose_path] = threading.Lock()
        return _extract_locks[pose_path]


# --------------------------------------------------------------------------- DB
def _init_db() -> None:
    """One-time DB setup at startup: check schema version, wipe if stale, create tables."""
    os.makedirs(DATA_DIR, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        row = conn.execute("SELECT v FROM _meta").fetchone()
        current_v = row["v"] if row else 0
    except Exception:
        current_v = 0
    if current_v != SCHEMA_VERSION:
        for tbl in ("runs", "users", "_meta"):
            conn.execute(f"DROP TABLE IF EXISTS {tbl}")
        conn.commit()
    conn.execute("CREATE TABLE IF NOT EXISTS _meta (v INTEGER)")
    if not conn.execute("SELECT v FROM _meta").fetchone():
        conn.execute("INSERT INTO _meta VALUES (?)", (SCHEMA_VERSION,))
    else:
        conn.execute("UPDATE _meta SET v=?", (SCHEMA_VERSION,))
    conn.execute("""CREATE TABLE IF NOT EXISTS users (
        id TEXT PRIMARY KEY,
        created_at TEXT,
        name TEXT NOT NULL,
        sex TEXT,
        height_cm REAL,
        leg_length_cm REAL
    )""")
    conn.execute("""CREATE TABLE IF NOT EXISTS runs (
        id TEXT PRIMARY KEY,
        created_at TEXT,
        label TEXT,
        view TEXT,
        source TEXT,
        score REAL,
        grade TEXT,
        cadence REAL,
        n_findings INTEGER,
        speed_kmh REAL,
        user_id TEXT REFERENCES users(id),
        result_json TEXT
    )""")
    conn.commit()
    conn.close()


def db() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def store_run(label: str, seq: PoseSequence, profile=None, user_id: str = None) -> dict:
    result = analyze(seq, label=label, profile=profile).to_dict()
    s = result["summary"]
    rid = uuid.uuid4().hex[:12]
    speed_kmh = (profile or {}).get("speed_kmh")
    with db() as conn:
        conn.execute(
            "INSERT INTO runs VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
            (rid, datetime.now(timezone.utc).isoformat(timespec="seconds"),
             s["label"], s["view"], s["source"], s["overall_score"], s["grade"],
             s["cadence"], s["n_findings"], speed_kmh, user_id, json.dumps(result)),
        )
    return {"id": rid, "result": result}


def list_runs(user_id: str = None) -> list:
    cols = "id, created_at, label, view, source, score, grade, cadence, n_findings, speed_kmh, user_id"
    with db() as conn:
        if user_id:
            rows = conn.execute(
                f"SELECT {cols} FROM runs WHERE user_id=? ORDER BY created_at DESC", (user_id,)
            ).fetchall()
        else:
            rows = conn.execute(
                f"SELECT {cols} FROM runs ORDER BY created_at DESC"
            ).fetchall()
    return [dict(r) for r in rows]


def get_run(rid: str):
    with db() as conn:
        row = conn.execute("SELECT result_json FROM runs WHERE id=?", (rid,)).fetchone()
    return json.loads(row["result_json"]) if row else None


def delete_run(rid: str) -> None:
    with db() as conn:
        conn.execute("DELETE FROM runs WHERE id=?", (rid,))


def list_users() -> list:
    with db() as conn:
        rows = conn.execute("SELECT * FROM users ORDER BY created_at").fetchall()
    return [dict(r) for r in rows]


def create_user(name: str, sex: str = None, height_cm: float = None,
                leg_length_cm: float = None) -> dict:
    uid = uuid.uuid4().hex[:12]
    created = datetime.now(timezone.utc).isoformat(timespec="seconds")
    with db() as conn:
        conn.execute("INSERT INTO users VALUES (?,?,?,?,?,?)",
                     (uid, created, name, sex, height_cm, leg_length_cm))
    return {"id": uid, "created_at": created, "name": name,
            "sex": sex, "height_cm": height_cm, "leg_length_cm": leg_length_cm}


def get_user(uid: str) -> dict:
    with db() as conn:
        row = conn.execute("SELECT * FROM users WHERE id=?", (uid,)).fetchone()
    return dict(row) if row else None


def update_user(uid: str, updates: dict) -> dict:
    allowed = {"name", "sex", "height_cm", "leg_length_cm"}
    fields = {k: v for k, v in updates.items() if k in allowed}
    if fields:
        sets = ", ".join(f"{k}=?" for k in fields)
        with db() as conn:
            conn.execute(f"UPDATE users SET {sets} WHERE id=?", [*fields.values(), uid])
    return get_user(uid)


def delete_user(uid: str) -> None:
    with db() as conn:
        conn.execute("UPDATE runs SET user_id=NULL WHERE user_id=?", (uid,))
        conn.execute("DELETE FROM users WHERE id=?", (uid,))


def seed_if_empty(force: bool = False) -> None:
    with db() as conn:
        count = conn.execute("SELECT COUNT(*) AS c FROM runs").fetchone()["c"]
        if force:
            conn.execute("DELETE FROM runs")
            count = 0
    if count == 0:
        with db() as conn:
            row = conn.execute("SELECT id FROM users WHERE name='Demo' LIMIT 1").fetchone()
        demo_id = row["id"] if row else create_user("Demo")["id"]
        for label, seq, cal in synthetic.demo_runs():
            store_run(label, seq, cal, user_id=demo_id)


def list_videos() -> list:
    os.makedirs(VIDEO_DIR, exist_ok=True)
    items = []
    for f in os.listdir(VIDEO_DIR):
        full = os.path.join(VIDEO_DIR, f)
        if not os.path.isfile(full):
            continue
        stem = os.path.splitext(f)[0]
        mtime = os.path.getmtime(full)
        pose_path = os.path.join(POSE_DIR, stem + ".pose.json")
        items.append({
            "stem": stem,
            "filename": f,
            "mtime": datetime.fromtimestamp(mtime, tz=timezone.utc).isoformat(timespec="seconds"),
            "cached": os.path.isfile(pose_path),
        })
    items.sort(key=lambda x: x["mtime"], reverse=True)
    return items


def ingest_video(video_stem: str, view: str, force: bool = False,
                 label: str = "", profile=None, user_id: str = None) -> dict:
    from gaitlab.schema import VIEWS
    safe_stem = os.path.basename(video_stem)
    if not safe_stem or safe_stem != video_stem:
        raise ValueError(f"invalid video stem: {video_stem!r}")
    if view not in VIEWS:
        raise ValueError(f"view must be one of {VIEWS}")

    os.makedirs(VIDEO_DIR, exist_ok=True)
    candidates = [
        f for f in glob.glob(os.path.join(VIDEO_DIR, safe_stem + ".*"))
        if os.path.normpath(f).startswith(os.path.normpath(VIDEO_DIR) + os.sep)
    ]
    if not candidates:
        raise FileNotFoundError(f"no video file for {safe_stem!r} in {VIDEO_DIR}")
    video_path = candidates[0]

    os.makedirs(POSE_DIR, exist_ok=True)
    pose_path = os.path.join(POSE_DIR, safe_stem + ".pose.json")

    extractor_log = ""
    lock = _get_extract_lock(pose_path)
    with lock:
        cached = os.path.isfile(pose_path) and not force
        if not cached:
            r = subprocess.run(
                [sys.executable, EXTRACTOR, video_path,
                 "--view", view, "--accurate", "-o", pose_path],
                capture_output=True, text=True, timeout=INGEST_TIMEOUT,
            )
            extractor_log = r.stderr.strip()
            if r.returncode != 0:
                raise RuntimeError(f"extractor failed: {r.stderr.strip()}")

    with open(pose_path) as fh:
        pose_dict = json.load(fh)
    pose_dict["view"] = view
    seq = PoseSequence.from_pose_dict(pose_dict)
    stored = store_run(label, seq, profile, user_id=user_id)
    stored["cached"] = cached
    stored["video_stem"] = safe_stem
    stored["extractor_log"] = extractor_log
    return stored


# ---------------------------------------------------------------------- handler
class Handler(BaseHTTPRequestHandler):
    server_version = "GaitLab/0.1"

    def log_message(self, fmt, *args):  # quieter console
        pass

    # -- helpers --
    def _json(self, obj, status=200):
        body = json.dumps(obj).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _read_body(self) -> dict:
        length = int(self.headers.get("Content-Length", 0))
        if not length:
            return {}
        return json.loads(self.rfile.read(length).decode("utf-8"))

    def _serve_static_abs(self, full_path: str):
        ctype = mimetypes.guess_type(full_path)[0] or "application/octet-stream"
        with open(full_path, "rb") as fh:
            data = fh.read()
        self.send_response(200)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-cache")
        self.end_headers()
        self.wfile.write(data)

    def _serve_static(self, path: str):
        rel = path.lstrip("/") or "index.html"
        full = os.path.normpath(os.path.join(WEB_DIR, rel))
        if not full.startswith(WEB_DIR) or not os.path.isfile(full):
            self.send_error(404)
            return
        ctype = mimetypes.guess_type(full)[0] or "application/octet-stream"
        with open(full, "rb") as fh:
            data = fh.read()
        self.send_response(200)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-cache")
        self.end_headers()
        self.wfile.write(data)

    # -- routes --
    def do_GET(self):
        parsed = urlparse(self.path)
        path = parsed.path
        qs = parse_qs(parsed.query)
        try:
            if path == "/api/runs":
                uid = (qs.get("user_id") or [None])[0]
                self._json(list_runs(uid))
            elif path == "/api/users":
                self._json(list_users())
            elif path.startswith("/api/users/"):
                uid = path.rsplit("/", 1)[-1]
                user = get_user(uid)
                self._json(user if user else {"error": "not found"}, 200 if user else 404)
            elif path.startswith("/api/runs/"):
                run = get_run(path.rsplit("/", 1)[-1])
                self._json(run, 200 if run else 404)
            elif path == "/api/videos":
                self._json(list_videos())
            elif path.startswith("/api/video/"):
                stem = os.path.basename(path[len("/api/video/"):])
                candidates = [
                    f for f in glob.glob(os.path.join(VIDEO_DIR, stem + ".*"))
                    if os.path.normpath(f).startswith(os.path.normpath(VIDEO_DIR) + os.sep)
                ]
                if not candidates:
                    self.send_error(404)
                else:
                    self._serve_static_abs(candidates[0])
            else:
                self._serve_static(path)
        except Exception as e:  # noqa: BLE001
            self._json({"error": str(e)}, 500)

    def do_PUT(self):
        path = urlparse(self.path).path
        try:
            if path.startswith("/api/users/"):
                uid = path.rsplit("/", 1)[-1]
                body = self._read_body()
                user = update_user(uid, body)
                self._json(user if user else {"error": "not found"}, 200 if user else 404)
            else:
                self.send_error(404)
        except Exception as e:
            self._json({"error": str(e)}, 500)

    def do_POST(self):
        path = urlparse(self.path).path
        try:
            if path == "/api/users":
                body = self._read_body()
                name = (body.get("name") or "").strip()
                if not name:
                    self._json({"error": "name is required"}, 400)
                    return
                self._json(create_user(
                    name=name,
                    sex=body.get("sex") or None,
                    height_cm=body.get("height_cm") or None,
                    leg_length_cm=body.get("leg_length_cm") or None,
                ), 201)
            elif path == "/api/analyze":
                body = self._read_body()
                seq = PoseSequence.from_pose_dict(body["pose"])
                self._json(store_run(body.get("label", ""), seq,
                                     body.get("profile") or body.get("calibration"),
                                     user_id=body.get("user_id") or None))
            elif path.startswith("/api/narrative/"):
                run = get_run(path.rsplit("/", 1)[-1])
                if not run:
                    self._json({"error": "run not found"}, 404)
                else:
                    from gaitlab import narrative
                    self._json(narrative.generate(run))
            elif path == "/api/seed":
                seed_if_empty(force=True)
                self._json(list_runs())
            elif path == "/api/ingest":
                body = self._read_body()
                try:
                    self._json(ingest_video(
                        video_stem=body.get("video", ""),
                        view=body.get("view", ""),
                        force=bool(body.get("force", False)),
                        label=body.get("label", ""),
                        profile=body.get("profile") or None,
                        user_id=body.get("user_id") or None,
                    ))
                except ValueError as e:
                    self._json({"error": str(e)}, 400)
                except FileNotFoundError as e:
                    self._json({"error": str(e)}, 404)
                except subprocess.TimeoutExpired:
                    self._json({"error": f"extraction timed out after {INGEST_TIMEOUT}s"}, 504)
                except RuntimeError as e:
                    self._json({"error": str(e)}, 500)
            else:
                self.send_error(404)
        except Exception as e:  # noqa: BLE001
            self._json({"error": str(e)}, 500)

    def do_DELETE(self):
        path = urlparse(self.path).path
        try:
            if path.startswith("/api/runs/"):
                delete_run(path.rsplit("/", 1)[-1])
                self._json({"ok": True})
            elif path.startswith("/api/users/"):
                delete_user(path.rsplit("/", 1)[-1])
                self._json({"ok": True})
            else:
                self.send_error(404)
        except Exception as e:
            self._json({"error": str(e)}, 500)


def main():
    ap = argparse.ArgumentParser(description="GaitLab local server")
    ap.add_argument("--port", type=int, default=8000)
    ap.add_argument("--no-open", action="store_true", help="don't open a browser")
    args = ap.parse_args()

    _init_db()
    seed_if_empty()
    url = f"http://localhost:{args.port}"
    print(f"GaitLab running at {url}  (Ctrl-C to stop)")
    if not args.no_open:
        try:
            webbrowser.open(url)
        except Exception:
            pass
    ThreadingHTTPServer(("127.0.0.1", args.port), Handler).serve_forever()


if __name__ == "__main__":
    main()
