"""Alur pembayaran DEMO. Tidak menerima webhook asli atau mengirim dokumen.

Semua penerimaan uang di modul ini adalah simulasi. Integrasi nyata wajib memakai
adapter terverifikasi dan penyimpanan produksi tersendiri (lihat README_UNTUK_CLAUDE).
"""
from __future__ import annotations

import json
import sqlite3
import uuid
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from .pricing import Quote, whole

DEMO_MARKER = "chatgpt-billing-simulation-v1"
SOURCES = {"simulasi_midtrans", "simulasi_qris", "simulasi_tunai"}
LABELS = {
    "quoted": "Menunggu persetujuan harga",
    "waiting_payment": "Menunggu pembayaran awal",
    "ready": "Siap dikerjakan",
    "working": "Sedang dikerjakan",
    "preview": "Menunggu review pratinjau",
    "waiting_balance": "Menunggu pelunasan",
    "ready_delivery": "Siap menyerahkan file final",
    "delivered": "Selesai",
    "cancelled": "Dibatalkan",
}


def _text(value: str, label: str, maximum: int = 300) -> str:
    if not isinstance(value, str) or not value.strip() or len(value) > maximum:
        raise ValueError(f"{label} wajib berupa teks 1 sampai {maximum} karakter.")
    return value.strip()


@dataclass(frozen=True)
class OrderView:
    order_id: str
    stage: str
    status: str
    total: int
    paid: int
    required_before_work: int
    remaining: int
    revisions_allowed: int
    revisions_used: int
    preview_reference: str
    final_reference: str
    quote: dict

    @property
    def can_start(self) -> bool:
        return self.stage == "accepted" and self.paid >= self.required_before_work

    @property
    def can_deliver(self) -> bool:
        return self.stage == "approved" and self.remaining == 0


@dataclass(frozen=True)
class PaymentUpdate:
    order: OrderView
    credited_amount: int = 0
    ready_for_work: bool = False


