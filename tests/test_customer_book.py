import tempfile
import unittest
from pathlib import Path

from app.customer_book import CustomerBookStore
from app.lead import LeadAgent


class CustomerBookStoreTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.db = Path(self.temp.name) / "assistant.db"
        self.store = CustomerBookStore(self.db)

    def test_touch_creates_customer_with_zero_default_profile(self):
        entry = self.store.touch("628111")
        self.assertEqual(entry.sender_id, "628111")
        self.assertEqual(entry.display_name, "")
        self.assertEqual(entry.business, "")
        self.assertEqual(entry.total_contacts, 1)

    def test_touch_increments_total_contacts_and_never_overwrites_profile(self):
        self.store.set_profile("628111", display_name="Budi", business="Risol Mamqi")
        self.store.touch("628111")
        entry = self.store.touch("628111")
        self.assertEqual(entry.total_contacts, 2)
        self.assertEqual(entry.display_name, "Budi")
        self.assertEqual(entry.business, "Risol Mamqi")

    def test_set_profile_fills_blank_fields_only(self):
        self.store.set_profile("628111", display_name="Budi", business="Risol Mamqi")
        entry = self.store.set_profile("628111", notes="pelanggan lama")
        self.assertEqual(entry.display_name, "Budi")
        self.assertEqual(entry.business, "Risol Mamqi")
        self.assertEqual(entry.notes, "pelanggan lama")

    def test_get_customer_returns_none_when_never_seen(self):
        self.assertIsNone(self.store.get_customer("628999"))

    def test_customer_never_sees_another_customers_profile_or_orders(self):
        # Isolasi antar pelanggan (policies/security_policy.md), sama seperti
        # tests/test_order_status.py — 628222 tidak boleh pernah melihat data 628111.
        self.store.set_profile("628111", display_name="Budi", business="Risol Mamqi")
        self.store.record_order("628111", "Risol Mamqi", "Risol isi ayam x10", amount=50000, created_by="admin:telegram")
        self.assertIsNone(self.store.get_customer("628222"))
        self.assertEqual(self.store.list_orders_for_customer("628222"), [])

    def test_record_order_creates_customer_row_if_not_seen_yet(self):
        entry = self.store.record_order(
            "628333", "Taqi Desk", "Print makalah 50 lembar", amount=25000, created_by="admin:telegram",
        )
        self.assertEqual(entry.business, "Taqi Desk")
        customer = self.store.get_customer("628333")
        self.assertIsNotNone(customer)
        self.assertEqual(customer.business, "Taqi Desk")
        self.assertEqual(customer.total_contacts, 0)

    def test_record_order_does_not_overwrite_existing_business(self):
        self.store.set_profile("628111", business="Risol Mamqi")
        self.store.record_order("628111", "Taqi Desk", "Print undangan", created_by="admin:telegram")
        customer = self.store.get_customer("628111")
        self.assertEqual(customer.business, "Risol Mamqi")

    def test_list_orders_for_customer_returns_most_recent_first(self):
        self.store.record_order("628111", "Risol Mamqi", "Order 1", created_by="admin:telegram")
        self.store.record_order("628111", "Risol Mamqi", "Order 2", created_by="admin:telegram")
        orders = self.store.list_orders_for_customer("628111")
        self.assertEqual([entry.item_description for entry in orders], ["Order 2", "Order 1"])

    def test_update_order_status_changes_status_and_returns_true(self):
        entry = self.store.record_order("628111", "Risol Mamqi", "Order 1", created_by="admin:telegram")
        self.assertTrue(self.store.update_order_status(entry.id, "selesai", updated_by="admin:telegram"))
        orders = self.store.list_orders_for_customer("628111")
        self.assertEqual(orders[0].status, "selesai")

    def test_update_order_status_returns_false_for_unknown_order(self):
        self.assertFalse(self.store.update_order_status("CO-unknown", "selesai", updated_by="admin:telegram"))

    def test_summary_by_business_totals_order_count_and_omzet(self):
        self.store.record_order("628111", "Risol Mamqi", "Order 1", amount=50000, created_by="admin:telegram")
        self.store.record_order("628222", "Risol Mamqi", "Order 2", amount=30000, created_by="admin:telegram")
        self.store.record_order("628111", "Taqi Desk", "Print", amount=10000, created_by="admin:telegram")
        summary = self.store.summary_by_business("Risol Mamqi")
        self.assertEqual(summary["total_order"], 2)
        self.assertEqual(summary["total_omzet"], 80000)

    def test_summary_by_business_ignores_orders_without_amount(self):
        self.store.record_order("628111", "Risol Mamqi", "Order tanpa harga", created_by="admin:telegram")
        summary = self.store.summary_by_business("Risol Mamqi")
        self.assertEqual(summary["total_order"], 1)
        self.assertEqual(summary["total_omzet"], 0)

    def test_record_order_rejects_missing_required_fields(self):
        with self.assertRaises(ValueError):
            self.store.record_order("", "Risol Mamqi", "Order", created_by="admin:telegram")
        with self.assertRaises(ValueError):
            self.store.record_order("628111", "", "Order", created_by="admin:telegram")
        with self.assertRaises(ValueError):
            self.store.record_order("628111", "Risol Mamqi", "", created_by="admin:telegram")
        with self.assertRaises(ValueError):
            self.store.record_order("628111", "Risol Mamqi", "Order", created_by="")

    def test_record_order_rejects_negative_amount(self):
        with self.assertRaises(ValueError):
            self.store.record_order("628111", "Risol Mamqi", "Order", amount=-1000, created_by="admin:telegram")


