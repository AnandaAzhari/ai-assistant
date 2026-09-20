"""Customer Book — profil pelanggan ringkas dan riwayat order per bisnis, supaya AI
Assistant "ingat" siapa yang pernah menghubungi dan admin bisa lihat rekap (jumlah
order, omzet per bisnis) tanpa mengumpulkan histori manual dari chat WhatsApp/Telegram.

BEDA dari `app/order_status.py`: `order_status` adalah status ANTREAN bebas teks yang
dijawabkan ke pelanggan ("Sedang dicetak, estimasi besok"). Tabel `customer_orders` di
sini adalah CATATAN TERSTRUKTUR per order (bisnis, item, harga) untuk rekap/laporan
admin (mis. `/pelanggan_ringkasan`) — dua modul ini saling melengkapi, bukan saling
menggantikan; admin bebas memakai salah satu atau keduanya untuk order yang sama.

Sama seperti `app/order_status.py`, data pelanggan (`customers`, `customer_orders`)
adalah data PER PELANGGAN: wajib mengikuti "Isolasi Antar Pelanggan" di
`policies/security_policy.md`. `get_customer`/`list_orders_for_customer` SELALU
mewajibkan `sender_id` dan memfilter WHERE sender_id = ?, ditegakkan di level kode
(bukan cuma instruksi ke AI) — tidak ada method yang mengembalikan data satu pelanggan
tertentu tanpa `sender_id`-nya sendiri. Method ringkasan lintas pelanggan
(`summary_by_business`, `list_customers`) HANYA untuk dipanggil dari jalur admin
(`handle_admin_message`), tidak pernah dari `handle_customer_message`.

`touch()` (dipanggil otomatis setiap pesan pelanggan masuk, lihat
`LeadAgent.handle_customer_message`) TIDAK PERNAH menimpa nama/bisnis yang sudah
tersimpan — hanya menambah `total_contacts` dan memperbarui `last_seen_at`. Nama dan
bisnis pelanggan hanya diisi lewat `set_profile`/`record_order` (jalur admin), supaya
data pelanggan tidak pernah berisi tebakan AI.
"""

from __future__ import annotations

import sqlite3
import uuid
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path


@dataclass(frozen=True)
class CustomerEntry:
    sender_id: str
    display_name: str
    business: str
    first_seen_at: str
    last_seen_at: str
    total_contacts: int
    notes: str


@dataclass(frozen=True)
class CustomerOrderEntry:
    id: str
    sender_id: str
    business: str
    item_description: str
    amount: int | None
    status: str
    created_at: str
    updated_at: str
    created_by: str