class DemoStore:
    """Database demo bertanda khusus; menolak database aplikasi utama.

    Pakai satu instance per koneksi/thread. Semua mutasi memakai transaksi SQLite
    untuk mencegah dua notifikasi menambah pembayaran yang sama dua kali.
    """

    def __init__(self, path: str | Path = ":memory:"):
        location = str(path)
        existing = location != ":memory:" and Path(location).exists()
        if location != ":memory:" and not existing:
            Path(location).parent.mkdir(parents=True, exist_ok=True)
        self.db = sqlite3.connect(location, timeout=10, isolation_level=None)
        self.db.row_factory = sqlite3.Row
        try:
            if existing:
                marker = self.db.execute("SELECT value FROM demo_meta WHERE name='identity'").fetchone()
                if marker is None or marker[0] != DEMO_MARKER:
                    raise ValueError("Database bukan milik prototipe ini.")
            self.db.execute("PRAGMA foreign_keys=ON")
            self.db.executescript("""
                CREATE TABLE IF NOT EXISTS demo_meta (name TEXT PRIMARY KEY, value TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS demo_orders (
                    id TEXT PRIMARY KEY, quote_json TEXT NOT NULL,
                    total INTEGER NOT NULL CHECK(total > 0),
                    initial INTEGER NOT NULL CHECK(initial > 0 AND initial <= total),
                    stage TEXT NOT NULL, revision_limit INTEGER NOT NULL,
                    revision_used INTEGER NOT NULL DEFAULT 0,
                    preview_reference TEXT NOT NULL DEFAULT '',
                    final_reference TEXT NOT NULL DEFAULT ''
                );
                CREATE TABLE IF NOT EXISTS demo_payments (
                    source TEXT NOT NULL, reference TEXT NOT NULL,
                    order_id TEXT NOT NULL REFERENCES demo_orders(id),
                    amount INTEGER NOT NULL CHECK(amount > 0),
                    status TEXT NOT NULL, credited INTEGER NOT NULL DEFAULT 0,
                    PRIMARY KEY(source, reference)
                );
                CREATE TABLE IF NOT EXISTS demo_events (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    order_id TEXT NOT NULL REFERENCES demo_orders(id),
                    created TEXT NOT NULL, action TEXT NOT NULL, detail TEXT NOT NULL
                );
            """)
            self.db.execute("INSERT OR IGNORE INTO demo_meta VALUES ('identity', ?)", (DEMO_MARKER,))
        except (sqlite3.Error, ValueError) as exc:
            self.db.close()
            raise ValueError("Database ditolak. Gunakan database demo baru, bukan assistant.db atau database toko.") from exc

    def close(self) -> None:
        self.db.close()

    @contextmanager
    def _transaction(self):
        self.db.execute("BEGIN IMMEDIATE")
        try:
            yield
            self.db.commit()
        except Exception:
            self.db.rollback()
            raise

    def _event(self, order_id: str, action: str, detail: str) -> None:
        self.db.execute("INSERT INTO demo_events(order_id,created,action,detail) VALUES(?,?,?,?)",
                        (order_id, datetime.now(timezone.utc).isoformat(), action, detail))

    def create_order(self, quote: Quote, *, approved_by: str, manual_review_confirmed: bool = False) -> OrderView:
        quote.validate()
        actor = _text(approved_by, "Operator pembuat penawaran")
        if type(manual_review_confirmed) is not bool:
            raise ValueError("Konfirmasi review harus true atau false.")
        if quote.review_reasons and not manual_review_confirmed:
            raise ValueError("Penawaran ini memerlukan pemeriksaan operator: " + " ".join(quote.review_reasons))
        order_id = "DEMO-" + uuid.uuid4().hex[:16].upper()
        with self._transaction():
            self.db.execute("""INSERT INTO demo_orders(id,quote_json,total,initial,stage,revision_limit)
                               VALUES(?,?,?,?,?,?)""",
                            (order_id, json.dumps(quote.to_dict(), ensure_ascii=False), quote.total,
                             quote.required_before_work, "quoted", quote.revision_rounds))
            self._event(order_id, "create_quote", actor + "; seluruh pembayaran adalah simulasi")
        return self.get(order_id)

    def get(self, order_id: str) -> OrderView:
        row = self.db.execute("SELECT * FROM demo_orders WHERE id=?", (order_id,)).fetchone()
        if row is None:
            raise ValueError("Pesanan demo tidak ditemukan.")
        paid = self.db.execute("SELECT COALESCE(SUM(amount),0) FROM demo_payments WHERE order_id=? AND credited=1",
                               (order_id,)).fetchone()[0]
        stage = row["stage"]
        status = stage
        if stage == "accepted":
            status = "ready" if paid >= row["initial"] else "waiting_payment"
        elif stage == "approved":
            status = "ready_delivery" if paid >= row["total"] else "waiting_balance"
        return OrderView(order_id, stage, status, row["total"], paid, row["initial"], row["total"] - paid,
                         row["revision_limit"], row["revision_used"], row["preview_reference"],
                         row["final_reference"], json.loads(row["quote_json"]))

    def list_orders(self) -> list[OrderView]:
        ids = [row[0] for row in self.db.execute("SELECT id FROM demo_orders ORDER BY rowid DESC")]
        return [self.get(order_id) for order_id in ids]

    def events(self, order_id: str) -> list[dict]:
        self.get(order_id)
        return [dict(row) for row in self.db.execute("SELECT * FROM demo_events WHERE order_id=? ORDER BY id", (order_id,))]

    def _set_stage(self, order_id: str, stage: str, action: str, actor: str) -> None:
        self.db.execute("UPDATE demo_orders SET stage=? WHERE id=?", (stage, order_id))
        self._event(order_id, action, _text(actor, "Pelaku tindakan"))

    def accept_quote(self, order_id: str, *, actor: str) -> OrderView:
        with self._transaction():
            if self.get(order_id).stage != "quoted":
                raise ValueError("Harga hanya dapat disetujui saat penawaran baru.")
            self._set_stage(order_id, "accepted", "accept_quote", actor)
        return self.get(order_id)

    def simulate_payment(self, order_id: str, reference: str, amount: int, *,
                         source: str = "simulasi_midtrans", status: str = "settlement",
                         actor: str = "simulator") -> OrderView:
        return self.simulate_payment_update(order_id, reference, amount, source=source,
                                            status=status, actor=actor).order

    def simulate_payment_update(self, order_id: str, reference: str, amount: int, *,
                                source: str = "simulasi_midtrans", status: str = "settlement",
                                actor: str = "simulator") -> PaymentUpdate:
        """HANYA SIMULASI. Status ini tidak boleh diambil dari chat pelanggan.

        pending/expire/deny tidak menambah uang. Settlement hanya dihitung sekali
        per (source, reference). Notifikasi lama tidak membatalkan uang yang tercatat.
        """
        ref = _text(reference, "Referensi transaksi", 120)
        actor = _text(actor, "Pelaku simulasi pembayaran")
        whole(amount, "Nominal pembayaran", 1)
        if source not in SOURCES or status not in ("pending", "settlement", "expire", "deny"):
            raise ValueError("Sumber atau status simulasi tidak dikenal.")
        with self._transaction():
            order = self.get(order_id)
            prior = self.db.execute("SELECT * FROM demo_payments WHERE source=? AND reference=?", (source, ref)).fetchone()
            if prior is not None:
                if (prior["order_id"], prior["amount"]) != (order_id, amount):
                    raise ValueError("Referensi transaksi sudah dipakai untuk pesanan atau nominal berbeda.")
                if prior["credited"]:
                    return PaymentUpdate(order)
            if order.stage in ("quoted", "cancelled", "delivered"):
                raise ValueError("Tahap pesanan tidak menerima pembayaran baru. Perlu pemeriksaan operator.")
            if amount > order.remaining:
                raise ValueError("Pembayaran melebihi sisa tagihan. Perlu pemeriksaan operator.")
            if prior is None:
                self.db.execute("INSERT INTO demo_payments VALUES(?,?,?,?,?,?)",
                                (source, ref, order_id, amount, status, int(status == "settlement")))
            else:
                # Setelah expire/deny, event pending yang terlambat tidak membuka percobaan lagi.
                if status == "pending" and prior["status"] in ("expire", "deny"):
                    return PaymentUpdate(order)
                if prior["status"] == status:
                    return PaymentUpdate(order)
                self.db.execute("UPDATE demo_payments SET status=?,credited=? WHERE source=? AND reference=?",
                                (status, int(status == "settlement"), source, ref))
            self._event(order_id, "simulated_payment", f"{actor}; {source}; {ref}; {status}; {amount}")
            updated = self.get(order_id)
            became_ready = updated.can_start and not order.can_start
            if became_ready:
                self._event(order_id, "ready_for_work", "Pembayaran awal cukup; belum mengeksekusi Nara.")
            result = PaymentUpdate(updated, amount if status == "settlement" else 0, became_ready)
        return result

    def start_work(self, order_id: str, *, actor: str) -> OrderView:
        with self._transaction():
            if not self.get(order_id).can_start:
                raise ValueError("Belum boleh dikerjakan: harga harus disetujui dan pembayaran awal harus cukup.")
            self._set_stage(order_id, "working", "start_work", actor)
        return self.get(order_id)

    def send_preview(self, order_id: str, reference: str, *, actor: str) -> OrderView:
        reference = _text(reference, "Referensi pratinjau", 1000)
        with self._transaction():
            if self.get(order_id).stage != "working":
                raise ValueError("Pratinjau hanya dapat dicatat setelah pengerjaan dimulai.")
            self.db.execute("UPDATE demo_orders SET preview_reference=? WHERE id=?", (reference, order_id))
            self._set_stage(order_id, "preview", "preview_recorded", actor)
        return self.get(order_id)

    def request_revision(self, order_id: str, note: str, *, actor: str, correction: bool = False) -> OrderView:
        note = _text(note, "Catatan revisi", 1000)
        if type(correction) is not bool:
            raise ValueError("Jenis koreksi harus true atau false.")
        with self._transaction():
            order = self.get(order_id)
            if order.stage != "preview":
                raise ValueError("Revisi hanya dapat diminta pada tahap review pratinjau.")
            if not correction and order.revisions_used >= order.revisions_allowed:
                raise ValueError("Jatah revisi habis. Sepakati penawaran tambahan sebelum lanjut.")
            self.db.execute("UPDATE demo_orders SET revision_used=revision_used+?,preview_reference='' WHERE id=?",
                            (0 if correction else 1, order_id))
            self._set_stage(order_id, "working", "correction" if correction else "revision", actor)
            self._event(order_id, "revision_note", note)
        return self.get(order_id)

    def approve_preview(self, order_id: str, *, actor: str) -> OrderView:
        with self._transaction():
            if self.get(order_id).stage != "preview":
                raise ValueError("Belum ada pratinjau yang menunggu persetujuan.")
            self._set_stage(order_id, "approved", "approve_preview", actor)
        return self.get(order_id)

    def release_final(self, order_id: str, reference: str, *, actor: str) -> OrderView:
        reference = _text(reference, "Referensi file final", 1000)
        with self._transaction():
            if not self.get(order_id).can_deliver:
                raise ValueError("File final ditahan sampai pratinjau disetujui dan tagihan lunas.")
            self.db.execute("UPDATE demo_orders SET final_reference=? WHERE id=?", (reference, order_id))
            self._set_stage(order_id, "delivered", "final_release_recorded", actor)
        return self.get(order_id)

    def cancel_unpaid(self, order_id: str, reason: str, *, actor: str) -> OrderView:
        reason = _text(reason, "Alasan pembatalan", 1000)
        with self._transaction():
            order = self.get(order_id)
            if order.paid or order.stage not in ("quoted", "accepted"):
                raise ValueError("Hanya pesanan belum dibayar dan belum dikerjakan yang dapat dibatalkan di demo.")
            self._set_stage(order_id, "cancelled", "cancel_unpaid", actor)
            self._event(order_id, "cancel_reason", reason)
        return self.get(order_id)