class LeadAgentCustomerBookAdminCommandTests(unittest.TestCase):
    """Command admin (app/lead.py handle_admin_message) untuk profil/order pelanggan."""

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.db = Path(self.temp.name) / "assistant.db"
        self.customer_book = CustomerBookStore(self.db)
        self.lead = LeadAgent(admin_channel="telegram", customer_book=self.customer_book)

    def test_without_customer_book_configured_reports_unavailable(self):
        lead = LeadAgent(admin_channel="telegram")
        for command in ("/pelanggan_nama 628111 | Budi", "/pelanggan_catat 628111 Risol Mamqi | Order",
                        "/pelanggan_riwayat 628111", "/pelanggan_ringkasan Risol Mamqi"):
            with self.subTest(command=command):
                reply = lead.handle_admin_message(command)
                self.assertEqual(reply.status, "belum_dikonfigurasi")

    def test_pelanggan_nama_saves_profile(self):
        reply = self.lead.handle_admin_message("/pelanggan_nama 628111 | Budi | Risol Mamqi")
        self.assertEqual(reply.status, "berhasil")
        customer = self.customer_book.get_customer("628111")
        self.assertEqual(customer.display_name, "Budi")
        self.assertEqual(customer.business, "Risol Mamqi")

    def test_pelanggan_nama_without_name_reports_format_error(self):
        reply = self.lead.handle_admin_message("/pelanggan_nama 628111")
        self.assertEqual(reply.status, "format_salah")

    def test_pelanggan_catat_saves_order_with_amount(self):
        reply = self.lead.handle_admin_message("/pelanggan_catat 628111 Risol Mamqi | Risol isi ayam x10 | 50000")
        self.assertEqual(reply.status, "berhasil")
        orders = self.customer_book.list_orders_for_customer("628111")
        self.assertEqual(len(orders), 1)
        self.assertEqual(orders[0].business, "Risol Mamqi")
        self.assertEqual(orders[0].amount, 50000)

    def test_pelanggan_catat_accepts_dotted_price(self):
        reply = self.lead.handle_admin_message("/pelanggan_catat 628111 Risol Mamqi | Risol isi ayam x10 | Rp 50.000")
        self.assertEqual(reply.status, "berhasil")
        orders = self.customer_book.list_orders_for_customer("628111")
        self.assertEqual(orders[0].amount, 50000)

    def test_pelanggan_catat_without_item_reports_format_error(self):
        reply = self.lead.handle_admin_message("/pelanggan_catat 628111 Risol Mamqi")
        self.assertEqual(reply.status, "format_salah")
        self.assertEqual(self.customer_book.list_orders_for_customer("628111"), [])

    def test_pelanggan_riwayat_shows_profile_and_orders(self):
        self.lead.handle_admin_message("/pelanggan_nama 628111 | Budi | Risol Mamqi")
        self.lead.handle_admin_message("/pelanggan_catat 628111 Risol Mamqi | Risol isi ayam x10 | 50000")
        reply = self.lead.handle_admin_message("/pelanggan_riwayat 628111")
        self.assertIn("Budi", reply.text)
        self.assertIn("Risol isi ayam x10", reply.text)

    def test_pelanggan_riwayat_for_unknown_customer_reports_empty(self):
        reply = self.lead.handle_admin_message("/pelanggan_riwayat 628999")
        self.assertEqual(reply.status, "berhasil")
        self.assertIn("Belum ada data", reply.text)

    def test_pelanggan_ringkasan_totals_order_and_omzet(self):
        self.lead.handle_admin_message("/pelanggan_catat 628111 Risol Mamqi | Order 1 | 50000")
        self.lead.handle_admin_message("/pelanggan_catat 628222 Risol Mamqi | Order 2 | 30000")
        reply = self.lead.handle_admin_message("/pelanggan_ringkasan Risol Mamqi")
        self.assertEqual(reply.status, "berhasil")
        self.assertIn("2 order", reply.text)


class HandleCustomerMessageCustomerBookTests(unittest.TestCase):
    """handle_customer_message() otomatis mencatat kontak pelanggan tanpa pernah
    menebak nama/bisnis — lihat app/lead.py `handle_customer_message`."""

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.db = Path(self.temp.name) / "assistant.db"

    def _lead(self):
        from app.approval_gate import ApprovalGate
        from app.trust_layer import TrustLayer

        customer_book = CustomerBookStore(self.db)
        lead = LeadAgent(
            trust_layer=TrustLayer(self.db), approval_gate=ApprovalGate(self.db), customer_book=customer_book,
        )
        return lead, customer_book

    def test_customer_message_touches_customer_record(self):
        lead, customer_book = self._lead()
        lead.handle_customer_message("628111", "Halo, mau tanya harga print")
        entry = customer_book.get_customer("628111")
        self.assertIsNotNone(entry)
        self.assertEqual(entry.total_contacts, 1)
        self.assertEqual(entry.display_name, "")

    def test_repeated_messages_increment_total_contacts(self):
        lead, customer_book = self._lead()
        lead.handle_customer_message("628111", "Halo")
        lead.handle_customer_message("628111", "Masih ada?")
        entry = customer_book.get_customer("628111")
        self.assertEqual(entry.total_contacts, 2)

    def test_works_without_customer_book_configured(self):
        from app.approval_gate import ApprovalGate
        from app.trust_layer import TrustLayer

        lead = LeadAgent(trust_layer=TrustLayer(self.db), approval_gate=ApprovalGate(self.db))
        reply = lead.handle_customer_message("628111", "Halo")
        self.assertIsNotNone(reply)


if __name__ == "__main__":
    unittest.main()