class CustomerBookStore:
    def __init__(self, db_path: str | Path):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        with self._connect() as db:
            db.execute(
                """CREATE TABLE IF NOT EXISTS customers (
                    sender_id TEXT PRIMARY KEY,
                    display_name TEXT NOT NULL DEFAULT '',
                    business TEXT NOT NULL DEFAULT '',
                    first_seen_at TEXT NOT NULL,
                    last_seen_at TEXT NOT NULL,
                    total_contacts INTEGER NOT NULL DEFAULT 0,
                    notes TEXT NOT NULL DEFAULT ''
                )"""
            )
            db.execute(
                """CREATE TABLE IF NOT EXISTS customer_orders (
                    id TEXT PRIMARY KEY,
                    sender_id TEXT NOT NULL,
                    business TEXT NOT NULL,
                    item_description TEXT NOT NULL,
                    amount INTEGER,
                    status TEXT NOT NULL DEFAULT 'baru',
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    created_by TEXT NOT NULL DEFAULT ''
                )"""
            )
            db.execute(
                "CREATE INDEX IF NOT EXISTS idx_customer_orders_sender ON customer_orders(sender_id, created_at)"
            )
            db.execute(
                "CREATE INDEX IF NOT EXISTS idx_customer_orders_business ON customer_orders(business, created_at)"
            )

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.db_path, timeout=10)
        connection.row_factory = sqlite3.Row
        return connection

    # -- Profil pelanggan ---------------------------------------------------

    def touch(self, sender_id: str, *, channel: str = "") -> CustomerEntry | None:
        """Catat kontak pasif — lihat docstring modul. `channel` disimpan hanya untuk
        kompatibilitas pemanggilan (mis. dari `handle_customer_message`), belum
        dipakai untuk logika apa pun di sini."""
        sender_id = (sender_id or "").strip()
        if not sender_id:
            return None
        now = datetime.now().isoformat(timespec="seconds")
        with self._connect() as db:
            db.execute(
                """INSERT INTO customers (sender_id, first_seen_at, last_seen_at, total_contacts)
                   VALUES (?, ?, ?, 1)
                   ON CONFLICT(sender_id) DO UPDATE SET
                       last_seen_at = excluded.last_seen_at,
                       total_contacts = total_contacts + 1""",
                (sender_id, now, now),
            )
            row = db.execute("SELECT * FROM customers WHERE sender_id = ?", (sender_id,)).fetchone()
        return CustomerEntry(**dict(row)) if row else None

    def set_profile(
        self, sender_id: str, *, display_name: str = "", business: str = "", notes: str = "",
    ) -> CustomerEntry:
        """Isi/ubah nama, bisnis utama, dan catatan pelanggan — dipanggil admin (mis.
        `/pelanggan_nama`), tidak pernah otomatis dari AI. Field kosong tidak menimpa
        nilai yang sudah tersimpan (supaya admin bisa mengisi satu field saja)."""
        sender_id = (sender_id or "").strip()
        if not sender_id:
            raise ValueError("sender_id wajib diisi.")
        now = datetime.now().isoformat(timespec="seconds")
        with self._connect() as db:
            existing = db.execute("SELECT * FROM customers WHERE sender_id = ?", (sender_id,)).fetchone()
            if existing is None:
                db.execute(
                    """INSERT INTO customers
                       (sender_id, display_name, business, first_seen_at, last_seen_at, total_contacts, notes)
                       VALUES (?, ?, ?, ?, ?, 0, ?)""",
                    (sender_id, display_name.strip(), business.strip(), now, now, notes.strip()),
                )
            else:
                merged_name = display_name.strip() or existing["display_name"]
                merged_business = business.strip() or existing["business"]
                merged_notes = notes.strip() or existing["notes"]
                db.execute(
                    "UPDATE customers SET display_name = ?, business = ?, notes = ? WHERE sender_id = ?",
                    (merged_name, merged_business, merged_notes, sender_id),
                )
            row = db.execute("SELECT * FROM customers WHERE sender_id = ?", (sender_id,)).fetchone()
        return CustomerEntry(**dict(row))

    def get_customer(self, sender_id: str) -> CustomerEntry | None:
        """SELALU difilter `sender_id` milik sendiri — lihat docstring modul,
        "Isolasi Antar Pelanggan"."""
        sender_id = (sender_id or "").strip()
        if not sender_id:
            return None
        with self._connect() as db:
            row = db.execute("SELECT * FROM customers WHERE sender_id = ?", (sender_id,)).fetchone()
        return CustomerEntry(**dict(row)) if row else None

    def list_customers(self, *, business: str = "", limit: int = 50) -> list[CustomerEntry]:
        """Listing lintas pelanggan — HANYA untuk jalur admin, tidak pernah dipanggil
        dari `handle_customer_message`."""
        with self._connect() as db:
            if business:
                rows = db.execute(
                    "SELECT * FROM customers WHERE business = ? ORDER BY last_seen_at DESC LIMIT ?",
                    (business.strip(), limit),
                ).fetchall()
            else:
                rows = db.execute(
                    "SELECT * FROM customers ORDER BY last_seen_at DESC LIMIT ?", (limit,),
                ).fetchall()
        return [CustomerEntry(**dict(row)) for row in rows]

    # -- Order pelanggan -----------------------------------------------------

    def record_order(
        self, sender_id: str, business: str, item_description: str, *,
        amount: int | None = None, status: str = "baru", created_by: str,
    ) -> CustomerOrderEntry:
        sender_id = (sender_id or "").strip()
        business = (business or "").strip()
        item_description = (item_description or "").strip()
        status = (status or "baru").strip() or "baru"
        created_by = (created_by or "").strip()
        if not sender_id:
            raise ValueError("sender_id (nomor pelanggan) wajib diisi.")
        if not business:
            raise ValueError("business (nama usaha) wajib diisi.")
        if not item_description:
            raise ValueError("item_description wajib diisi.")
        if not created_by:
            raise ValueError("created_by wajib diisi agar audit trail jelas.")
        if amount is not None and amount < 0:
            raise ValueError("amount tidak boleh negatif.")
        order_id = f"CO-{uuid.uuid4().hex[:10]}"
        now = datetime.now().isoformat(timespec="seconds")
        with self._connect() as db:
            db.execute(
                """INSERT INTO customer_orders
                   (id, sender_id, business, item_description, amount, status, created_at, updated_at, created_by)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (order_id, sender_id, business, item_description, amount, status, now, now, created_by),
            )
            # Order baru dari pelanggan yang belum pernah tercatat di `customers`
            # (mis. admin mencatat order duluan sebelum pelanggan pernah chat sama
            # sekali): pastikan tetap muncul di `customers`, tanpa menimpa
            # first_seen_at/last_seen_at/business kalau baris itu sudah ada.
            db.execute(
                """INSERT INTO customers (sender_id, business, first_seen_at, last_seen_at, total_contacts)
                   VALUES (?, ?, ?, ?, 0)
                   ON CONFLICT(sender_id) DO UPDATE SET
                       business = CASE WHEN customers.business = '' THEN excluded.business ELSE customers.business END""",
                (sender_id, business, now, now),
            )
        return CustomerOrderEntry(order_id, sender_id, business, item_description, amount, status, now, now, created_by)

    def update_order_status(self, order_id: str, status: str, *, updated_by: str) -> bool:
        order_id = (order_id or "").strip()
        status = (status or "").strip()
        if not order_id or not status:
            return False
        now = datetime.now().isoformat(timespec="seconds")
        with self._connect() as db:
            cursor = db.execute(
                "UPDATE customer_orders SET status = ?, updated_at = ? WHERE id = ?",
                (status, now, order_id),
            )
            return cursor.rowcount > 0

    def list_orders_for_customer(self, sender_id: str, *, limit: int = 20) -> list[CustomerOrderEntry]:
        """SELALU difilter `sender_id` — lihat "Isolasi Antar Pelanggan" di
        `policies/security_policy.md`, sama seperti `OrderStatusStore.list_for_customer`."""
        sender_id = (sender_id or "").strip()
        if not sender_id:
            return []
        with self._connect() as db:
            rows = db.execute(
                "SELECT * FROM customer_orders WHERE sender_id = ? ORDER BY created_at DESC LIMIT ?",
                (sender_id, limit),
            ).fetchall()
        return [CustomerOrderEntry(**dict(row)) for row in rows]

    # -- Ringkasan admin -------------------------------------------------

    def summary_by_business(self, business: str) -> dict:
        """Total order dan total omzet (jumlah `amount` yang terisi) untuk satu
        bisnis, dipakai admin lewat `/pelanggan_ringkasan` — rekap LINTAS pelanggan,
        tidak pernah dipanggil dari jalur pelanggan."""
        business = (business or "").strip()
        with self._connect() as db:
            row = db.execute(
                """SELECT COUNT(*) AS total_order, COALESCE(SUM(amount), 0) AS total_omzet
                   FROM customer_orders WHERE business = ?""",
                (business,),
            ).fetchone()
        return {"business": business, "total_order": row["total_order"], "total_omzet": row["total_omzet"]}
