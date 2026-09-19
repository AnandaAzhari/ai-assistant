import tempfile
import unittest
from pathlib import Path

from app.lead import LeadAgent
from app.price_list import PriceListStore


class PriceListStoreTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.db = Path(self.temp.name) / "assistant.db"
        self.store = PriceListStore(self.db)

    def test_set_and_find_exact_service_name(self):
        self.store.set_price("Cetak Skripsi", "Rp250/lembar hitam putih", updated_by="admin:telegram")
        entry = self.store.find("berapa harga cetak skripsi ya kak")
        self.assertIsNotNone(entry)
        self.assertEqual(entry.display_name, "Cetak Skripsi")
        self.assertEqual(entry.price_text, "Rp250/lembar hitam putih")

    def test_find_returns_none_when_no_match(self):
        self.store.set_price("Cetak Skripsi", "Rp250/lembar", updated_by="admin:telegram")
        self.assertIsNone(self.store.find("harga foto photobooth berapa"))

    def test_find_prefers_most_specific_longest_match(self):
        self.store.set_price("Cetak Skripsi", "Rp250/lembar hitam putih", updated_by="admin:telegram")
        self.store.set_price("Cetak Skripsi Warna", "Rp1000/lembar warna", updated_by="admin:telegram")
        entry = self.store.find("mau tanya harga cetak skripsi warna dong")
        self.assertEqual(entry.display_name, "Cetak Skripsi Warna")

    def test_set_price_overwrites_previous_entry_for_same_service_case_insensitive(self):
        self.store.set_price("Cetak Skripsi", "Rp250/lembar", updated_by="admin:telegram")
        self.store.set_price("cetak   skripsi", "Rp300/lembar (naik harga kertas)", updated_by="admin:web")
        entries = self.store.list_all()
        self.assertEqual(len(entries), 1)
        self.assertEqual(entries[0].price_text, "Rp300/lembar (naik harga kertas)")
        self.assertEqual(entries[0].updated_by, "admin:web")

    def test_remove_deletes_entry(self):
        self.store.set_price("Cetak Skripsi", "Rp250/lembar", updated_by="admin:telegram")
        self.assertTrue(self.store.remove("Cetak Skripsi"))
        self.assertIsNone(self.store.find("cetak skripsi"))

    def test_remove_missing_entry_returns_false(self):
        self.assertFalse(self.store.remove("Layanan Yang Tidak Ada"))

    def test_empty_service_or_price_is_rejected(self):
        with self.assertRaises(ValueError):
            self.store.set_price("", "Rp1000", updated_by="admin:telegram")
        with self.assertRaises(ValueError):
            self.store.set_price("Cetak", "", updated_by="admin:telegram")
        with self.assertRaises(ValueError):
            self.store.set_price("Cetak", "Rp1000", updated_by="")

    def test_note_is_included_in_entry(self):
        entry = self.store.set_price(
            "Jilid Softcover", "Rp15.000", note="Belum termasuk laminasi", updated_by="admin:telegram",
        )
        self.assertEqual(entry.note, "Belum termasuk laminasi")


class LeadAgentPriceListAdminCommandTests(unittest.TestCase):
    """Command admin (app/lead.py handle_admin_message) untuk mengelola price list."""

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.db = Path(self.temp.name) / "assistant.db"
        self.price_list = PriceListStore(self.db)
        self.lead = LeadAgent(admin_channel="telegram", price_list=self.price_list)

    def test_without_price_list_configured_reports_unavailable(self):
        lead = LeadAgent(admin_channel="telegram")
        reply = lead.handle_admin_message("/harga_set Cetak Skripsi | Rp250/lembar")
        self.assertEqual(reply.status, "belum_dikonfigurasi")

    def test_harga_set_saves_entry(self):
        reply = self.lead.handle_admin_message("/harga_set Cetak Skripsi | Rp250/lembar | Minimal 10 lembar")
        self.assertEqual(reply.status, "berhasil")
        entry = self.price_list.find("cetak skripsi")
        self.assertEqual(entry.price_text, "Rp250/lembar")
        self.assertEqual(entry.note, "Minimal 10 lembar")

    def test_harga_set_without_pipe_separator_reports_format_error(self):
        reply = self.lead.handle_admin_message("/harga_set Cetak Skripsi Rp250 per lembar")
        self.assertEqual(reply.status, "format_salah")
        self.assertIsNone(self.price_list.find("cetak skripsi"))

    def test_harga_hapus_removes_entry(self):
        self.lead.handle_admin_message("/harga_set Cetak Skripsi | Rp250/lembar")
        reply = self.lead.handle_admin_message("/harga_hapus Cetak Skripsi")
        self.assertEqual(reply.status, "berhasil")
        self.assertIsNone(self.price_list.find("cetak skripsi"))

    def test_harga_list_shows_all_entries(self):
        self.lead.handle_admin_message("/harga_set Cetak Skripsi | Rp250/lembar")
        self.lead.handle_admin_message("/harga_set Jilid Softcover | Rp15.000")
        reply = self.lead.handle_admin_message("/harga_list")
        self.assertIn("Cetak Skripsi", reply.text)
        self.assertIn("Jilid Softcover", reply.text)


class HandleCustomerMessagePriceListTests(unittest.TestCase):
    """handle_customer_message() menjawab dari price list asli kalau ada, tetap
    fallback ke teks generik kalau tidak ketemu — lihat app/lead.py
    `_augment_reply_with_real_data`."""

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.db = Path(self.temp.name) / "assistant.db"

    def _lead(self):
        from app.approval_gate import ApprovalGate
        from app.trust_layer import TrustLayer

        price_list = PriceListStore(self.db)
        lead = LeadAgent(
            trust_layer=TrustLayer(self.db), approval_gate=ApprovalGate(self.db), price_list=price_list,
        )
        return lead, price_list

    def test_price_question_answered_from_real_price_list(self):
        lead, price_list = self._lead()
        price_list.set_price("Cetak Skripsi", "Rp250/lembar hitam putih", updated_by="admin:telegram")
        reply = lead.handle_customer_message("628111", "Kak, harga cetak skripsi berapa ya?")
        self.assertEqual(reply.target, "kirim_estimasi_harga_standar")
        self.assertIn("Rp250/lembar hitam putih", reply.text)

    def test_price_question_without_matching_entry_falls_back_to_generic_reply(self):
        lead, price_list = self._lead()
        price_list.set_price("Cetak Skripsi", "Rp250/lembar", updated_by="admin:telegram")
        reply = lead.handle_customer_message("628222", "Kak, harga cetak banner berapa ya?")
        self.assertEqual(reply.target, "kirim_estimasi_harga_standar")
        self.assertNotIn("Rp250/lembar", reply.text)
        self.assertIn("admin", reply.text.casefold())


if __name__ == "__main__":
    unittest.main()
