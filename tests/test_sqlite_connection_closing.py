"""Regresi untuk bug koneksi SQLite tidak tertutup di Windows.

sqlite3.Connection dipakai sebagai context manager (`with self._connect() as db:`)
di seluruh app/*.py HANYA mengelola commit/rollback transaksi — ia TIDAK menutup
koneksi/file handle. Di Linux/macOS itu tidak terlihat (file yang masih terbuka
tetap bisa dihapus), tapi di Windows itu membuat file database sementara tetap
terkunci, sehingga `tempfile.TemporaryDirectory` gagal dibersihkan setelah test
(`PermissionError: [WinError 32] The process cannot access the file...`) —
persis yang dilaporkan Ananda saat menjalankan test suite di komputernya
(ratusan ERROR, bukan cuma kegagalan test yang sudah dikenal).

Setiap `connect()`/`_connect()` di bawah ini sudah diubah jadi `@contextmanager`
yang menutup koneksi lewat `finally: connection.close()` (pola yang sama dengan
yang sudah lebih dulu dipakai di app/document_preferences.py). Test ini memverifikasi
langsung: begitu blok `with store._connect() as db:` (atau `.connect()`) selesai,
koneksinya benar-benar tertutup — bukan cuma "terlihat aman" dari luar.
"""
import tempfile
import unittest
from pathlib import Path

import sqlite3

from app.approval_gate import ApprovalGate
from app.attachment_guard import AttachmentGuard
from app.customer_book import CustomerBookStore
from app.dp_policy import DpPolicyStore
from app.finance import FinanceService
from app.google_sheets_sync import GoogleSheetsSync
from app.kill_switch import KillSwitch
from app.order_status import OrderStatusStore
from app.payment_gate import PaymentGateStore
from app.price_list import PriceListStore
from app.pricing import PricingConfigStore
from app.source_registry import SourceRegistry
from app.trust_layer import TrustLayer


class ConnectionActuallyClosesTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.db = Path(self.temp.name) / "assistant.db"

    def _assert_closes(self, store, method_name: str):
        connect = getattr(store, method_name)
        with connect() as db:
            pass
        with self.assertRaises(sqlite3.ProgrammingError, msg=f"{store.__class__.__name__}.{method_name} tidak menutup koneksi"):
            db.execute("SELECT 1")

    def test_finance_service_closes_connection(self):
        self._assert_closes(FinanceService(self.db), "connect")

    def test_source_registry_closes_connection(self):
        self._assert_closes(SourceRegistry(self.db), "connect")

    def test_approval_gate_closes_connection(self):
        self._assert_closes(ApprovalGate(self.db), "connect")

    def test_trust_layer_closes_connection(self):
        self._assert_closes(TrustLayer(self.db), "connect")

    def test_attachment_guard_closes_connection(self):
        quarantine = Path(self.temp.name) / "quarantine"
        self._assert_closes(AttachmentGuard(quarantine, self.db), "_connect")

    def test_customer_book_closes_connection(self):
        self._assert_closes(CustomerBookStore(self.db), "_connect")

    def test_dp_policy_closes_connection(self):
        self._assert_closes(DpPolicyStore(self.db), "_connect")

    def test_google_sheets_sync_closes_connection(self):
        self._assert_closes(GoogleSheetsSync(self.db), "_connect")

    def test_kill_switch_closes_connection(self):
        self._assert_closes(KillSwitch(self.db), "_connect")

    def test_order_status_closes_connection(self):
        self._assert_closes(OrderStatusStore(self.db), "_connect")

    def test_payment_gate_closes_connection(self):
        self._assert_closes(PaymentGateStore(self.db), "_connect")

    def test_price_list_closes_connection(self):
        self._assert_closes(PriceListStore(self.db), "_connect")

    def test_pricing_config_store_closes_connection(self):
        self._assert_closes(PricingConfigStore(self.db), "_connect")

    def test_temp_directory_cleanup_does_not_leave_any_connection_open(self):
        """Simulasi langsung kondisi yang bikin Windows gagal (WinError 32): buka lalu
        tutup blok `with` untuk semua store di atas dalam SATU direktori sementara,
        lalu pastikan tidak ada exception saat direktori itu coba dibersihkan
        (di Linux ini selalu lolos; nilainya ada di baris-baris `_assert_closes` di
        atas yang memverifikasi setiap koneksi individual benar-benar tertutup,
        bukan cuma "commit tapi belum di-release")."""
        quarantine = Path(self.temp.name) / "quarantine2"
        stores_and_methods = [
            (FinanceService(self.db), "connect"),
            (SourceRegistry(self.db), "connect"),
            (ApprovalGate(self.db), "connect"),
            (TrustLayer(self.db), "connect"),
            (AttachmentGuard(quarantine, self.db), "_connect"),
            (CustomerBookStore(self.db), "_connect"),
            (DpPolicyStore(self.db), "_connect"),
            (GoogleSheetsSync(self.db), "_connect"),
            (KillSwitch(self.db), "_connect"),
            (OrderStatusStore(self.db), "_connect"),
            (PaymentGateStore(self.db), "_connect"),
            (PriceListStore(self.db), "_connect"),
            (PricingConfigStore(self.db), "_connect"),
        ]
        for store, method_name in stores_and_methods:
            with getattr(store, method_name)() as db:
                db.execute("SELECT 1")
        # Tidak ada assert tambahan di sini — kegagalan sungguhan muncul di Windows
        # sebagai PermissionError saat self.temp.cleanup() dipanggil oleh addCleanup.


if __name__ == "__main__":
    unittest.main()
