"""Payment Gate — menahan file makalah bersih (DOCX + PDF tanpa watermark) sampai
admin menandai order itu lunas, lalu mengirimkannya otomatis ke pelanggan.

Bagian dari alur proteksi pembayaran (lihat `app/pdf_watermark.py` untuk pratinjau
ber-watermark yang dikirim duluan, dan `app/lead.py` untuk titik pemakaiannya):

1. Makalah selesai dibuat -> pelanggan HANYA menerima PDF pratinjau ber-watermark
   (`app/pdf_watermark.py`). DOCX + PDF bersihnya disimpan di sini lewat
   `save_pending()`, BELUM dikirim.
2. Admin ketik `/lunas <nomor_wa_pelanggan>` di Telegram -> `mark_paid()` menandai
   pending release milik nomor itu sebagai lunas.
3. WhatsApp dan Telegram berjalan sebagai DUA PROSES TERPISAH yang cuma berbagi
   database ini (lihat `app/admin_runtime.py`) — tidak ada cara satu proses
   langsung "menyuruh" proses lain kirim pesan saat itu juga. Selain itu, WhatsApp
   Business API cuma mengizinkan balasan bebas (non-template) dalam jendela 24 jam
   sejak pesan TERAKHIR dari pelanggan (lihat `app/whatsapp.py`) — jadi mengirim di
   luar jendela itu tanpa template akan ditolak Meta. Karena dua alasan itu, rilis
   file BUKAN push instan saat `/lunas` diketik, melainkan dikirim otomatis begitu
   pelanggan itu mengirim PESAN APA PUN berikutnya ke bot WhatsApp — `LeadAgent`
   mengecek `pop_ready_release()` di awal `handle_customer_message()` sebelum
   memproses isi pesan itu sendiri. Dalam praktik pelanggan hampir selalu langsung
   bilang sesuatu ("sudah saya bayar") begitu transfer, jadi terasa nyaris instan.

`payment_info` (teks QR GoPay/DANA/no rekening) sengaja disimpan di sini, diisi
admin sendiri lewat command (`/set_pembayaran <teks>`) — BUKAN ditulis langsung oleh
siapa pun ke kode ini, supaya nomor rekening/DANA asli Taqi tidak pernah perlu
ditempel ke mana pun di luar Telegram admin miliknya sendiri.
"""

from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Iterator

_PAYMENT_INFO_KEY = "default"


@dataclass(frozen=True)
class PendingRelease:
    sender_id: str
    docx_path: str
    pdf_path: str
    created_at: str
    paid_at: str  # kosong = belum lunas
    delivered_at: str  # kosong = belum pernah dikirim ke pelanggan


