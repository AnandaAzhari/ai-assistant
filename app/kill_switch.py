"""Kill Switch — mematikan auto-proses channel pelanggan secara darurat.

Menjalankan langkah pertama "Incident Response" di `policies/security_policy.md`
("aktifkan kill switch; hentikan channel/agent terdampak; ...") dan menutup gap
yang sudah ditandai eksplisit di `docs/roadmap_customer_channel_v1.md` Fase 4
("kill switch ... didokumentasikan tapi belum ada implementasi kode").

Kenapa modul terpisah, bukan sekadar flag di `.env`: status kill switch harus bisa
diubah SAAT RUNTIME oleh admin lewat Telegram (tanpa restart proses, tanpa akses
server), dan harus tercatat sebagai audit trail (siapa mematikan, kapan, kenapa) —
sama seperti `app/approval_gate.py`/`app/trust_layer.py`, disimpan di SQLite, bukan
di memori proses saja (supaya kill switch tetap AKTIF walau proses WhatsApp
di-restart setelah admin mematikannya).

Cara pakai: `LeadAgent.handle_customer_message()` memanggil `is_active()` SEBAGAI
PEMERIKSAAN PALING AWAL — sebelum Trust Layer, Approval Gate, AI intent, atau
Document Agent disentuh sama sekali. Begitu aktif, pesan pelanggan di scope itu
langsung dibalas "sedang tidak bisa diproses otomatis" tanpa diproses lebih jauh.

Scope: "global" mematikan SEMUA channel pelanggan sekaligus; scope bernama
(mis. "whatsapp") hanya mematikan channel itu. `is_active(scope)` mengembalikan
True kalau salah satu dari keduanya aktif — jadi admin bisa mematikan satu channel
saja, atau semuanya sekaligus lewat "global".
"""

from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Iterator

GLOBAL_SCOPE = "global"

# Balasan default ke pelanggan saat kill switch aktif — tidak menjelaskan detail
# teknis/insiden ke publik, konsisten dengan nada netral di
# policies/attachment_link_security.md bagian "Response Agent ke Pelanggan".
CUSTOMER_NOTICE_TEXT = (
    "Mohon maaf, layanan otomatis kami sedang tidak dapat memproses pesan untuk "
    "sementara waktu. Tim kami akan segera menghubungi Anda kembali."
)


@dataclass(frozen=True)
class KillSwitchState:
    scope: str
    active: bool
    reason: str
    changed_by: str
    changed_at: str


class KillSwitch:
    """State machine on/off sederhana, per scope, dengan audit log append-only."""

    def __init__(self, db_path: str | Path):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        with self._connect() as db:
            db.execute(
                """CREATE TABLE IF NOT EXISTS kill_switch_state (
                    scope TEXT PRIMARY KEY,
                    active INTEGER NOT NULL,
                    reason TEXT NOT NULL DEFAULT '',
                    changed_by TEXT NOT NULL DEFAULT '',
                    changed_at TEXT NOT NULL DEFAULT ''
                )"""
            )
            # Riwayat lengkap (append-only) terpisah dari state saat ini, supaya
            # histori aktif/nonaktif tidak pernah hilang meski state ditimpa berkali-kali
            # — sama seperti pola audit di app/trust_layer.py (tabel trust_events).
            db.execute(
                """CREATE TABLE IF NOT EXISTS kill_switch_log (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    scope TEXT NOT NULL,
                    active INTEGER NOT NULL,
                    reason TEXT NOT NULL DEFAULT '',
                    changed_by TEXT NOT NULL DEFAULT '',
                    changed_at TEXT NOT NULL
                )"""
            )

    @contextmanager
    def _connect(self) -> Iterator[sqlite3.Connection]:
        """Buka transaksi SQLite dan selalu tutup handle file setelah dipakai.

        sqlite3.Connection sebagai context manager hanya commit/rollback; ia tidak
        menutup koneksi. Pada Windows hal itu membuat file database sementara tetap
        terkunci sehingga TemporaryDirectory gagal dibersihkan (WinError 32) — lihat
        pola yang sama di app/document_preferences.py.
        """
        connection = sqlite3.connect(self.db_path, timeout=10)
        connection.row_factory = sqlite3.Row
        try:
            with connection:
                yield connection
        finally:
            connection.close()

    def _set(self, scope: str, active: bool, reason: str, changed_by: str) -> KillSwitchState:
        scope = (scope or GLOBAL_SCOPE).strip() or GLOBAL_SCOPE
        changed_by = (changed_by or "").strip()
        if not changed_by:
            raise ValueError("changed_by wajib diisi agar audit trail jelas siapa yang mengubah kill switch.")
        reason = (reason or "").strip()
        now = datetime.now().isoformat(timespec="seconds")
        with self._connect() as db:
            db.execute(
                """INSERT INTO kill_switch_state (scope, active, reason, changed_by, changed_at)
                   VALUES (?,?,?,?,?)
                   ON CONFLICT(scope) DO UPDATE SET
                       active=excluded.active, reason=excluded.reason,
                       changed_by=excluded.changed_by, changed_at=excluded.changed_at""",
                (scope, int(active), reason, changed_by, now),
            )
            db.execute(
                """INSERT INTO kill_switch_log (scope, active, reason, changed_by, changed_at)
                   VALUES (?,?,?,?,?)""",
                (scope, int(active), reason, changed_by, now),
            )
        return KillSwitchState(scope, active, reason, changed_by, now)

    def activate(self, *, scope: str = GLOBAL_SCOPE, reason: str = "", changed_by: str) -> KillSwitchState:
        return self._set(scope, True, reason, changed_by)

    def deactivate(self, *, scope: str = GLOBAL_SCOPE, reason: str = "", changed_by: str) -> KillSwitchState:
        return self._set(scope, False, reason, changed_by)

    def is_active(self, scope: str = GLOBAL_SCOPE) -> bool:
        """True bila scope "global" ATAU scope spesifik ini sedang aktif (dimatikan)."""
        scope = (scope or GLOBAL_SCOPE).strip() or GLOBAL_SCOPE
        with self._connect() as db:
            rows = db.execute(
                "SELECT active FROM kill_switch_state WHERE scope IN (?, ?)",
                (GLOBAL_SCOPE, scope),
            ).fetchall()
        return any(bool(row["active"]) for row in rows)

    def status(self, scope: str = GLOBAL_SCOPE) -> KillSwitchState:
        """Status terkini scope tsb. Belum pernah diubah -> dianggap nonaktif (default aman)."""
        scope = (scope or GLOBAL_SCOPE).strip() or GLOBAL_SCOPE
        with self._connect() as db:
            row = db.execute(
                "SELECT scope, active, reason, changed_by, changed_at FROM kill_switch_state WHERE scope = ?",
                (scope,),
            ).fetchone()
        if row is None:
            return KillSwitchState(scope, False, "", "", "")
        return KillSwitchState(row["scope"], bool(row["active"]), row["reason"], row["changed_by"], row["changed_at"])

    def history(self, *, scope: str | None = None, limit: int = 20) -> list[dict]:
        with self._connect() as db:
            if scope:
                rows = db.execute(
                    "SELECT * FROM kill_switch_log WHERE scope = ? ORDER BY id DESC LIMIT ?",
                    (scope, limit),
                ).fetchall()
            else:
                rows = db.execute(
                    "SELECT * FROM kill_switch_log ORDER BY id DESC LIMIT ?", (limit,),
                ).fetchall()
        return [dict(row) for row in rows]
