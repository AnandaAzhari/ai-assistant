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

    def test_opening_balance_before_transactions(self):
        reply = self.lead.handle_admin_message("Set saldo awal BCA 500 ribu")
        self.assertEqual(reply.status, "berhasil")
        self.assertEqual(self.finance.balances()["BCA"], 500000)
        self.assertIn("Rp500.000", self.lead.handle_admin_message("/akun").text)

    def test_opening_balance_locked_after_transaction(self):
        self.lead.handle_admin_message("Set saldo awal BCA 500 ribu")
        self.lead.handle_admin_message(
            "Catat pengeluaran 80 ribu beli tinta untuk Taqi Desk pakai BCA"
        )
        with self.assertRaises(ValueError):
            self.finance.handle("Set saldo awal BCA 600 ribu")

    def test_record_expense_from_natural_language(self):
        reply = self.lead.handle_admin_message(
            "Catat pengeluaran 80 ribu beli tinta untuk Taqi Desk pakai BCA"
        )
        self.assertEqual(reply.target, "finance")
        self.assertEqual(reply.status, "berhasil")
        self.assertIn("Rp80.000", reply.text)
        self.assertIn("Tinta Printer", reply.text)
        self.assertEqual(self.finance.balances()["BCA"], -80000)

    def test_dynamic_category_is_created(self):
        reply = self.lead.handle_admin_message(
            "Catat pengeluaran 45 ribu beli kabel USB untuk Taqi Desk pakai Cash"
        )
        self.assertEqual(reply.status, "berhasil")
        self.assertIn("Kabel USB", reply.text)
        self.assertIn("kategori baru dibuat", reply.text)
        self.assertIn("Kabel USB", self.lead.handle_admin_message("/kategori").text)

    def test_explicit_category_override(self):
        reply = self.lead.handle_admin_message(
            "Catat pengeluaran 70 ribu beli rak kecil kategori Perlengkapan untuk Taqi Desk pakai Cash"
        )
        self.assertEqual(reply.status, "berhasil")
        self.assertIn("Perlengkapan", reply.text)

    def test_missing_business_does_not_write(self):
        reply = self.lead.handle_admin_message("Catat pengeluaran 80 ribu beli tinta pakai BCA")
        self.assertEqual(reply.status, "needs_review")
        self.assertIn("usaha atau Personal", reply.text)
        self.assertEqual(self.finance.today_summary()["count"], 0)

    def test_duplicate_guard(self):
        text = "Catat pemasukan 20 ribu jasa print untuk Taqi Desk pakai Cash"
        self.assertEqual(self.lead.handle_admin_message(text).status, "berhasil")
        with self.assertRaises(ValueError):
            self.finance.handle(text)

    def test_reports(self):
        self.lead.handle_admin_message(
            "Catat pemasukan 100 ribu jasa print untuk Taqi Desk pakai Cash"
        )
        self.lead.handle_admin_message(
            "Catat pengeluaran 25 ribu beli kertas untuk Taqi Desk pakai Cash"
        )
        reply = self.lead.handle_admin_message("/hari_ini")
        self.assertIn("Pemasukan: Rp100.000", reply.text)
        self.assertIn("Pengeluaran: Rp25.000", reply.text)
        self.assertIn("Arus kas bersih: Rp75.000", reply.text)


class FinanceSearchTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.db = Path(self.temp.name) / "finance.db"
        self.finance = FinanceService(self.db)

    def _record(self, **overrides):
        defaults = dict(
            kind="expense", amount=80000, account="BCA", business="Taqi Desk",
            category="Perlengkapan", description="Beli tinta printer",
        )
        defaults.update(overrides)
        return self.finance.record(**defaults)

    def test_search_matches_description(self):
        self._record(description="Beli tinta printer merek Epson")
        self.assertEqual(len(self.finance.search("tinta printer")), 1)

    def test_search_matches_category_and_business(self):
        self._record(category="Bahan Baku", business="Risol Mamqi", description="Belanja cabai")
        self.assertEqual(len(self.finance.search("bahan baku")), 1)
        self.assertEqual(len(self.finance.search("risol mamqi")), 1)

    def test_search_is_case_insensitive(self):
        self._record(description="Top up saldo DANA istri")
        self.assertEqual(len(self.finance.search("SALDO DANA")), 1)

    def test_search_no_match_returns_empty_list(self):
        self._record(description="Beli tinta printer")
        self.assertEqual(self.finance.search("sewa gedung"), [])

    def test_search_empty_keyword_returns_empty_list(self):
        self._record()
        self.assertEqual(self.finance.search(""), [])
        self.assertEqual(self.finance.search("   "), [])

    def test_search_orders_newest_first_and_respects_limit(self):
        for i in range(3):
            self._record(description=f"Cicilan sewa booth edisi {i}")
        hits = self.finance.search("Cicilan sewa booth", limit=2)
        self.assertEqual(len(hits), 2)
        self.assertIn("edisi 2", hits[0]["description"])

    def test_search_result_fields(self):
        self._record(
            kind="income", amount=150000, account="QRIS", business="Pixiva.ID",
            category="Jasa Foto", description="DP photobooth ulang tahun",
        )
        hits = self.finance.search("photobooth")
        self.assertEqual(len(hits), 1)
        hit = hits[0]
        self.assertEqual(hit["kind"], "income")
        self.assertEqual(hit["amount"], 150000)
        self.assertEqual(hit["account"], "QRIS")
        self.assertEqual(hit["business"], "Pixiva.ID")
        self.assertEqual(hit["category"], "Jasa Foto")


if __name__ == "__main__":
    unittest.main()
