import tempfile
import unittest
from pathlib import Path

from app.payment_gate import PaymentGateStore


class PaymentGateStoreTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.db = Path(self.temp.name) / "assistant.db"
        self.store = PaymentGateStore(self.db)

    def test_no_pending_release_for_unknown_sender(self):
        self.assertIsNone(self.store.get_pending("628111"))
        self.assertIsNone(self.store.pop_ready_release("628111"))

    def test_save_then_get_pending(self):
        self.store.save_pending("628111", "/final/berkas.docx", "/final/berkas.pdf")
        entry = self.store.get_pending("628111")
        self.assertIsNotNone(entry)
        self.assertEqual(entry.docx_path, "/final/berkas.docx")
        self.assertEqual(entry.pdf_path, "/final/berkas.pdf")
        self.assertEqual(entry.paid_at, "")
        self.assertEqual(entry.delivered_at, "")

    def test_pop_ready_release_returns_none_before_marked_paid(self):
        self.store.save_pending("628111", "/final/berkas.docx", "/final/berkas.pdf")
        self.assertIsNone(self.store.pop_ready_release("628111"))

    def test_mark_paid_returns_none_when_nothing_pending(self):
        self.assertIsNone(self.store.mark_paid("628111", updated_by="admin:telegram"))

    def test_mark_paid_then_pop_ready_release_delivers_once(self):
        self.store.save_pending("628111", "/final/berkas.docx", "/final/berkas.pdf")
        marked = self.store.mark_paid("628111", updated_by="admin:telegram")
        self.assertIsNotNone(marked)
        self.assertNotEqual(marked.paid_at, "")

        release = self.store.pop_ready_release("628111")
        self.assertIsNotNone(release)
        self.assertEqual(release.docx_path, "/final/berkas.docx")
        self.assertEqual(release.pdf_path, "/final/berkas.pdf")

        # Sekali diambil, tidak boleh dikirim ulang lagi untuk pesan berikutnya
        # (lihat docstring PaymentGateStore.pop_ready_release).
        self.assertIsNone(self.store.pop_ready_release("628111"))

    def test_save_pending_resets_paid_state_for_new_order(self):
        """Kalau pelanggan yang sama pesan makalah lagi (order baru) sebelum order
        lamanya diambil, save_pending menimpa entri lama — mencegah rilis "lunas"
        yang salah sasaran ke order baru yang belum tentu sudah dibayar."""
        self.store.save_pending("628111", "/lama.docx", "/lama.pdf")
        self.store.mark_paid("628111", updated_by="admin:telegram")

        self.store.save_pending("628111", "/baru.docx", "/baru.pdf")
        self.assertIsNone(self.store.pop_ready_release("628111"))
        entry = self.store.get_pending("628111")
        self.assertEqual(entry.docx_path, "/baru.docx")
        self.assertEqual(entry.paid_at, "")

    def test_clear_removes_pending_entry(self):
        self.store.save_pending("628111", "/final/berkas.docx", "/final/berkas.pdf")
        self.assertTrue(self.store.clear("628111"))
        self.assertIsNone(self.store.get_pending("628111"))
        self.assertFalse(self.store.clear("628111"))

    def test_payment_info_defaults_to_empty(self):
        self.assertEqual(self.store.get_payment_info(), "")

    def test_set_then_get_payment_info(self):
        self.store.set_payment_info(
            "Transfer BCA 1234567890 a.n. Ananda Azhari", updated_by="admin:telegram",
        )
        self.assertEqual(self.store.get_payment_info(), "Transfer BCA 1234567890 a.n. Ananda Azhari")

    def test_set_payment_info_overwrites_previous_value(self):
        self.store.set_payment_info("Versi lama", updated_by="admin:telegram")
        self.store.set_payment_info("Versi baru", updated_by="admin:telegram")
        self.assertEqual(self.store.get_payment_info(), "Versi baru")

    def test_set_payment_info_rejects_empty_text(self):
        with self.assertRaises(ValueError):
            self.store.set_payment_info("   ", updated_by="admin:telegram")

    def test_save_pending_rejects_missing_fields(self):
        with self.assertRaises(ValueError):
            self.store.save_pending("", "/a.docx", "/a.pdf")
        with self.assertRaises(ValueError):
            self.store.save_pending("628111", "", "/a.pdf")


if __name__ == "__main__":
    unittest.main()
