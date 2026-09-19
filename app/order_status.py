"""Order Status — status pesanan asli yang dikelola admin, dipakai untuk menjawab
pelanggan tanpa AI pernah mengarang status.

Sama seperti `app/price_list.py`, menutup gap "hallucination prevention" untuk
`action_type == "kirim_status_antrean"` — sebelumnya selalu dibalas teks generik
"belum bisa dipastikan otomatis". TaqiDesk (sistem order otomatis) belum terhubung
(lihat `handle_admin_message` — kata kunci "taqidesk" masih "integrasi belum
diaktifkan"), jadi modul ini adalah pencatatan MANUAL oleh admin dulu — bukan
otomatis dari sistem order — sampai TaqiDesk benar-benar tersambung nanti.

BEDA PENTING dari `app/price_list.py`: status order adalah data PER PELANGGAN, jadi
wajib mengikuti "Isolasi Antar Pelanggan" di `policies/security_policy.md` — setiap
query dari jalur pelanggan HARUS difilter `sender_id` miliknya sendiri, tidak pernah
query bebas/lintas pelanggan. `get_latest_for_customer`/`list_for_customer` menegakkan
ini di level kode (bukan cuma instruksi ke AI): keduanya SELALU mewajibkan `sender_id`
dan memfilter WHERE sender_id = ?, tidak ada method yang mengembalikan data lintas
pelanggan dari jalur ini.
"""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path


@dataclass(frozen=True)
class OrderStatusEntry:
    order_id: str
    sender_id: str
    status_text: str
    updated_by: str
    updated_at: str


class OrderStatusStore:
    def __init__(self, db_path: str | Path):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        with self._connect() as db:
            db.execute(
                """CREATE TABLE IF NOT EXISTS order_status (
                    order_id TEXT PRIMARY KEY,
                    sender_id TEXT NOT NULL,
                    status_text TEXT NOT NULL,
                    updated_by TEXT NOT NULL DEFAULT '',
                    updated_at TEXT NOT NULL DEFAULT ''
                )"""
            )
            db.execute("CREATE INDEX IF NOT EXISTS idx_order_status_sender ON order_status(sender_id, updated_at)")

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.db_path, timeout=10)
        connection.row_factory = sqlite3.Row
        return connection

    def set_status(self, order_id: str, sender_id: str, status_text: str, *, updated_by: str) -> OrderStatusEntry:
        order_id = (order_id or "").strip()
        if not order_id:
            raise ValueError("order_id wajib diisi.")
        sender_id = (sender_id or "").strip()
        if not sender_id:
            raise ValueError("sender_id (nomor pelanggan pemilik order) wajib diisi.")
        status_text = (status_text or "").strip()
        if not status_text:
            raise ValueError("status_text wajib diisi.")
        updated_by = (updated_by or "").strip()
        if not updated_by:
            raise ValueError("updated_by wajib diisi agar audit trail jelas.")
        now = datetime.now().isoformat(timespec="seconds")
        with self._connect() as db:
            db.execute(
                """INSERT INTO order_status (order_id, sender_id, status_text, updated_by, updated_at)
                   VALUES (?,?,?,?,?)
                   ON CONFLICT(order_id) DO UPDATE SET
                       sender_id=excluded.sender_id, status_text=excluded.status_text,
                       updated_by=excluded.updated_by, updated_at=excluded.updated_at""",
                (order_id, sender_id, status_text, updated_by, now),
            )
        return OrderStatusEntry(order_id, sender_id, status_text, updated_by, now)

    def list_for_customer(self, sender_id: str, *, limit: int = 5) -> list[OrderStatusEntry]:
        """SELALU difilter `sender_id` — lihat docstring modul, "Isolasi Antar Pelanggan"."""
        sender_id = (sender_id or "").strip()
        if not sender_id:
            return []
        with self._connect() as db:
            rows = db.execute(
                "SELECT * FROM order_status WHERE sender_id = ? ORDER BY updated_at DESC LIMIT ?",
                (sender_id, limit),
            ).fetchall()
        return [OrderStatusEntry(*row) for row in rows]

    def get_latest_for_customer(self, sender_id: str) -> OrderStatusEntry | None:
        entries = self.list_for_customer(sender_id, limit=1)
        return entries[0] if entries else None

    def remove(self, order_id: str) -> bool:
        with self._connect() as db:
            cursor = db.execute("DELETE FROM order_status WHERE order_id = ?", ((order_id or "").strip(),))
            return cursor.rowcount > 0
