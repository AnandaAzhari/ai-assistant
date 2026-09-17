"""Persistent document state, keyed by exact order/session scope."""
from __future__ import annotations

import json
import sqlite3
from contextlib import closing
from pathlib import Path


class DocumentSessionStore:
    def __init__(self, db_path: str | Path):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        with closing(sqlite3.connect(self.db_path, timeout=10)) as db, db:
            db.execute("""CREATE TABLE IF NOT EXISTS document_sessions (
                scope_id TEXT PRIMARY KEY, payload TEXT NOT NULL,
                updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP)""")

    def load(self, scope: str) -> dict | None:
        with closing(sqlite3.connect(self.db_path, timeout=10)) as db:
            row = db.execute("SELECT payload FROM document_sessions WHERE scope_id=?", (scope,)).fetchone()
        if row is None:
            return None
        payload = json.loads(row[0])
        if not isinstance(payload, dict) or payload.get("version") != 1:
            raise ValueError("Versi sesi dokumen tidak dikenali.")
        return payload

    def save(self, scope: str, payload: dict) -> None:
        encoded = json.dumps(payload, ensure_ascii=False)
        with closing(sqlite3.connect(self.db_path, timeout=10)) as db, db:
            db.execute("""INSERT INTO document_sessions(scope_id,payload) VALUES(?,?)
                ON CONFLICT(scope_id) DO UPDATE SET payload=excluded.payload,
                updated_at=CURRENT_TIMESTAMP""", (scope, encoded))
