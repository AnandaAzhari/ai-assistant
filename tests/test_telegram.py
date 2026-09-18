import unittest

from app.lead import LeadAgent, LeadReply
from app.telegram import AdminIdentity, TelegramAdminAdapter


class FakeClient:
    def __init__(self):
        self.sent = []

    def send_message(self, chat_id, text):
        self.sent.append((chat_id, text))


class TelegramAdminTests(unittest.TestCase):
    def setUp(self):
        self.client = FakeClient()
        self.lead = LeadAgent()
        self.adapter = TelegramAdminAdapter(
            self.client,
            AdminIdentity(user_id=12345, chat_id=67890),
            self.lead.handle_admin_message,
        )

    def update(self, *, user=12345, chat=67890, text="/status"):
        return {
            "update_id": 1,
            "message": {
                "from": {"id": user},
                "chat": {"id": chat, "type": "private"},
                "text": text,
            },
        }

    def test_owner_status_is_processed(self):
        self.assertTrue(self.adapter.process_update(self.update()))
        self.assertEqual(self.client.sent[0][0], 67890)
        self.assertIn("Lead Agent: aktif", self.client.sent[0][1])

    def test_unknown_user_is_silently_ignored(self):
        self.assertFalse(self.adapter.process_update(self.update(user=999)))
        self.assertEqual(self.client.sent, [])

    def test_wrong_chat_is_ignored(self):
        self.assertFalse(self.adapter.process_update(self.update(chat=111)))
        self.assertEqual(self.client.sent, [])

    def test_finance_language_routes_without_writing_data(self):
        reply = self.lead.handle_admin_message("Catat pengeluaran 80 ribu beli tinta pakai BCA")
        self.assertEqual(reply.target, "finance")
        self.assertEqual(reply.status, "terdeteksi")
        self.assertIn("belum diaktifkan", reply.text)

    def test_taqidesk_language_routes_to_docutech(self):
        reply = self.lead.handle_admin_message("Tampilkan antrean TaqiDesk")
        self.assertEqual(reply.target, "docutech")

    def test_non_text_update_explains_text_only_support(self):
        update = {"update_id": 2, "message": {"from": {"id": 12345}, "chat": {"id": 67890, "type": "private"}, "photo": []}}
        self.assertTrue(self.adapter.process_update(update))
        self.assertIn("pesan teks", self.client.sent[0][1])

    def test_handler_contract(self):
        reply = self.lead.handle_admin_message("/bantuan")
        self.assertIsInstance(reply, LeadReply)
        self.assertIn("/status", reply.text)


if __name__ == "__main__":
    unittest.main()

