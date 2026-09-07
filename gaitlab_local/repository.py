"""SQLite persistence for the local GaitLab application."""

from __future__ import annotations

import json
import sqlite3
import uuid
from collections.abc import Callable, Mapping
from contextlib import closing
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

SCHEMA_VERSION = 2

_V1_RUN_COLUMNS = (
    "id", "created_at", "label", "view", "source", "score", "grade", "cadence",
    "n_findings", "result_json",
)
_V2_RUN_COLUMNS = (
    "id", "created_at", "label", "view", "source", "score", "grade", "cadence",
    "n_findings", "speed_kmh", "user_id", "result_json",
)
_USER_COLUMNS = ("id", "created_at", "name", "sex", "height_cm", "leg_length_cm")


class SchemaError(RuntimeError):
    """The database schema is unknown or internally inconsistent."""


class UnsupportedSchemaVersion(SchemaError):
    """The database was created by a newer, unsupported application version."""


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


class SQLiteRepository:
    """Own connections, migrations, transactions, and run/user persistence.

    ``initialize`` is deliberately non-destructive.  It recognizes the original v1
    run-only schema and migrates it in place; unknown/future schemas raise rather than
    treating user data as disposable.
    """

    def __init__(
        self,
        db_path: str | Path,
        *,
        id_factory: Callable[[], str] | None = None,
        clock: Callable[[], str] | None = None,
    ) -> None:
        self.db_path = Path(db_path)
        self._id_factory = id_factory or (lambda: uuid.uuid4().hex[:12])
        self._clock = clock or _utc_now

    def connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        return conn

    def initialize(self) -> None:
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        conn = self.connect()
        try:
            with conn:
                # Legacy sqlite3 transaction control opens an implicit transaction only
                # for DML, so the DDL below would otherwise autocommit statement by
                # statement and an interrupted migration could not be rolled back.
                conn.execute("BEGIN")
                version = self._detect_version(conn)
                if version > SCHEMA_VERSION:
                    raise UnsupportedSchemaVersion(
                        f"database schema version {version} is newer than supported "
                        f"version {SCHEMA_VERSION}"
                    )
                if version == 0:
                    self._create_v2(conn)
                    version = SCHEMA_VERSION
                elif version == 1:
                    self._migrate_v1_to_v2(conn)
                    version = SCHEMA_VERSION
                elif version == SCHEMA_VERSION and not self._table_exists(conn, "_meta"):
                    self._write_version(conn, version)

                if version != SCHEMA_VERSION:
                    raise UnsupportedSchemaVersion(
                        f"no migration from database schema version {version} to "
                        f"{SCHEMA_VERSION}"
                    )
                self._verify_v2(conn)
        finally:
            conn.close()

    # -- schema -------------------------------------------------------------
    @staticmethod
    def _table_exists(conn: sqlite3.Connection, name: str) -> bool:
        return conn.execute(
            "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (name,)
        ).fetchone() is not None

    @staticmethod
    def _columns(conn: sqlite3.Connection, table: str) -> tuple[str, ...]:
        return tuple(row["name"] for row in conn.execute(f"PRAGMA table_info({table})"))

    def _detect_version(self, conn: sqlite3.Connection) -> int:
        if self._table_exists(conn, "_meta"):
            try:
                rows = conn.execute("SELECT v FROM _meta").fetchall()
            except sqlite3.DatabaseError as exc:
                raise SchemaError("could not read database schema metadata") from exc
            if len(rows) != 1 or not isinstance(rows[0]["v"], int):
                raise SchemaError(
                    "database schema metadata must contain exactly one integer version"
                )
            return int(rows[0]["v"])

        tables = {
            row["name"]
            for row in conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'"
            )
        }
        if not tables:
            return 0
        if tables == {"runs"} and self._columns(conn, "runs") == _V1_RUN_COLUMNS:
            return 1
        if {"runs", "users"}.issubset(tables):
            run_columns = set(self._columns(conn, "runs"))
            user_columns = set(self._columns(conn, "users"))
            if set(_V2_RUN_COLUMNS).issubset(run_columns) and set(
                _USER_COLUMNS
            ).issubset(user_columns):
                return 2
        raise SchemaError(
            "database has an unrecognized schema; refusing to modify or delete existing data"
        )

    def _create_v2(self, conn: sqlite3.Connection) -> None:
        conn.execute("CREATE TABLE _meta (v INTEGER NOT NULL)")
        conn.execute(
            """CREATE TABLE users (
                id TEXT PRIMARY KEY,
                created_at TEXT,
                name TEXT NOT NULL,
                sex TEXT,
                height_cm REAL,
                leg_length_cm REAL
            )"""
        )
        conn.execute(
            """CREATE TABLE runs (
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
            )"""
        )
        self._write_version(conn, SCHEMA_VERSION)

    def _migrate_v1_to_v2(self, conn: sqlite3.Connection) -> None:
        if not self._table_exists(conn, "runs") or self._columns(conn, "runs") != _V1_RUN_COLUMNS:
            raise SchemaError("database claims schema v1 but its runs table does not match v1")
        conn.execute(
            """CREATE TABLE IF NOT EXISTS users (
                id TEXT PRIMARY KEY,
                created_at TEXT,
                name TEXT NOT NULL,
                sex TEXT,
                height_cm REAL,
                leg_length_cm REAL
            )"""
        )
        conn.execute("ALTER TABLE runs ADD COLUMN speed_kmh REAL")
        conn.execute("ALTER TABLE runs ADD COLUMN user_id TEXT REFERENCES users(id)")
        self._write_version(conn, SCHEMA_VERSION)

    @staticmethod
    def _write_version(conn: sqlite3.Connection, version: int) -> None:
        conn.execute("CREATE TABLE IF NOT EXISTS _meta (v INTEGER NOT NULL)")
        conn.execute("DELETE FROM _meta")
        conn.execute("INSERT INTO _meta(v) VALUES (?)", (version,))

    def _verify_v2(self, conn: sqlite3.Connection) -> None:
        if not self._table_exists(conn, "runs") or not self._table_exists(conn, "users"):
            raise SchemaError("database schema v2 is missing the runs or users table")
        if not set(_V2_RUN_COLUMNS).issubset(self._columns(conn, "runs")):
            raise SchemaError("database schema v2 has an incompatible runs table")
        if not set(_USER_COLUMNS).issubset(self._columns(conn, "users")):
            raise SchemaError("database schema v2 has an incompatible users table")

    # -- runs --------------------------------------------------------------
    def create_run(
        self,
        result: Mapping[str, Any],
        *,
        user_id: str | None = None,
        speed_kmh: float | None = None,
    ) -> str:
        summary = result["summary"]
        run_id = self._id_factory()
        with closing(self.connect()) as conn, conn:
            conn.execute(
                """INSERT INTO runs (
                    id, created_at, label, view, source, score, grade, cadence,
                    n_findings, speed_kmh, user_id, result_json
                ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?)""",
                (
                    run_id,
                    self._clock(),
                    summary["label"],
                    summary["view"],
                    summary["source"],
                    summary["overall_score"],
                    summary["grade"],
                    summary["cadence"],
                    summary["n_findings"],
                    speed_kmh,
                    user_id,
                    json.dumps(result),
                ),
            )
        return run_id

    def list_runs(self, user_id: str | None = None) -> list[dict[str, Any]]:
        columns = (
            "id, created_at, label, view, source, score, grade, cadence, "
            "n_findings, speed_kmh, user_id"
        )
        with closing(self.connect()) as conn, conn:
            if user_id:
                rows = conn.execute(
                    f"SELECT {columns} FROM runs WHERE user_id=? ORDER BY created_at DESC",
                    (user_id,),
                ).fetchall()
            else:
                rows = conn.execute(
                    f"SELECT {columns} FROM runs ORDER BY created_at DESC"
                ).fetchall()
        return [dict(row) for row in rows]

    def get_run(self, run_id: str) -> dict[str, Any] | None:
        with closing(self.connect()) as conn, conn:
            row = conn.execute(
                "SELECT result_json FROM runs WHERE id=?", (run_id,)
            ).fetchone()
        return json.loads(row["result_json"]) if row else None

    def delete_run(self, run_id: str) -> None:
        with closing(self.connect()) as conn, conn:
            conn.execute("DELETE FROM runs WHERE id=?", (run_id,))

    def count_runs(self) -> int:
        with closing(self.connect()) as conn, conn:
            return int(conn.execute("SELECT COUNT(*) FROM runs").fetchone()[0])

    def run_identities(self, user_id: str) -> set[tuple[str, str, str]]:
        with closing(self.connect()) as conn, conn:
            rows = conn.execute(
                "SELECT label, view, source FROM runs WHERE user_id=?", (user_id,)
            ).fetchall()
        return {(row["label"], row["view"], row["source"]) for row in rows}

    # -- users -------------------------------------------------------------
    def list_users(self) -> list[dict[str, Any]]:
        with closing(self.connect()) as conn, conn:
            rows = conn.execute("SELECT * FROM users ORDER BY created_at").fetchall()
        return [dict(row) for row in rows]

    def create_user(
        self,
        name: str,
        sex: str | None = None,
        height_cm: float | None = None,
        leg_length_cm: float | None = None,
    ) -> dict[str, Any]:
        user = {
            "id": self._id_factory(),
            "created_at": self._clock(),
            "name": name,
            "sex": sex,
            "height_cm": height_cm,
            "leg_length_cm": leg_length_cm,
        }
        with closing(self.connect()) as conn, conn:
            conn.execute(
                """INSERT INTO users
                   (id, created_at, name, sex, height_cm, leg_length_cm)
                   VALUES (:id, :created_at, :name, :sex, :height_cm, :leg_length_cm)""",
                user,
            )
        return user

    def get_user(self, user_id: str) -> dict[str, Any] | None:
        with closing(self.connect()) as conn, conn:
            row = conn.execute("SELECT * FROM users WHERE id=?", (user_id,)).fetchone()
        return dict(row) if row else None

    def find_user_by_name(self, name: str) -> dict[str, Any] | None:
        with closing(self.connect()) as conn, conn:
            row = conn.execute(
                "SELECT * FROM users WHERE name=? ORDER BY created_at LIMIT 1", (name,)
            ).fetchone()
        return dict(row) if row else None

    def update_user(self, user_id: str, updates: Mapping[str, Any]) -> dict[str, Any] | None:
        allowed = {"name", "sex", "height_cm", "leg_length_cm"}
        fields = {key: value for key, value in updates.items() if key in allowed}
        if fields:
            assignments = ", ".join(f"{key}=?" for key in fields)
            with closing(self.connect()) as conn, conn:
                conn.execute(
                    f"UPDATE users SET {assignments} WHERE id=?",
                    [*fields.values(), user_id],
                )
        return self.get_user(user_id)

    def delete_user(self, user_id: str) -> None:
        with closing(self.connect()) as conn, conn:
            conn.execute("UPDATE runs SET user_id=NULL WHERE user_id=?", (user_id,))
            conn.execute("DELETE FROM users WHERE id=?", (user_id,))
