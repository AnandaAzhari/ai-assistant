"""Interaction Log — Fase 5 (Evaluasi & Observability) di `docs/roadmap_customer_channel_v1.md`.

Tujuan Fase 5: tahu apakah jawaban AI dari tiap agent benar-benar bagus, bukan cuma
"kodenya jalan tanpa error" — ini beda dari `tests/` yang menguji logika Python
deterministik. Modul ini menyimpan setiap interaksi produksi (input pelanggan/owner +
jawaban agent) sebagai data yang bisa ditinjau ulang, bukan cuma dikirim lalu dilupakan,
dan menyediakan alur tinjauan berkala (mingguan/bulanan) — lihat `sample_for_review()` dan
`mark_reviewed()`. Terhubung ke prinsip Long-Term Feedback Memory di
`docs/agent_memory_v1.md`: sama-sama append-only, tapi log ini untuk kualitas jawaban
AI secara umum (dinilai owner "baik/perlu_perbaikan/tidak_baik"), berbeda dari
`app/content_learning.py` yang khusus utuk gaya/performa konten Social Media Agent.

Privasi: hanya menyimpan potongan teks (dipotong ke panjang wajar) untuk keperluan
tinjauan kualitas, bukan menyimpan token/API key/data pembayaran apa pun — mengikuti
`policies/security_policy.md`.
"""
from __future__ import annotations

import sqlite3
import uuid
from contextlib import closing
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

ALLOWED_REVIEW_LABELS = {"baik", "perlu_perbaikan", "tidak_baik"}
_MAX_TEXT_LENGTH = 4000


@dataclass(frozen=True)
class InteractionLogEntry:
    id: str
    created_at: str
    agent: str
    scope: str
    channel: str
    input_text: str
    output_text: str
    status: str
    model: str
    reviewed: bool
    review_label: str
    review_note: str
    reviewed_by: str
    reviewed_at: str


def _row_to_entry(row: sqlite3.Row) -> InteractionLogEntry:
    return InteractionLogEntry(
        id=row["id"], created_at=row["created_at"], agent=row["agent"], scope=row["scope"],
        channel=row["channel"], input_text=row["input_text"], output_text=row["output_text"],
        status=row["status"], model=row["model"], reviewed=bool(row["reviewed"]),
        review_label=row["review_label"], review_note=row["review_note"],
        reviewed_by=row["reviewed_by"], reviewed_at=row["reviewed_at"],
    )


