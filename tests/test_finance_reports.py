"""Laporan keuangan tambahan (minggu ini, laba/rugi, arus kas, filter per usaha/akun) —
lihat `app/finance.py` (`week_summary`, `profit_loss`, `cash_flow`) dan
`docs/finance_saas_v1.md`. Perilaku lama (`/hari_ini`, `/bulan_ini` tanpa argumen) tetap
diuji di `tests/test_finance.py`; file ini fokus ke fitur baru saja."""

import tempfile
import unittest
import uuid
from pathlib import Path

from app.finance import FinanceService
from app.lead import LeadAgent


class FinanceReportTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.db = Path(self.temp.name) / "finance.db"
        self.finance = FinanceService(self.db)
        self.lead = LeadAgent(finance=self.finance)

    def _insert_transaction(self, *, created, kind, amount, account, business, category="Lainnya"):
        """Sisipkan transaksi langsung lewat SQL dengan `created` terkontrol — dipakai
        untuk menguji `cash_flow()` menghitung saldo awal dari transaksi SEBELUM
        periode, sesuatu yang tidak bisa diatur lewat `record()` (selalu memakai
        `datetime.now()`). Pola direct-SQL ini sudah dipakai di
        `tests/test_finance_correction.py`."""
        with self.finance.connect() as db:
            db.execute(
                """INSERT INTO finance_transactions
                   (id, created, kind, amount, account, business, category, description, source, status)
                   VALUES (?,?,?,?,?,?,?,?,?,'confirmed')""",
                (str(uuid.uuid4()), created, kind, amount, account, business, category, "test", "test"),
            )

    def test_minggu_ini_includes_transaction_recorded_now(self):
        self.lead.handle_admin_message(
            "Catat pemasukan 100 ribu jasa print untuk Taqi Desk pakai Cash"
        )
        reply = self.lead.handle_admin_message("/minggu_ini")
        self.assertEqual(reply.status, "berhasil")
        self.assertIn("Minggu ini", reply.text)
        self.assertIn("Pemasukan: Rp100.000", reply.text)

    def test_hari_ini_with_business_filter_only_counts_that_business(self):
        self.lead.handle_admin_message(
            "Catat pemasukan 100 ribu jasa print untuk Taqi Desk pakai Cash"
        )
        self.lead.handle_admin_message(
            "Catat pemasukan 50 ribu jual risol untuk Risol Mamqi pakai Cash"
        )
        reply = self.lead.handle_admin_message("/hari_ini Risol Mamqi")
        self.assertEqual(reply.status, "berhasil")
        self.assertIn("(Risol Mamqi)", reply.text)
        self.assertIn("Pemasukan: Rp50.000", reply.text)
        self.assertNotIn("Rp100.000", reply.text)

    def test_bulan_ini_without_argument_still_aggregates_all_business_unchanged(self):
        self.lead.handle_admin_message(
            "Catat pemasukan 100 ribu jasa print untuk Taqi Desk pakai Cash"
        )
        self.lead.handle_admin_message(
            "Catat pemasukan 50 ribu jual risol untuk Risol Mamqi pakai Cash"
        )
        reply = self.lead.handle_admin_message("/bulan_ini")
        self.assertEqual(reply.status, "berhasil")
        self.assertIn("Pemasukan: Rp150.000", reply.text)

    def test_unknown_business_filter_is_rejected_with_helpful_message(self):
        reply = self.lead.handle_admin_message("/bulan_ini Usaha Yang Tidak Ada")
        self.assertEqual(reply.status, "needs_review")
        self.assertIn("tidak dikenali", reply.text)
        self.assertIn("Taqi Desk", reply.text)

    def test_laba_rugi_breaks_down_expense_by_category(self):
        self.lead.handle_admin_message(
            "Catat pemasukan 500 ribu jasa print untuk Taqi Desk pakai Cash"
        )
        self.lead.handle_admin_message(
            "Catat pengeluaran 100 ribu beli tinta untuk Taqi Desk pakai Cash"
        )
        self.lead.handle_admin_message(
            "Catat pengeluaran 50 ribu beli kertas untuk Taqi Desk pakai Cash"
        )
        reply = self.lead.handle_admin_message("/laba_rugi")
        self.assertEqual(reply.status, "berhasil")
        self.assertIn("Pendapatan: Rp500.000", reply.text)
        self.assertIn("Tinta Printer: Rp100.000", reply.text)
        self.assertIn("Kertas: Rp50.000", reply.text)
        self.assertIn("Total pengeluaran: Rp150.000", reply.text)
        self.assertIn("Laba bersih: Rp350.000", reply.text)

    def test_laba_rugi_shows_rugi_label_when_expense_exceeds_income(self):
        self.lead.handle_admin_message(
            "Catat pemasukan 50 ribu jasa print untuk Taqi Desk pakai Cash"
        )
        self.lead.handle_admin_message(
            "Catat pengeluaran 200 ribu beli tinta untuk Taqi Desk pakai Cash"
        )
        reply = self.lead.handle_admin_message("/laba_rugi")
        self.assertIn("Rugi bersih: Rp150.000", reply.text)
        self.assertNotIn("Laba bersih", reply.text)

    def test_laba_rugi_with_business_filter(self):
        self.lead.handle_admin_message(
            "Catat pemasukan 500 ribu jasa print untuk Taqi Desk pakai Cash"
        )
        self.lead.handle_admin_message(
            "Catat pemasukan 50 ribu jual risol untuk Risol Mamqi pakai Cash"
        )
        reply = self.lead.handle_admin_message("/laba_rugi Risol Mamqi")
        self.assertIn("Risol Mamqi", reply.text)
        self.assertIn("Pendapatan: Rp50.000", reply.text)

    def test_arus_kas_computes_opening_balance_from_transactions_before_period(self):
        self.finance.set_opening_balance("BCA", 200000)
        # Transaksi bulan LALU (di luar periode /arus_kas bulan ini) — harus tetap
        # terhitung sebagai bagian saldo awal periode berjalan.
        last_month = "2020-01-15T10:00:00"
        self._insert_transaction(
            created=last_month, kind="income", amount=300000, account="BCA", business="Taqi Desk",
        )
        self.lead.handle_admin_message(
            "Catat pemasukan 100 ribu jasa print untuk Taqi Desk pakai BCA"
        )
        reply = self.lead.handle_admin_message("/arus_kas BCA")
        self.assertEqual(reply.status, "berhasil")
        # Saldo awal periode = 200rb (opening) + 300rb (transaksi sebelum periode) = 500rb.
        self.assertIn("saldo awal Rp500.000", reply.text)
        self.assertIn("masuk Rp100.000", reply.text)
        self.assertIn("keluar Rp0", reply.text)
        self.assertIn("saldo akhir Rp600.000", reply.text)

    def test_arus_kas_without_account_lists_all_active_accounts(self):
        reply = self.lead.handle_admin_message("/arus_kas")
        self.assertEqual(reply.status, "berhasil")
        for account_name in ("Cash", "BCA", "BNI"):
            self.assertIn(account_name, reply.text)

    def test_unknown_account_filter_is_rejected_with_helpful_message(self):
        reply = self.lead.handle_admin_message("/arus_kas Rekening Antah Berantah")
        self.assertEqual(reply.status, "needs_review")
        self.assertIn("tidak dikenali", reply.text)


