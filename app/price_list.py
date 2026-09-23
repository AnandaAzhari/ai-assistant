"""Price List — data harga asli yang dikelola admin, dipakai untuk menjawab pelanggan
tanpa AI pernah mengarang angka.

Menutup gap "hallucination prevention" yang sudah ditandai eksplisit di
`docs/roadmap_customer_channel_v1.md` ("Guardrail Tambahan"): "Setiap agent yang
memberi jawaban ke pelanggan (harga, ketersediaan, status order, estimasi waktu)
wajib mengambil datanya dari sumber yang benar (database/price list), bukan dikarang
oleh model AI. Kalau data tidak tersedia, agent menjawab 'belum bisa dipastikan'
daripada menebak."

Sebelum modul ini ada, `action_type == "kirim_estimasi_harga_standar"` SELALU dibalas
teks generik "belum bisa dipastikan otomatis, diteruskan ke admin" — walau admin
sudah punya harga tetap untuk sebagian besar layanan. Modul ini menyimpan price list
terstruktur di SQLite (bukan teks bebas yang bisa "dilengkapi" AI), dikelola admin
lewat command Telegram/Web Admin (`/harga_set`, `/harga_hapus`, `/harga_list` di
`app/lead.py`), dan DICARI (bukan dikarang) oleh `LeadAgent.handle_customer_message()`
saat pelanggan tanya harga. Kalau layanan yang ditanyakan tidak ditemukan di price
list, `LeadAgent` tetap jatuh ke balasan lama ("diteruskan ke admin") — tidak pernah
menebak angka.

Price list adalah data BISNIS milik semua pelanggan (mirip FAQ), bukan data per
pelanggan — jadi tidak butuh isolasi `scope_id`/`sender_id` seperti Document Agent
atau Order Status (lihat `app/order_status.py` untuk yang butuh isolasi itu).
"""

from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Iterator


def _normalize(text: str) -> str:
    return " ".join((text or "").casefold().split())


@dataclass(frozen=True)
class PriceEntry:
    key: str
    display_name: str
    price_text: str
    note: str
    updated_by: str
    updated_at: str


class PriceListStore:
    def __init__(self, db_path: str | Path):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        with self._connect() as db:
            db.execute(
                """CREATE TABLE IF NOT EXISTS price_list (
                    key TEXT PRIMARY KEY,
                    display_name TEXT NOT NULL,
                    price_text TEXT NOT NULL,
                    note TEXT NOT NULL DEFAULT '',
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

    def set_price(self, service: str, price_text: str, *, note: str = "", updated_by: str) -> PriceEntry:
        display_name = (service or "").strip()
        if not display_name:
            raise ValueError("Nama layanan wajib diisi.")
        price_text = (price_text or "").strip()
        if not price_text:
            raise ValueError("Harga/info harga wajib diisi.")
        updated_by = (updated_by or "").strip()
        if not updated_by:
            raise ValueError("updated_by wajib diisi agar audit trail jelas.")
        key = _normalize(display_name)
        now = datetime.now().isoformat(timespec="seconds")
        with self._connect() as db:
            db.execute(
                """INSERT INTO price_list (key, display_name, price_text, note, updated_by, updated_at)
                   VALUES (?,?,?,?,?,?)
                   ON CONFLICT(key) DO UPDATE SET
                       display_name=excluded.display_name, price_text=excluded.price_text,
                       note=excluded.note, updated_by=excluded.updated_by, updated_at=excluded.updated_at""",
                (key, display_name, price_text, (note or "").strip(), updated_by, now),
            )
        return PriceEntry(key, display_name, price_text, (note or "").strip(), updated_by, now)

    def remove(self, service: str) -> bool:
        key = _normalize(service)
        with self._connect() as db:
            cursor = db.execute("DELETE FROM price_list WHERE key = ?", (key,))
            return cursor.rowcount > 0

    def list_all(self) -> list[PriceEntry]:
        with self._connect() as db:
            rows = db.execute("SELECT * FROM price_list ORDER BY display_name").fetchall()
        return [PriceEntry(*row) for row in rows]

    def find(self, query: str) -> PriceEntry | None:
        """Cocokkan pesan bebas pelanggan terhadap nama layanan tersimpan.

        Pencocokan substring case-insensitive DUA ARAH (nama layanan ada di dalam
        pesan pelanggan, atau sebaliknya), supaya "harga cetak skripsi 50 lembar
        berapa ya" tetap ketemu entri "Cetak Skripsi". Kalau ada beberapa entri yang
        cocok, pilih nama layanan TERPANJANG (paling spesifik) supaya "Cetak Skripsi
        Warna" tidak keliru menjawab pakai harga "Cetak Skripsi" biasa.
        """
        normalized_query = _normalize(query)
        if not normalized_query:
            return None
        candidates = [
            entry for entry in self.list_all()
            if entry.key in normalized_query or normalized_query in entry.key
        ]
        if not candidates:
            return None
        return max(candidates, key=lambda entry: len(entry.key))
