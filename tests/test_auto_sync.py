import tempfile
import unittest
from pathlib import Path

from app.finance import FinanceService
from app.lead import LeadAgent
from app.google_sheets_sync import SheetsSyncResult


class FakeSheetsSync:
    def __init__(self, *, configured=True, succeed=True):
        self.configured = configured
        self.succeed = succeed
        self.calls = 0

    def status(self):
        if self.configured:
            return SheetsSyncResult("siap", "siap")
        return SheetsSyncResult("belum_dikonfigurasi", "belum")

    def sync_now(self, timeout=30):
        self.calls += 1
        if self.succeed:
            return SheetsSyncResult("berhasil", "ok")
        return SheetsSyncResult("gagal", "gagal")


class AutoSyncTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        db = Path(self.temp.name) / "assistant.db"
        self.finance = FinanceService(db)

    def test_transaction_triggers_auto_sync(self):
        sync = FakeSheetsSync()
        lead = LeadAgent(finance=self.finance, sheets_sync=sync)
        reply = lead.handle_admin_message(
            "Catat pengeluaran 80 ribu beli tinta untuk Taqi Desk pakai BCA"
        )
        self.assertEqual(reply.status, "berhasil")
        self.assertEqual(sync.calls, 1)
        self.assertIn("tersinkron otomatis", reply.text)

    def test_read_commands_do_not_auto_sync(self):
        sync = FakeSheetsSync()
        lead = LeadAgent(finance=self.finance, sheets_sync=sync)
        for command in ("/saldo", "/akun", "/kategori", "/hari_ini", "/bulan_ini"):
            with self.subTest(command=command):
                lead.handle_admin_message(command)
        self.assertEqual(sync.calls, 0)

    def test_opening_balance_triggers_auto_sync(self):
        sync = FakeSheetsSync()
        lead = LeadAgent(finance=self.finance, sheets_sync=sync)
        reply = lead.handle_admin_message("Set saldo awal BCA 500 ribu")
        self.assertEqual(reply.status, "berhasil")
        self.assertEqual(sync.calls, 1)
        self.assertIn("tersinkron otomatis", reply.text)

    def test_sync_failure_keeps_local_transaction(self):
        sync = FakeSheetsSync(succeed=False)
        lead = LeadAgent(finance=self.finance, sheets_sync=sync)
        reply = lead.handle_admin_message(
            "Catat pemasukan 100 ribu jasa print untuk Taqi Desk pakai Cash"
        )
        self.assertEqual(reply.status, "berhasil")
        self.assertEqual(sync.calls, 1)
        self.assertIn("Data lokal tetap tersimpan", reply.text)
        self.assertEqual(self.finance.today_summary()["count"], 1)

    def test_unconfigured_sync_does_not_block_finance(self):
        sync = FakeSheetsSync(configured=False)
        lead = LeadAgent(finance=self.finance, sheets_sync=sync)
        reply = lead.handle_admin_message(
            "Catat pemasukan 100 ribu jasa print untuk Taqi Desk pakai Cash"
        )
        self.assertEqual(reply.status, "berhasil")
        self.assertEqual(sync.calls, 0)
        self.assertEqual(self.finance.today_summary()["count"], 1)


if __name__ == "__main__":
    unittest.main()
