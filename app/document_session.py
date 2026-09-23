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

    def search(self, keyword: str, *, limit: int = 5) -> list[dict]:
        """Cari sesi (lintas SEMUA scope_id — chat pribadi, tiap topik Telegram, tiap
        pelanggan WhatsApp) yang payload JSON-nya mengandung `keyword`. Dipakai Lead
        Agent (perintah /cari_riwayat) supaya admin tidak perlu tahu scope persis atau
        pindah ke topik Nara dulu untuk menelusuri sesi makalah yang pernah/sedang
        dibahas di mana pun. Substring sederhana, tidak sensitif huruf besar/kecil
        (perilaku bawaan LIKE di SQLite untuk teks ASCII) — bukan pencarian semantik."""
        keyword = (keyword or "").strip()
        if not keyword:
            return []
        pattern = "%" + keyword.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_") + "%"
        with closing(sqlite3.connect(self.db_path, timeout=10)) as db:
            rows = db.execute(
                """SELECT scope_id, payload, updated_at FROM document_sessions
                   WHERE payload LIKE ? ESCAPE '\\'
                   ORDER BY updated_at DESC LIMIT ?""",
                (pattern, limit),
            ).fetchall()
        results = []
        for scope_id, payload, updated_at in rows:
            try:
                data = json.loads(payload)
            except (json.JSONDecodeError, TypeError):
                data = {}
            results.append({"scope_id": scope_id, "payload": data, "updated_at": updated_at})
        return results
