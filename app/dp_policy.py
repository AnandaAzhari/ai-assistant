"""DP Policy — status wajib/opsional untuk uang muka (DP), bisa diubah admin
SAAT RUNTIME lewat Telegram (tanpa restart proses, tanpa akses server), sama
persis pola `app/kill_switch.py` (state on/off + audit log append-only di
SQLite).

Kenapa terpisah dari `app/pricing.py`: `make_quote()` di situ SELALU menghitung
angka DP sebagai referensi (`Quote.dp_amount`/`Quote.sisa`), tapi apakah DP itu
BENAR-BENAR wajib dibayar sebelum pekerjaan mulai adalah keputusan operasional
yang bisa berubah-ubah (mis. dinaikkan jadi wajib kalau makin banyak pelanggan
kabur setelah pesan, diturunkan lagi kalau ternyata tidak perlu) — bukan bagian
dari kalkulator harga itu sendiri. Pemisahan ini juga membuat modul harga tetap
testable murni tanpa pernah menyentuh database kebijakan.

Default aman: OPSIONAL (belum pernah diaktifkan admin = DP ditawarkan tapi
tidak memblokir apa pun) — konsisten dengan default aman `KillSwitch` (belum
pernah diaktifkan = nonaktif).

CATATAN INTEGRASI (sengaja belum dikerjakan di sini): pada tahap ini,
`DpPolicyStore` baru dipakai untuk MENAMPILKAN status (mis. di balasan
`/hitung_harga`, dan lewat `/dp_status`) dan diubah admin lewat
`/dp_wajib`/`/dp_opsional` di `app/lead.py` — belum dihubungkan sebagai
GERBANG yang benar-benar menahan Document Agent mulai bekerja sebelum DP
masuk. Menyambungkan gerbang itu ke alur intake dokumen (`app/document_agent.py`)
adalah langkah lanjutan tersendiri yang butuh desain terpisah (di mana tepatnya
titik tahannya), supaya tidak diam-diam mengubah alur intake yang sudah
berjalan tanpa persetujuan eksplisit lebih dulu.
"""

from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Iterator


@dataclass(frozen=True)
class DpPolicyState:
    mandatory: bool
    reason: str
    changed_by: str
    changed_at: str


class DpPolicyStore:
    """State machine on/off sederhana (mirip `KillSwitch`, tapi satu status
    global saja — tidak ada scope per-channel karena DP adalah kebijakan
    bisnis, bukan kendali teknis per channel)."""

    _KEY = "dp_mandatory"

    def __init__(self, db_path: str | Path):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        with self._connect() as db:
            db.execute(
                """CREATE TABLE IF NOT EXISTS dp_policy_state (
                    key TEXT PRIMARY KEY,
                    mandatory INTEGER NOT NULL,
                    reason TEXT NOT NULL DEFAULT '',
                    changed_by TEXT NOT NULL DEFAULT '',
                    changed_at TEXT NOT NULL DEFAULT ''
                )"""
            )
            db.execute(
                """CREATE TABLE IF NOT EXISTS dp_policy_log (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    mandatory INTEGER NOT NULL,
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

    def _set(self, mandatory: bool, reason: str, changed_by: str) -> DpPolicyState:
        changed_by = (changed_by or "").strip()
        if not changed_by:
            raise ValueError("changed_by wajib diisi agar audit trail jelas siapa yang mengubah kebijakan DP.")
        reason = (reason or "").strip()
        now = datetime.now().isoformat(timespec="seconds")
        with self._connect() as db:
            db.execute(
                """INSERT INTO dp_policy_state (key, mandatory, reason, changed_by, changed_at)
                   VALUES (?,?,?,?,?)
                   ON CONFLICT(key) DO UPDATE SET
                       mandatory=excluded.mandatory, reason=excluded.reason,
                       changed_by=excluded.changed_by, changed_at=excluded.changed_at""",
                (self._KEY, int(mandatory), reason, changed_by, now),
            )
            db.execute(
                "INSERT INTO dp_policy_log (mandatory, reason, changed_by, changed_at) VALUES (?,?,?,?)",
                (int(mandatory), reason, changed_by, now),
            )
        return DpPolicyState(mandatory, reason, changed_by, now)

    def set_mandatory(self, *, reason: str = "", changed_by: str) -> DpPolicyState:
        return self._set(True, reason, changed_by)

    def set_optional(self, *, reason: str = "", changed_by: str) -> DpPolicyState:
        return self._set(False, reason, changed_by)

    def is_mandatory(self) -> bool:
        return self.status().mandatory

    def status(self) -> DpPolicyState:
        """Status terkini. Belum pernah diubah -> dianggap opsional (default aman)."""
        with self._connect() as db:
            row = db.execute(
                "SELECT mandatory, reason, changed_by, changed_at FROM dp_policy_state WHERE key = ?",
                (self._KEY,),
            ).fetchone()
        if row is None:
            return DpPolicyState(False, "", "", "")
        return DpPolicyState(bool(row["mandatory"]), row["reason"], row["changed_by"], row["changed_at"])

    def history(self, limit: int = 20) -> list[dict]:
        with self._connect() as db:
            rows = db.execute(
                "SELECT * FROM dp_policy_log ORDER BY id DESC LIMIT ?", (limit,),
            ).fetchall()
        return [dict(row) for row in rows]
