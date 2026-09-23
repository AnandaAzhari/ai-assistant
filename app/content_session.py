"""Working Memory untuk Social Media Agent — state satu alur kerja konten yang aktif.

Mengikuti pola `app/document_session.py` (DocumentSessionStore) dan prinsip
"Working Memory" di `docs/agent_memory_v1.md`: state per alur kerja (satu draft
konten yang belum final) disimpan sebagai payload terstruktur berkunci `scope_id`
yang bisa dibentuk ulang dari identitas alur kerja (usaha:platform:content_id),
bukan dari riwayat chat mentah. Boleh dianggap habis/direset setelah konten
selesai (published/retracted) — lihat `clear()`.
"""
from __future__ import annotations

import json
import sqlite3
from contextlib import closing
from pathlib import Path


class ContentSessionStore:
    def __init__(self, db_path: str | Path):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        with closing(sqlite3.connect(self.db_path, timeout=10)) as db, db:
            db.execute("""CREATE TABLE IF NOT EXISTS content_sessions (
                scope_id TEXT PRIMARY KEY, payload TEXT NOT NULL,
                updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP)""")

    @staticmethod
    def build_scope(business: str, platform: str, content_id: str) -> str:
        """Bentuk scope_id konsisten "usaha:platform:content_id" dari identitas alur kerja."""
        parts = [str(business or "").strip(), str(platform or "").strip(), str(content_id or "").strip()]
        if not all(parts):
            raise ValueError(
                "business, platform, dan content_id wajib diisi untuk membentuk scope_id."
            )
        return ":".join(parts)

    def load(self, scope: str) -> dict | None:
        with closing(sqlite3.connect(self.db_path, timeout=10)) as db:
            row = db.execute("SELECT payload FROM content_sessions WHERE scope_id=?", (scope,)).fetchone()
        if row is None:
            return None
        payload = json.loads(row[0])
        if not isinstance(payload, dict) or payload.get("version") != 1:
            raise ValueError("Versi sesi konten tidak dikenali.")
        return payload

    def save(self, scope: str, payload: dict) -> None:
        encoded = json.dumps(payload, ensure_ascii=False)
        with closing(sqlite3.connect(self.db_path, timeout=10)) as db, db:
            db.execute("""INSERT INTO content_sessions(scope_id,payload) VALUES(?,?)
                ON CONFLICT(scope_id) DO UPDATE SET payload=excluded.payload,
                updated_at=CURRENT_TIMESTAMP""", (scope, encoded))

    def clear(self, scope: str) -> None:
        """Hapus working memory satu alur kerja setelah selesai (published/retracted).

        Tidak memengaruhi Long-Term Feedback Memory (`ContentLearningStore`) — riwayat
        belajar tetap tersimpan meskipun working memory-nya dibersihkan.
        """
        with closing(sqlite3.connect(self.db_path, timeout=10)) as db, db:
            db.execute("DELETE FROM content_sessions WHERE scope_id=?", (scope,))

    def search(self, keyword: str, *, limit: int = 5) -> list[dict]:
        """Cari working memory (lintas semua scope_id "usaha:platform:content_id")
        yang payload JSON-nya mengandung `keyword`. Sama polanya dengan
        `DocumentSessionStore.search` — dipakai Lead Agent (/cari_riwayat) supaya
        draft/brief konten yang sedang atau pernah digarap Kirana ikut tercari."""
        keyword = (keyword or "").strip()
        if not keyword:
            return []
        pattern = "%" + keyword.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_") + "%"
        with closing(sqlite3.connect(self.db_path, timeout=10)) as db:
            rows = db.execute(
                """SELECT scope_id, payload, updated_at FROM content_sessions
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
