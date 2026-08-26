"""End-to-end HTTP contract tests using temporary files and SQLite."""

from __future__ import annotations

import json
import subprocess
import threading
from contextlib import contextmanager
from http.client import HTTPConnection
from http.server import ThreadingHTTPServer
from pathlib import Path

from gaitlab.core.schema import KEYPOINTS, PoseSequence
from gaitlab_local.application import LocalApplication
from gaitlab_local.cache import PoseCache
from gaitlab_local.http import make_handler
from gaitlab_local.ingest import VideoIngestor
from gaitlab_local.repository import SQLiteRepository


def _pose(*, source: str = "browser") -> dict:
    point = (0.5, 0.5, 1.0)
    return PoseSequence(
        fps=30,
        width=640,
        height=480,
        view="side-left",
        frames=[[point for _ in KEYPOINTS]],
        source=source,
    ).to_pose_dict()


def _result(sequence: PoseSequence, label: str, profile) -> dict:
    return {
        "summary": {
            "label": label,
            "view": sequence.view,
            "source": sequence.source,
            "overall_score": 91.0,
            "grade": "A",
            "cadence": 176.0,
            "n_findings": 0,
            "profile": profile,
        },
        "pose": sequence.to_pose_dict(),
    }


@contextmanager
def _running_server(application, web_dir, *, max_body_bytes=128 * 1024 * 1024):
    handler = make_handler(
        application, web_dir, max_body_bytes=max_body_bytes
    )
    server = ThreadingHTTPServer(("127.0.0.1", 0), handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield server.server_address
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)


def _request(address, method: str, path: str, body=None, *, raw=False):
    headers = {}
    encoded = None
    if body is not None:
        encoded = body if raw else json.dumps(body).encode("utf-8")
        headers["Content-Type"] = "application/json"
    connection = HTTPConnection(*address, timeout=3)
    try:
        connection.request(method, path, body=encoded, headers=headers)
        response = connection.getresponse()
        payload = response.read()
        content_type = response.getheader("Content-Type", "")
        value = json.loads(payload) if "application/json" in content_type else payload
        return response.status, value
    finally:
        connection.close()


def _application(tmp_path):
    identifiers = iter(("user-1", "run-1", "run-2", "demo-run"))
    repository = SQLiteRepository(
        tmp_path / "gaitlab.db",
        id_factory=lambda: next(identifiers),
        clock=lambda: "2026-01-02T03:04:05+00:00",
    )
    repository.initialize()

    video_dir = tmp_path / "video"
    video_dir.mkdir()
    (video_dir / "clip with space.mp4").write_bytes(b"video bytes")

    def runner(args, **_kwargs):
        output = Path(args[args.index("-o") + 1])
        output.write_text(json.dumps(_pose(source="extractor")), encoding="utf-8")
        return subprocess.CompletedProcess(args, 0, stdout="", stderr="pose ready")

    ingestor = VideoIngestor(
        video_dir,
        PoseCache(tmp_path / "pose"),
        tmp_path / "extract_pose.py",
        runner=runner,
    )
    application = LocalApplication(
        repository,
        ingestor,
        analyze_fn=lambda sequence, *, label="", profile=None: _result(
            sequence, label, profile
        ),
        demo_runs_fn=lambda: (
            ("Demo run", PoseSequence.from_pose_dict(_pose(source="demo")), None),
        ),
        narrative_fn=lambda run: {"title": run["summary"]["label"]},
    )
    return application, repository


def test_http_analysis_ingest_persistence_and_seed_contracts(tmp_path):
    application, repository = _application(tmp_path)
    web_dir = tmp_path / "web"
    web_dir.mkdir()
    (web_dir / "index.html").write_text("<h1>GaitLab</h1>", encoding="utf-8")

    with _running_server(application, web_dir) as address:
        status, index = _request(address, "GET", "/")
        assert status == 200
        assert index == b"<h1>GaitLab</h1>"

        status, user = _request(
            address,
            "POST",
            "/api/users",
            {"name": " Runner ", "height_cm": 170},
        )
        assert status == 201
        assert user["id"] == "user-1"
        assert user["name"] == "Runner"

        status, analyzed = _request(
            address,
            "POST",
            "/api/analyze",
            {
                "pose": _pose(),
                "label": "Browser run",
                "profile": {"speed_kmh": 12.5},
                "user_id": user["id"],
            },
        )
        assert status == 200
        assert set(analyzed) == {"id", "result"}
        assert analyzed["id"] == "run-1"
        assert analyzed["result"]["summary"]["label"] == "Browser run"

        status, ingested = _request(
            address,
            "POST",
            "/api/ingest",
            {
                "video": "clip with space",
                "view": "side-left",
                "label": "Video run",
                "user_id": user["id"],
            },
        )
        assert status == 200
        assert set(ingested) == {
            "id",
            "result",
            "cached",
            "video_stem",
            "extractor_log",
        }
        assert ingested["id"] == "run-2"
        assert ingested["cached"] is False
        assert ingested["video_stem"] == "clip with space"
        assert ingested["extractor_log"] == "pose ready"

        status, runs = _request(
            address, "GET", f"/api/runs?user_id={user['id']}"
        )
        assert status == 200
        assert {run["id"] for run in runs} == {"run-1", "run-2"}
        assert next(run for run in runs if run["id"] == "run-1")["speed_kmh"] == 12.5

        status, stored = _request(address, "GET", "/api/runs/run-1")
        assert status == 200
        assert stored == analyzed["result"]

        status, narrative = _request(address, "POST", "/api/narrative/run-1")
        assert status == 200
        assert narrative == {"title": "Browser run"}

        status, videos = _request(address, "GET", "/api/videos")
        assert status == 200
        assert videos[0]["filename"] == "clip with space.mp4"
        status, video = _request(
            address, "GET", "/api/video/clip%20with%20space"
        )
        assert status == 200
        assert video == b"video bytes"

        # The old route deleted every run before reseeding. It is now additive while
        # keeping the response shape (the complete run list) unchanged.
        status, after_seed = _request(
            address, "POST", "/api/seed", {"user_id": user["id"]}
        )
        assert status == 200
        assert {run["id"] for run in after_seed} == {
            "run-1",
            "run-2",
            "demo-run",
        }

    assert repository.count_runs() == 3


def test_http_maps_client_errors_and_enforces_the_body_limit(tmp_path):
    application, _repository = _application(tmp_path)
    web_dir = tmp_path / "web"
    web_dir.mkdir()
    (web_dir / "index.html").write_text("ok", encoding="utf-8")

    with _running_server(application, web_dir, max_body_bytes=32) as address:
        status, error = _request(
            address, "POST", "/api/users", b"{not-json", raw=True
        )
        assert status == 400
        assert error == {"error": "invalid JSON body"}

        status, error = _request(
            address, "POST", "/api/users", b"x" * 33, raw=True
        )
        assert status == 413
        assert "32 byte limit" in error["error"]

        status, error = _request(
            address,
            "POST",
            "/api/ingest",
            {"video": "x", "view": "bad"},
        )
        assert status == 400
        assert "view must be one of" in error["error"]

        status, missing = _request(address, "GET", "/api/runs/missing")
        assert status == 404
        assert missing is None

        outside = tmp_path / "outside.txt"
        outside.write_text("secret", encoding="utf-8")
        status, _body = _request(address, "GET", "/../outside.txt")
        assert status == 404
