import tempfile
import unittest
from pathlib import Path

from app.finance import FinanceService
from app.google_sheets_sync import SheetsSyncResult
from app.lead import LeadAgent


class FakeSheetsSync:
    configured = True

    def __init__(self):
        self.calls = 0

    def status(self):
        return SheetsSyncResult("siap", "siap")

    def sync_now(self, timeout=30):
        self.calls += 1
        return SheetsSyncResult("berhasil", "ok")


class FinanceCorrectionTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.db = Path(self.temp.name) / "assistant.db"
        self.finance = FinanceService(self.db)

    def test_correction_moves_latest_expense_to_correct_account(self):
        lead = LeadAgent(finance=self.finance)
        reply = lead.handle_admin_message(
            "Catat pengeluaran 300 ribu top up saldo DANA istri pakai DANA"
        )
        self.assertEqual(reply.status, "berhasil")
        self.assertEqual(self.finance.balances()["DANA"], -300000)

        corrected = lead.handle_admin_message(
            "Koreksi transaksi terakhir, akun seharusnya BNI"
        )
        self.assertEqual(corrected.status, "berhasil")
        self.assertEqual(self.finance.balances()["DANA"], 0)
        self.assertEqual(self.finance.balances()["BNI"], -300000)

        with self.finance.connect() as db:
            statuses = [row[0] for row in db.execute(
                "SELECT status FROM finance_transactions ORDER BY created,rowid"
            ).fetchall()]
            audit_count = db.execute("SELECT COUNT(*) FROM finance_corrections").fetchone()[0]
        self.assertEqual(statuses, ["reversed", "confirmed"])
        self.assertEqual(audit_count, 1)

    def test_topup_without_source_is_not_written(self):
        lead = LeadAgent(finance=self.finance)
        reply = lead.handle_admin_message(
            "Catat pengeluaran 300 ribu top up saldo DANA istri"
        )
        self.assertEqual(reply.status, "needs_review")
        self.assertIn("akun sumber", reply.text)
        self.assertEqual(self.finance.today_summary()["count"], 0)

    def test_correction_triggers_auto_sync(self):
        sync = FakeSheetsSync()
        lead = LeadAgent(finance=self.finance, sheets_sync=sync)
        lead.handle_admin_message(
            "Catat pengeluaran 300 ribu top up saldo DANA istri pakai DANA"
        )
        calls_after_create = sync.calls
        reply = lead.handle_admin_message(
            "Koreksi transaksi terakhir, akun seharusnya BNI"
        )
        self.assertEqual(reply.status, "berhasil")
        self.assertEqual(sync.calls, calls_after_create + 1)
        self.assertIn("tersinkron otomatis", reply.text)


if __name__ == "__main__":
    unittest.main()