class PaymentGateStore:
    def __init__(self, db_path: str | Path):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        with self._connect() as db:
            db.execute(
                """CREATE TABLE IF NOT EXISTS pending_document_release (
                    sender_id TEXT PRIMARY KEY,
                    docx_path TEXT NOT NULL,
                    pdf_path TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    paid_at TEXT NOT NULL DEFAULT '',
                    delivered_at TEXT NOT NULL DEFAULT ''
                )"""
            )
            db.execute(
                """CREATE TABLE IF NOT EXISTS payment_info (
                    key TEXT PRIMARY KEY,
                    info_text TEXT NOT NULL,
                    updated_by TEXT NOT NULL DEFAULT '',
                    updated_at TEXT NOT NULL DEFAULT ''
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

    # -- Pending release (DOCX + PDF bersih yang ditahan sampai lunas) ----------

    def save_pending(self, sender_id: str, docx_path: str, pdf_path: str) -> None:
        sender_id = (sender_id or "").strip()
        if not sender_id:
            raise ValueError("sender_id wajib diisi.")
        if not docx_path or not pdf_path:
            raise ValueError("docx_path dan pdf_path wajib diisi.")
        now = datetime.now().isoformat(timespec="seconds")
        with self._connect() as db:
            db.execute(
                """INSERT INTO pending_document_release
                       (sender_id, docx_path, pdf_path, created_at, paid_at, delivered_at)
                   VALUES (?,?,?,?,'','')
                   ON CONFLICT(sender_id) DO UPDATE SET
                       docx_path=excluded.docx_path, pdf_path=excluded.pdf_path,
                       created_at=excluded.created_at, paid_at='', delivered_at=''""",
                (sender_id, docx_path, pdf_path, now),
            )

    def _get(self, sender_id: str) -> PendingRelease | None:
        with self._connect() as db:
            row = db.execute(
                "SELECT * FROM pending_document_release WHERE sender_id = ?", ((sender_id or "").strip(),),
            ).fetchone()
        return PendingRelease(*row) if row else None

    def get_pending(self, sender_id: str) -> PendingRelease | None:
        return self._get(sender_id)

    def mark_paid(self, sender_id: str, *, updated_by: str) -> PendingRelease | None:
        """Dipanggil dari command admin `/lunas <nomor_wa>`. Mengembalikan entri yang
        ditandai lunas (None kalau memang tidak ada order tertahan untuk nomor itu)
        supaya pemanggil bisa langsung kasih konfirmasi yang jelas ke admin."""
        sender_id = (sender_id or "").strip()
        entry = self._get(sender_id)
        if entry is None:
            return None
        now = datetime.now().isoformat(timespec="seconds")
        with self._connect() as db:
            db.execute(
                "UPDATE pending_document_release SET paid_at = ? WHERE sender_id = ?",
                (now, sender_id),
            )
        return self._get(sender_id)

    def pop_ready_release(self, sender_id: str) -> PendingRelease | None:
        """Dipanggil `LeadAgent.handle_customer_message()` di awal setiap pesan
        pelanggan masuk (lihat docstring modul, poin 3). Kalau order untuk nomor ini
        sudah lunas TAPI belum pernah dikirim, tandai terkirim dan kembalikan
        entrinya supaya pemanggil bisa lampirkan `docx_path`/`pdf_path` ke balasan.
        Sekali diambil, tidak akan dikirim ulang lagi untuk pesan berikutnya."""
        entry = self._get(sender_id)
        if entry is None or not entry.paid_at or entry.delivered_at:
            return None
        now = datetime.now().isoformat(timespec="seconds")
        with self._connect() as db:
            db.execute(
                "UPDATE pending_document_release SET delivered_at = ? WHERE sender_id = ?",
                (now, entry.sender_id),
            )
        return self._get(entry.sender_id)

    def clear(self, sender_id: str) -> bool:
        with self._connect() as db:
            cursor = db.execute(
                "DELETE FROM pending_document_release WHERE sender_id = ?", ((sender_id or "").strip(),),
            )
            return cursor.rowcount > 0

    # -- Info pembayaran (QR GoPay/DANA/no rekening, diisi admin sendiri) -------

    def set_payment_info(self, info_text: str, *, updated_by: str) -> str:
        info_text = (info_text or "").strip()
        if not info_text:
            raise ValueError("Info pembayaran wajib diisi.")
        updated_by = (updated_by or "").strip()
        if not updated_by:
            raise ValueError("updated_by wajib diisi agar audit trail jelas.")
        now = datetime.now().isoformat(timespec="seconds")
        with self._connect() as db:
            db.execute(
                """INSERT INTO payment_info (key, info_text, updated_by, updated_at)
                   VALUES (?,?,?,?)
                   ON CONFLICT(key) DO UPDATE SET
                       info_text=excluded.info_text, updated_by=excluded.updated_by,
                       updated_at=excluded.updated_at""",
                (_PAYMENT_INFO_KEY, info_text, updated_by, now),
            )
        return info_text

    def get_payment_info(self) -> str:
        with self._connect() as db:
            row = db.execute(
                "SELECT info_text FROM payment_info WHERE key = ?", (_PAYMENT_INFO_KEY,),
            ).fetchone()
        return row["info_text"] if row else ""
