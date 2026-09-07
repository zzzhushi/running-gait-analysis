"""Stdlib HTTP adapter for :class:`gaitlab_local.application.LocalApplication`."""

from __future__ import annotations

import json
import mimetypes
import os
import shutil
import traceback
from http.server import BaseHTTPRequestHandler
from pathlib import Path
from urllib.parse import parse_qs, unquote, urlparse

from .application import InvalidInput, LocalApplication, NotFoundError
from .ingest import ExtractionError, ExtractionTimeout

DEFAULT_MAX_BODY_BYTES = 128 * 1024 * 1024


class PayloadTooLarge(InvalidInput):
    pass


def make_handler(
    application: LocalApplication,
    web_dir: str | Path,
    *,
    max_body_bytes: int = DEFAULT_MAX_BODY_BYTES,
) -> type[BaseHTTPRequestHandler]:
    """Bind an application and static root to a request-handler class."""
    bound_application = application
    static_root = Path(web_dir).resolve()

    class Handler(BaseHTTPRequestHandler):
        server_version = "GaitLab/0.1"

        def log_message(self, fmt, *args):  # quieter console
            pass

        # -- helpers -------------------------------------------------------
        def _json(self, obj, status: int = 200) -> None:
            body = json.dumps(obj).encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def _read_body(self) -> dict:
            raw_length = self.headers.get("Content-Length", "0")
            try:
                length = int(raw_length)
            except ValueError as exc:
                raise InvalidInput("invalid Content-Length") from exc
            if length < 0:
                raise InvalidInput("invalid Content-Length")
            if length > max_body_bytes:
                raise PayloadTooLarge(
                    f"request body exceeds {max_body_bytes} byte limit"
                )
            if not length:
                return {}
            try:
                value = json.loads(self.rfile.read(length).decode("utf-8"))
            except (UnicodeDecodeError, json.JSONDecodeError) as exc:
                raise InvalidInput("invalid JSON body") from exc
            if not isinstance(value, dict):
                raise InvalidInput("JSON body must be an object")
            return value

        def _serve_file(self, path: Path) -> None:
            content_type = mimetypes.guess_type(path)[0] or "application/octet-stream"
            content_length = path.stat().st_size
            self.send_response(200)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(content_length))
            self.send_header("Cache-Control", "no-cache")
            self.end_headers()
            with path.open("rb") as handle:
                shutil.copyfileobj(handle, self.wfile, length=64 * 1024)

        def _serve_static(self, request_path: str) -> None:
            relative = request_path.lstrip("/") or "index.html"
            candidate = (static_root / relative).resolve()
            try:
                candidate.relative_to(static_root)
            except ValueError:
                self.send_error(404)
                return
            if not candidate.is_file():
                self.send_error(404)
                return
            self._serve_file(candidate)

        def _handle_exception(self, exc: Exception) -> None:
            if isinstance(exc, PayloadTooLarge):
                self._json({"error": str(exc)}, 413)
            elif isinstance(exc, InvalidInput):
                self._json({"error": str(exc)}, 400)
            elif isinstance(exc, (NotFoundError, FileNotFoundError)):
                self._json({"error": str(exc)}, 404)
            elif isinstance(exc, ExtractionTimeout):
                self._json({"error": str(exc)}, 504)
            elif isinstance(exc, ExtractionError):
                self._json(
                    {"error": str(exc), "extractor_log": exc.log}, 500
                )
            else:
                # Unexpected: the console is the operator's only channel here, since
                # log_message is silenced. Keep the wire response free of internals.
                traceback.print_exc()
                self._json(
                    {"error": f"internal server error ({type(exc).__name__})"}, 500
                )

        # -- routes --------------------------------------------------------
        def do_GET(self) -> None:
            parsed = urlparse(self.path)
            path = unquote(parsed.path)
            query = parse_qs(parsed.query)
            try:
                if path == "/api/runs":
                    user_id = (query.get("user_id") or [None])[0]
                    self._json(bound_application.list_runs(user_id))
                elif path == "/api/users":
                    self._json(bound_application.list_users())
                elif path.startswith("/api/users/"):
                    user = bound_application.get_user(path.rsplit("/", 1)[-1])
                    self._json(
                        user if user else {"error": "not found"},
                        200 if user else 404,
                    )
                elif path.startswith("/api/runs/"):
                    run = bound_application.get_run(path.rsplit("/", 1)[-1])
                    self._json(run, 200 if run else 404)
                elif path == "/api/videos":
                    self._json(bound_application.list_videos())
                elif path.startswith("/api/video/"):
                    stem = os.path.basename(path[len("/api/video/") :])
                    try:
                        video_path = bound_application.video_path(stem)
                    except (InvalidInput, FileNotFoundError):
                        self.send_error(404)
                    else:
                        self._serve_file(video_path)
                else:
                    self._serve_static(path)
            except Exception as exc:  # noqa: BLE001
                self._handle_exception(exc)

        def do_PUT(self) -> None:
            path = unquote(urlparse(self.path).path)
            try:
                if path.startswith("/api/users/"):
                    user_id = path.rsplit("/", 1)[-1]
                    user = bound_application.update_user(user_id, self._read_body())
                    self._json(
                        user if user else {"error": "not found"},
                        200 if user else 404,
                    )
                else:
                    self.send_error(404)
            except Exception as exc:  # noqa: BLE001
                self._handle_exception(exc)

        def do_POST(self) -> None:
            path = unquote(urlparse(self.path).path)
            try:
                if path == "/api/users":
                    body = self._read_body()
                    self._json(
                        bound_application.create_user(
                            body.get("name", ""),
                            sex=body.get("sex") or None,
                            height_cm=body.get("height_cm") or None,
                            leg_length_cm=body.get("leg_length_cm") or None,
                        ),
                        201,
                    )
                elif path == "/api/analyze":
                    body = self._read_body()
                    if "pose" not in body:
                        raise InvalidInput("pose is required")
                    profile = body.get("profile") or body.get("calibration")
                    if profile is not None and not isinstance(profile, dict):
                        raise InvalidInput("profile must be an object")
                    self._json(
                        bound_application.analyze_pose(
                            body["pose"],
                            label=body.get("label", ""),
                            profile=profile,
                            user_id=body.get("user_id") or None,
                        )
                    )
                elif path.startswith("/api/narrative/"):
                    self._json(
                        bound_application.generate_narrative(
                            path.rsplit("/", 1)[-1]
                        )
                    )
                elif path == "/api/seed":
                    body = self._read_body()
                    user_id = body.get("user_id") or None
                    bound_application.seed_demo_runs(user_id=user_id)
                    self._json(bound_application.list_runs(user_id))
                elif path == "/api/ingest":
                    body = self._read_body()
                    profile = body.get("profile") or None
                    if profile is not None and not isinstance(profile, dict):
                        raise InvalidInput("profile must be an object")
                    self._json(
                        bound_application.ingest_video(
                            video_stem=body.get("video", ""),
                            view=body.get("view", ""),
                            force=bool(body.get("force", False)),
                            label=body.get("label", ""),
                            profile=profile,
                            user_id=body.get("user_id") or None,
                        )
                    )
                else:
                    self.send_error(404)
            except Exception as exc:  # noqa: BLE001
                self._handle_exception(exc)

        def do_DELETE(self) -> None:
            path = unquote(urlparse(self.path).path)
            try:
                if path.startswith("/api/runs/"):
                    bound_application.delete_run(path.rsplit("/", 1)[-1])
                    self._json({"ok": True})
                elif path.startswith("/api/users/"):
                    bound_application.delete_user(path.rsplit("/", 1)[-1])
                    self._json({"ok": True})
                else:
                    self.send_error(404)
            except Exception as exc:  # noqa: BLE001
                self._handle_exception(exc)

    return Handler
