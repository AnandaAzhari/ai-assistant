import tempfile
import unittest
from pathlib import Path

from app.finance import FinanceService, parse_amount
from app.lead import LeadAgent


class FinanceTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.db = Path(self.temp.name) / "finance.db"
        self.finance = FinanceService(self.db)
        self.lead = LeadAgent(finance=self.finance)

    def test_parse_indonesian_amounts(self):
        self.assertEqual(parse_amount("80 ribu"), 80000)
        self.assertEqual(parse_amount("80rb"), 80000)
        self.assertEqual(parse_amount("1,5 juta"), 1500000)
        self.assertEqual(parse_amount("120.000"), 120000)

    def test_record_expense_from_natural_language(self):
        reply = self.lead.handle_admin_message(
            "Catat pengeluaran 80 ribu beli tinta untuk Taqi DocuTech pakai BCA"
        )
        self.assertEqual(reply.target, "finance")
        self.assertEqual(reply.status, "berhasil")
        self.assertIn("Rp80.000", reply.text)
        self.assertIn("Tinta Printer", reply.text)
        self.assertEqual(self.finance.balances()["BCA"], -80000)

    def test_missing_business_does_not_write(self):
        reply = self.lead.handle_admin_message("Catat pengeluaran 80 ribu beli tinta pakai BCA")
        self.assertEqual(reply.status, "needs_review")
        self.assertIn("usaha atau Personal", reply.text)
        self.assertEqual(self.finance.today_summary()["count"], 0)

    def test_duplicate_guard(self):
        text = "Catat pemasukan 20 ribu jasa print untuk Taqi DocuTech pakai Cash"
        self.assertEqual(self.lead.handle_admin_message(text).status, "berhasil")
        with self.assertRaises(ValueError):
            self.finance.handle(text)

    def test_reports(self):
        self.lead.handle_admin_message(
            "Catat pemasukan 100 ribu jasa print untuk Taqi DocuTech pakai Cash"
        )
        self.lead.handle_admin_message(
            "Catat pengeluaran 25 ribu beli kertas untuk Taqi DocuTech pakai Cash"
        )
        reply = self.lead.handle_admin_message("/hari_ini")
        self.assertIn("Pemasukan: Rp100.000", reply.text)
        self.assertIn("Pengeluaran: Rp25.000", reply.text)
        self.assertIn("Arus kas bersih: Rp75.000", reply.text)


if __name__ == "__main__":
    unittest.main()
