"""Integration tests untuk command admin baru di app/lead.py yang memakai
app/pricing.py (kalkulator harga) dan app/dp_policy.py (kebijakan DP
wajib/opsional). Lihat tests/test_pricing.py dan tests/test_dp_policy.py untuk
tes unit modulnya sendiri — fokus di sini murni pada wiring command Telegram/
Web Admin: parsing, fallback fail-safe saat modul belum dikonfigurasi, dan
bahwa balasan menampilkan data yang benar-benar dihitung, bukan dikarang."""

import tempfile
import unittest
from pathlib import Path

from app.dp_policy import DpPolicyStore
from app.lead import LeadAgent
from app.pricing import PricingConfigStore


class PricingCommandsUnconfiguredFallbackTests(unittest.TestCase):
    def test_paket_set_without_pricing_store_is_fail_safe(self):
        lead = LeadAgent()
        reply = lead.handle_admin_message("/paket_set Standar | 10 | 60000")
        self.assertEqual(reply.status, "belum_dikonfigurasi")

    def test_hitung_harga_without_pricing_store_is_fail_safe(self):
        lead = LeadAgent()
        reply = lead.handle_admin_message("/hitung_harga 8")
        self.assertEqual(reply.status, "belum_dikonfigurasi")

    def test_dp_wajib_without_dp_policy_is_fail_safe(self):
        lead = LeadAgent()
        reply = lead.handle_admin_message("/dp_wajib")
        self.assertEqual(reply.status, "belum_dikonfigurasi")


class PricingCommandsTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.pricing = PricingConfigStore(Path(self.temp.name) / "assistant.db")
        self.lead = LeadAgent(pricing=self.pricing)

    def test_paket_set_stores_and_paket_list_shows_it(self):
        reply = self.lead.handle_admin_message("/paket_set Ekonomis | 3 | 20000")
        self.assertEqual(reply.status, "berhasil")
        self.assertIn("Ekonomis", reply.text)
        listing = self.lead.handle_admin_message("/paket_list")
        self.assertIn("Ekonomis", listing.text)

    def test_paket_set_rejects_malformed_input(self):
        reply = self.lead.handle_admin_message("/paket_set Ekonomis tanpa pemisah")
        self.assertEqual(reply.status, "format_salah")

    def test_paket_hapus_removes_existing_package(self):
        reply = self.lead.handle_admin_message("/paket_hapus Ringkas")
        self.assertEqual(reply.status, "berhasil")
        listing = self.lead.handle_admin_message("/paket_list")
        self.assertNotIn("Ringkas", listing.text)

    def test_paket_hapus_reports_not_found(self):
        reply = self.lead.handle_admin_message("/paket_hapus Tidak Ada")
        self.assertEqual(reply.status, "tidak_ditemukan")

    def test_tarif_set_updates_known_key(self):
        reply = self.lead.handle_admin_message("/tarif_set halaman_tambahan 7000")
        self.assertEqual(reply.status, "berhasil")
        self.assertEqual(self.pricing.all_settings()["halaman_tambahan"], 7000)

    def test_tarif_set_rejects_unknown_key(self):
        reply = self.lead.handle_admin_message("/tarif_set kunci_ngawur 100")
        self.assertEqual(reply.status, "format_salah")

    def test_tarif_set_accepts_rupiah_formatted_amount(self):
        reply = self.lead.handle_admin_message("/tarif_set halaman_tambahan Rp7.000")
        self.assertEqual(reply.status, "berhasil")
        self.assertEqual(self.pricing.all_settings()["halaman_tambahan"], 7000)

    def test_hitung_harga_auto_package_matches_manual_calculation(self):
        reply = self.lead.handle_admin_message("/hitung_harga 8")
        self.assertEqual(reply.status, "berhasil")
        self.assertIn("Standar", reply.text)
        self.assertIn("Rp60.000", reply.text)
        self.assertIn("Rp18.000", reply.text)  # DP referensi
        self.assertIn("Rp42.000", reply.text)  # sisa

    def test_hitung_harga_with_explicit_package(self):
        reply = self.lead.handle_admin_message("/hitung_harga 8 | Ringkas")
        self.assertEqual(reply.status, "berhasil")
        self.assertIn("Rp53.000", reply.text)

    def test_hitung_harga_rejects_non_numeric_pages(self):
        reply = self.lead.handle_admin_message("/hitung_harga delapan")
        self.assertEqual(reply.status, "format_salah")

    def test_hitung_rapikan_computes_expected_total(self):
        reply = self.lead.handle_admin_message("/hitung_rapikan struktur 12")
        self.assertEqual(reply.status, "berhasil")
        self.assertIn("Rp42.000", reply.text)  # 12 x 3500

    def test_hitung_rapikan_rejects_unknown_level(self):
        reply = self.lead.handle_admin_message("/hitung_rapikan super 12")
        self.assertEqual(reply.status, "format_salah")


class DpPolicyCommandsTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.dp_policy = DpPolicyStore(Path(self.temp.name) / "dp.db")
        self.lead = LeadAgent(dp_policy=self.dp_policy)

    def test_default_status_is_optional(self):
        reply = self.lead.handle_admin_message("/dp_status")
        self.assertIn("opsional", reply.text)

    def test_dp_wajib_then_status_reflects_it(self):
        activate = self.lead.handle_admin_message("/dp_wajib banyak yang kabur")
        self.assertEqual(activate.status, "berhasil")
        status = self.lead.handle_admin_message("/dp_status")
        self.assertIn("WAJIB", status.text)
        self.assertIn("banyak yang kabur", status.text)

    def test_dp_opsional_reverts_status(self):
        self.lead.handle_admin_message("/dp_wajib")
        reply = self.lead.handle_admin_message("/dp_opsional sudah stabil")
        self.assertEqual(reply.status, "berhasil")
        status = self.lead.handle_admin_message("/dp_status")
        self.assertIn("opsional", status.text)


if __name__ == "__main__":
    unittest.main()