class InteractionLogStore:
    def __init__(self, db_path: str | Path):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        with closing(sqlite3.connect(self.db_path, timeout=10)) as db, db:
            db.execute("""CREATE TABLE IF NOT EXISTS agent_interactions (
                id TEXT PRIMARY KEY,
                created_at TEXT NOT NULL,
                agent TEXT NOT NULL,
                scope TEXT NOT NULL DEFAULT '',
                channel TEXT NOT NULL DEFAULT '',
                input_text TEXT NOT NULL DEFAULT '',
                output_text TEXT NOT NULL DEFAULT '',
                status TEXT NOT NULL DEFAULT '',
                model TEXT NOT NULL DEFAULT '',
                reviewed INTEGER NOT NULL DEFAULT 0,
                review_label TEXT NOT NULL DEFAULT '',
                review_note TEXT NOT NULL DEFAULT '',
                reviewed_by TEXT NOT NULL DEFAULT '',
                reviewed_at TEXT NOT NULL DEFAULT '')""")
            db.execute(
                "CREATE INDEX IF NOT EXISTS idx_interactions_review "
                "ON agent_interactions(agent, reviewed, created_at)"
            )

    def _connect(self) -> sqlite3.Connection:
        db = sqlite3.connect(self.db_path, timeout=10)
        db.row_factory = sqlite3.Row
        return db

    def log(
        self, agent: str, scope: str, channel: str, input_text: str, output_text: str, *,
        status: str = "", model: str = "",
    ) -> InteractionLogEntry:
        agent = str(agent or "").strip()
        if not agent:
            raise ValueError("agent wajib diisi.")
        entry = InteractionLogEntry(
            id=str(uuid.uuid4()), created_at=datetime.now().isoformat(timespec="seconds"),
            agent=agent, scope=str(scope or "").strip(), channel=str(channel or "").strip(),
            input_text=str(input_text or "").strip()[:_MAX_TEXT_LENGTH],
            output_text=str(output_text or "").strip()[:_MAX_TEXT_LENGTH],
            status=str(status or "").strip(), model=str(model or "").strip(),
            reviewed=False, review_label="", review_note="", reviewed_by="", reviewed_at="",
        )
        with closing(self._connect()) as db, db:
            db.execute(
                """INSERT INTO agent_interactions
                   (id,created_at,agent,scope,channel,input_text,output_text,status,model,
                    reviewed,review_label,review_note,reviewed_by,reviewed_at)
                   VALUES(?,?,?,?,?,?,?,?,?,0,'','','','')""",
                (entry.id, entry.created_at, entry.agent, entry.scope, entry.channel,
                 entry.input_text, entry.output_text, entry.status, entry.model),
            )
        return entry

    def get(self, entry_id: str) -> InteractionLogEntry | None:
        with closing(self._connect()) as db:
            row = db.execute("SELECT * FROM agent_interactions WHERE id=?", (entry_id,)).fetchone()
        return _row_to_entry(row) if row else None

    def sample_for_review(
        self, agent: str | None = None, *, limit: int = 10, only_unreviewed: bool = True,
    ) -> list[InteractionLogEntry]:
        """Ambil sampel interaksi produksi untuk tinjauan berkala — paling lama dulu
        (FIFO), supaya backlog tinjauan tidak menumpuk di satu ujung."""
        query = "SELECT * FROM agent_interactions WHERE 1=1"
        params: list = []
        if agent:
            query += " AND agent=?"
            params.append(str(agent).strip())
        if only_unreviewed:
            query += " AND reviewed=0"
        query += " ORDER BY created_at ASC, rowid ASC LIMIT ?"
        params.append(int(limit))
        with closing(self._connect()) as db:
            rows = db.execute(query, params).fetchall()
        return [_row_to_entry(row) for row in rows]

    def mark_reviewed(
        self, entry_id: str, label: str, *, note: str = "", reviewed_by: str = "",
    ) -> InteractionLogEntry:
        label = str(label or "").strip()
        if label not in ALLOWED_REVIEW_LABELS:
            raise ValueError(f"label tidak dikenali: {label!r}. Pilihan: {sorted(ALLOWED_REVIEW_LABELS)}")
        existing = self.get(entry_id)
        if existing is None:
            raise ValueError(f"Interaksi dengan id {entry_id!r} tidak ditemukan.")
        reviewed_at = datetime.now().isoformat(timespec="seconds")
        with closing(self._connect()) as db, db:
            db.execute(
                """UPDATE agent_interactions
                   SET reviewed=1, review_label=?, review_note=?, reviewed_by=?, reviewed_at=?
                   WHERE id=?""",
                (label, str(note or "").strip(), str(reviewed_by or "").strip(), reviewed_at, entry_id),
            )
        return self.get(entry_id)

    def review_summary(self, agent: str | None = None) -> dict:
        """Ringkasan tren kualitas — dipakai untuk tinjauan berkala melihat apakah
        proporsi 'tidak_baik'/'perlu_perbaikan' naik dari waktu ke waktu."""
        query = "SELECT reviewed, review_label, COUNT(*) AS n FROM agent_interactions WHERE 1=1"
        params: list = []
        if agent:
            query += " AND agent=?"
            params.append(str(agent).strip())
        query += " GROUP BY reviewed, review_label"
        with closing(self._connect()) as db:
            rows = db.execute(query, params).fetchall()
        summary = {"total": 0, "reviewed": 0, "unreviewed": 0, "baik": 0, "perlu_perbaikan": 0, "tidak_baik": 0}
        for row in rows:
            n = int(row["n"])
            summary["total"] += n
            if row["reviewed"]:
                summary["reviewed"] += n
                label = row["review_label"] or ""
                if label in ALLOWED_REVIEW_LABELS:
                    summary[label] += n
            else:
                summary["unreviewed"] += n
        return summary