class FinanceServiceReportUnitTests(unittest.TestCase):
    """Unit test langsung ke `FinanceService`, terpisah dari format teks Telegram."""

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.finance = FinanceService(Path(self.temp.name) / "finance.db")

    def test_category_breakdown_orders_by_total_descending(self):
        self.finance.record(
            kind="expense", amount=100000, account="Cash", business="Taqi Desk",
            category="Tinta", description="beli tinta",
        )
        self.finance.record(
            kind="expense", amount=300000, account="Cash", business="Taqi Desk",
            category="Kertas", description="beli kertas",
        )
        from datetime import datetime, timedelta
        start = (datetime.now() - timedelta(days=1)).isoformat(timespec="seconds")
        end = (datetime.now() + timedelta(days=1)).isoformat(timespec="seconds")
        rows = self.finance.category_breakdown(start, end, "expense")
        self.assertEqual([row["category"] for row in rows], ["Kertas", "Tinta"])

    def test_profit_loss_net_matches_income_minus_expense(self):
        self.finance.record(
            kind="income", amount=1000000, account="Cash", business="Taqi Desk",
            category="Jasa", description="jasa print",
        )
        self.finance.record(
            kind="expense", amount=400000, account="Cash", business="Taqi Desk",
            category="Tinta", description="beli tinta",
        )
        data = self.finance.month_summary()
        from datetime import datetime
        start, end = self.finance._month_bounds(datetime.now())
        pnl = self.finance.profit_loss(
            start.isoformat(timespec="seconds"), end.isoformat(timespec="seconds"),
        )
        self.assertEqual(pnl["net"], data["net"])
        self.assertEqual(pnl["net"], 600000)


if __name__ == "__main__":
    unittest.main()
