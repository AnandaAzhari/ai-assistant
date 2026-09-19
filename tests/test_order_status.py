import tempfile
import unittest
from pathlib import Path

from app.lead import LeadAgent
from app.order_status import OrderStatusStore


class OrderStatusStoreTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.db = Path(self.temp.name) / "assistant.db"
        self.store = OrderStatusStore(self.db)

    def test_set_and_get_latest_for_customer(self):
        self.store.set_status("ORD-001", "628111", "Sedang dicetak", updated_by="admin:telegram")
        entry = self.store.get_latest_for_customer("628111")
        self.assertEqual(entry.order_id, "ORD-001")
        self.assertEqual(entry.status_text, "Sedang dicetak")

    def test_customer_never_sees_another_customers_order(self):
        # Isolasi antar pelanggan (policies/security_policy.md) — pelanggan 628222
        # tidak boleh pernah melihat order milik 628111 lewat method mana pun.
        self.store.set_status("ORD-001", "628111", "Sedang dicetak", updated_by="admin:telegram")
        self.assertIsNone(self.store.get_latest_for_customer("628222"))
        self.assertEqual(self.store.list_for_customer("628222"), [])

    def test_get_latest_returns_none_when_no_order_recorded(self):
        self.assertIsNone(self.store.get_latest_for_customer("628999"))

    def test_list_for_customer_returns_most_recent_first(self):
        self.store.set_status("ORD-001", "628111", "Diterima", updated_by="admin:telegram")
        self.store.set_status("ORD-002", "628111", "Sedang dicetak", updated_by="admin:telegram")
        entries = self.store.list_for_customer("628111")
        self.assertEqual([entry.order_id for entry in entries], ["ORD-002", "ORD-001"])

    def test_updating_same_order_id_overwrites_status(self):
        self.store.set_status("ORD-001", "628111", "Diterima", updated_by="admin:telegram")
        self.store.set_status("ORD-001", "628111", "Selesai, siap diambil", updated_by="admin:telegram")
        entries = self.store.list_for_customer("628111")
        self.assertEqual(len(entries), 1)
        self.assertEqual(entries[0].status_text, "Selesai, siap diambil")

    def test_empty_fields_are_rejected(self):
        with self.assertRaises(ValueError):
            self.store.set_status("", "628111", "Diterima", updated_by="admin:telegram")
        with self.assertRaises(ValueError):
            self.store.set_status("ORD-001", "", "Diterima", updated_by="admin:telegram")
        with self.assertRaises(ValueError):
            self.store.set_status("ORD-001", "628111", "", updated_by="admin:telegram")
        with self.assertRaises(ValueError):
            self.store.set_status("ORD-001", "628111", "Diterima", updated_by="")

    def test_remove_deletes_order(self):
        self.store.set_status("ORD-001", "628111", "Diterima", updated_by="admin:telegram")
        self.assertTrue(self.store.remove("ORD-001"))
        self.assertIsNone(self.store.get_latest_for_customer("628111"))


class LeadAgentOrderStatusAdminCommandTests(unittest.TestCase):
    """Command admin (app/lead.py handle_admin_message) untuk mencatat status order."""

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.db = Path(self.temp.name) / "assistant.db"
        self.order_status = OrderStatusStore(self.db)
        self.lead = LeadAgent(admin_channel="telegram", order_status=self.order_status)

    def test_without_order_status_configured_reports_unavailable(self):
        lead = LeadAgent(admin_channel="telegram")
        reply = lead.handle_admin_message("/status_set 628111 ORD-001 | Sedang dicetak")
        self.assertEqual(reply.status, "belum_dikonfigurasi")

    def test_status_set_saves_entry(self):
        reply = self.lead.handle_admin_message("/status_set 628111 ORD-001 | Sedang dicetak")
        self.assertEqual(reply.status, "berhasil")
        entry = self.order_status.get_latest_for_customer("628111")
        self.assertEqual(entry.order_id, "ORD-001")
        self.assertEqual(entry.status_text, "Sedang dicetak")

    def test_status_set_without_pipe_separator_reports_format_error(self):
        reply = self.lead.handle_admin_message("/status_set 628111 ORD-001 Sedang dicetak")
        self.assertEqual(reply.status, "format_salah")
        self.assertIsNone(self.order_status.get_latest_for_customer("628111"))

    def test_status_lihat_shows_customer_history(self):
        self.lead.handle_admin_message("/status_set 628111 ORD-001 | Diterima")
        reply = self.lead.handle_admin_message("/status_lihat 628111")
        self.assertIn("ORD-001", reply.text)
        self.assertIn("Diterima", reply.text)


class HandleCustomerMessageOrderStatusTests(unittest.TestCase):
    """handle_customer_message() menjawab dari status order asli milik pengirim SAJA
    — lihat app/lead.py `_augment_reply_with_real_data` dan isolasi antar pelanggan."""

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.db = Path(self.temp.name) / "assistant.db"

    def _lead(self):
        from app.approval_gate import ApprovalGate
        from app.trust_layer import TrustLayer

        order_status = OrderStatusStore(self.db)
        lead = LeadAgent(
            trust_layer=TrustLayer(self.db), approval_gate=ApprovalGate(self.db), order_status=order_status,
        )
        return lead, order_status

    def test_status_question_answered_from_real_order_status(self):
        lead, order_status = self._lead()
        order_status.set_status("ORD-001", "628111", "Sedang dicetak, estimasi besok", updated_by="admin:telegram")
        reply = lead.handle_customer_message("628111", "Kak, pesanan saya sudah sampai mana ya?")
        self.assertEqual(reply.target, "kirim_status_antrean")
        self.assertIn("ORD-001", reply.text)
        self.assertIn("Sedang dicetak, estimasi besok", reply.text)

    def test_status_question_never_leaks_another_customers_order(self):
        lead, order_status = self._lead()
        order_status.set_status("ORD-001", "628111", "Sedang dicetak", updated_by="admin:telegram")
        reply = lead.handle_customer_message("628222", "Kak, pesanan saya sudah sampai mana ya?")
        self.assertEqual(reply.target, "kirim_status_antrean")
        self.assertNotIn("ORD-001", reply.text)
        self.assertIn("admin", reply.text.casefold())


if __name__ == "__main__":
    unittest.main()
