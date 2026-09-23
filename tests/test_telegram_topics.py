"""Fitur topik grup Telegram ("Taqi AI — Ruang Admin"): topik 🧠 Lead Agent,
📁 Nara, 💰 Laras dipetakan ke agent masing-masing lewat `AdminIdentity.topic_agents`
(app/telegram.py). Lihat juga tests/test_telegram.py dan tests/test_telegram_integration.py
untuk perilaku chat pribadi yang TIDAK BOLEH berubah sama sekali oleh fitur ini.

Lima kebutuhan yang diuji di sini (persis permintaan owner):
1. Topik terhubung ke agent masing-masing (agent_hint diteruskan ke LeadAgent).
2. Balasan tetap masuk ke topik asal (message_thread_id diteruskan balik).
3. Perintah admin dibatasi hanya akun Telegram owner (is_authorized, sama di grup
   maupun chat pribadi).
4. Riwayat percakapan tiap topik terpisah (DocumentAgent tersendiri untuk topik Nara,
   tidak bercampur dengan topik lain/chat pribadi).
5. Fungsi chat pribadi bot yang sudah berjalan tetap dipertahankan (regresi nol —
   dicek lagi di sini dengan skenario campuran grup+pribadi, bukan cuma diasumsikan
   dari test_telegram.py/test_telegram_integration.py yang sudah ada)."""

import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock

from app.dp_policy import DpPolicyStore
from app.lead import LeadAgent, LeadReply
from app.pricing import PricingConfigStore
from app.telegram import AdminIdentity, TelegramAdminAdapter
from app.telegram_store import TelegramUpdateStore

GROUP_CHAT_ID = -1001234567890
LEAD_THREAD, NARA_THREAD, LARAS_THREAD, UNKNOWN_THREAD = 10, 20, 30, 999
OWNER_ID = 12345


def topic_identity(**overrides):
    kwargs = dict(
        user_id=OWNER_ID, chat_id=67890, group_chat_id=GROUP_CHAT_ID,
        topic_agents={LEAD_THREAD: "lead", NARA_THREAD: "document", LARAS_THREAD: "finance"},
    )
    kwargs.update(overrides)
    return AdminIdentity(**kwargs)


def group_message(*, user=OWNER_ID, thread_id=NARA_THREAD, text="halo", chat_id=GROUP_CHAT_ID, update_id=1):
    message = {"from": {"id": user}, "chat": {"id": chat_id, "type": "supergroup"}, "text": text}
    if thread_id is not None:
        message["message_thread_id"] = thread_id
    return {"update_id": update_id, "message": message}


def private_message(*, user=OWNER_ID, chat_id=67890, text="/status", update_id=1):
    return {"update_id": update_id, "message": {"from": {"id": user}, "chat": {"id": chat_id, "type": "private"}, "text": text}}


class Client:
    def __init__(self):
        self.sent = []
        self.thread_ids = []
        self.batches = []

    def send_message(self, chat_id, text, *, message_thread_id=None):
        self.sent.append((chat_id, text))
        self.thread_ids.append(message_thread_id)

    def get_updates(self, *, offset=None, timeout=30):
        if not self.batches:
            raise KeyboardInterrupt
        return self.batches.pop(0)


class AdminIdentityTopicTests(unittest.TestCase):
    def test_agent_for_topic_maps_known_threads(self):
        identity = topic_identity()
        self.assertEqual(identity.agent_for_topic(LEAD_THREAD), "lead")
        self.assertEqual(identity.agent_for_topic(NARA_THREAD), "document")
        self.assertEqual(identity.agent_for_topic(LARAS_THREAD), "finance")

    def test_agent_for_topic_is_none_for_unknown_or_missing_thread(self):
        identity = topic_identity()
        self.assertIsNone(identity.agent_for_topic(UNKNOWN_THREAD))
        self.assertIsNone(identity.agent_for_topic(None))

    def test_default_identity_has_no_group_or_topics_configured(self):
        identity = AdminIdentity(OWNER_ID)
        self.assertIsNone(identity.group_chat_id)
        self.assertEqual(identity.topic_agents, {})
        self.assertIsNone(identity.agent_for_topic(NARA_THREAD))

    def test_group_chat_id_allows_negative_numbers(self):
        identity = AdminIdentity(OWNER_ID, group_chat_id=-100123)
        self.assertEqual(identity.group_chat_id, -100123)

    def test_group_chat_id_must_be_an_integer(self):
        with self.assertRaises(ValueError):
            AdminIdentity(OWNER_ID, group_chat_id="not-a-number")


class AuthorizationTests(unittest.TestCase):
    def setUp(self):
        self.client = Client()
        self.handler = Mock(return_value=LeadReply("lead", "berhasil", "Selesai"))
        self.adapter = TelegramAdminAdapter(self.client, topic_identity(), self.handler)

    def test_owner_in_known_topic_is_authorized(self):
        self.assertTrue(self.adapter.process_update(group_message(thread_id=NARA_THREAD)))
        self.handler.assert_called_once()

    def test_owner_in_unmapped_topic_including_general_is_ignored(self):
        for thread_id in (UNKNOWN_THREAD, None):
            with self.subTest(thread_id=thread_id):
                self.handler.reset_mock()
                self.assertFalse(self.adapter.process_update(group_message(thread_id=thread_id, update_id=thread_id or 1)))
                self.handler.assert_not_called()

    def test_other_user_in_group_is_never_authorized_even_in_known_topic(self):
        self.assertFalse(self.adapter.process_update(group_message(user=999)))
        self.handler.assert_not_called()
        self.assertEqual(self.client.sent, [])

    def test_wrong_group_chat_id_is_rejected(self):
        self.assertFalse(self.adapter.process_update(group_message(chat_id=-1)))
        self.handler.assert_not_called()

    def test_group_without_group_chat_id_configured_is_never_authorized(self):
        adapter = TelegramAdminAdapter(self.client, AdminIdentity(OWNER_ID, chat_id=67890), self.handler)
        self.assertFalse(adapter.process_update(group_message()))
        self.handler.assert_not_called()

    def test_private_chat_still_works_exactly_as_before(self):
        self.assertTrue(self.adapter.process_update(private_message()))
        self.handler.assert_called_once_with("/status", agent_hint=None)


class ReplyRoutingTests(unittest.TestCase):
    def setUp(self):
        self.client = Client()
        self.handler = Mock(return_value=LeadReply("document", "berhasil", "Makalah dicatat"))
        self.adapter = TelegramAdminAdapter(self.client, topic_identity(), self.handler)

    def test_reply_to_group_topic_is_threaded_back(self):
        self.adapter.process_update(group_message(thread_id=NARA_THREAD))
        self.assertEqual(self.client.sent, [(GROUP_CHAT_ID, "Makalah dicatat")])
        self.assertEqual(self.client.thread_ids, [NARA_THREAD])
        self.handler.assert_called_once_with("halo", agent_hint="document")

    def test_reply_to_private_chat_never_carries_a_thread_id(self):
        self.adapter.process_update(private_message(text="/bantuan"))
        self.assertEqual(self.client.thread_ids, [None])

    def test_lead_agent_topic_passes_no_special_hint(self):
        self.adapter.process_update(group_message(thread_id=LEAD_THREAD, text="/status"))
        self.handler.assert_called_once_with("/status", agent_hint="lead")

    def test_laras_topic_hints_finance(self):
        self.adapter.process_update(group_message(thread_id=LARAS_THREAD, text="saldo berapa"))
        self.handler.assert_called_once_with("saldo berapa", agent_hint="finance")


class DurablePendingAcrossTopicsTests(unittest.TestCase):
    """flush_pending harus menjangkau pesan tertunda dari chat pribadi MAUPUN grup —
    sebelum fitur topik ada, hanya chat pribadi yang dicek (lihat app/telegram.py)."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.store = TelegramUpdateStore(Path(self.tmp.name) / "telegram.db", 1)
        self.client = Client()
        self.handler = Mock(return_value=LeadReply("document", "berhasil", "Selesai"))
        self.adapter = TelegramAdminAdapter(self.client, topic_identity(), self.handler, store=self.store)

    def test_interrupted_group_topic_message_is_redelivered_to_correct_topic_on_restart(self):
        self.store.reserve(1, GROUP_CHAT_ID, NARA_THREAD)
        self.adapter.flush_pending()
        self.assertEqual(len(self.client.sent), 1)
        self.assertIn("terhenti", self.client.sent[0][1])
        self.assertEqual(self.client.thread_ids, [NARA_THREAD])


class TelegramUpdateStoreThreadIdTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.db = Path(self.tmp.name) / "assistant.db"

    def test_reserve_and_get_round_trip_thread_id(self):
        store = TelegramUpdateStore(self.db, 1)
        store.reserve(1, GROUP_CHAT_ID, NARA_THREAD)
        self.assertEqual(store.get(1)["thread_id"], NARA_THREAD)

    def test_thread_id_defaults_to_none_for_private_chat(self):
        store = TelegramUpdateStore(self.db, 1)
        store.reserve(1, 67890)
        self.assertIsNone(store.get(1)["thread_id"])

    def test_migration_adds_thread_id_column_to_pre_existing_database(self):
        import sqlite3
        self.db.parent.mkdir(parents=True, exist_ok=True)
        with sqlite3.connect(self.db) as db:
            db.execute('''CREATE TABLE telegram_updates (
                bot_id INTEGER NOT NULL, update_id INTEGER NOT NULL, chat_id INTEGER NOT NULL,
                state TEXT NOT NULL, reply TEXT NOT NULL DEFAULT '', sent_chunks INTEGER NOT NULL DEFAULT 0,
                PRIMARY KEY(bot_id, update_id))''')
            db.execute("INSERT INTO telegram_updates(bot_id,update_id,chat_id,state) VALUES(1,1,67890,'sent')")
        store = TelegramUpdateStore(self.db, 1)
        row = store.get(1)
        self.assertIsNone(row["thread_id"])
        self.assertEqual(row["state"], "sent")
        self.assertTrue(store.reserve(2, GROUP_CHAT_ID, NARA_THREAD))


class LeadAgentTopicHintRoutingTests(unittest.TestCase):
    """Level LeadAgent langsung (tanpa transport Telegram): agent_hint hanya
    mempengaruhi teks bebas yang ambigu — command/kata kunci eksplisit tidak
    pernah dibajak oleh hint topik (bisa tetap dipakai dari topik mana pun)."""

    def setUp(self):
        self.document = Mock()
        self.document.session_active = False
        self.document.handle.return_value = Mock(status="berhasil", text="Nara: dicatat")
        self.finance = Mock()
        self.finance.handle.return_value = Mock(status="berhasil", text="Laras: dicatat")
        self.lead = LeadAgent(document=self.document, finance=self.finance)

    def test_document_hint_routes_ambiguous_free_text_to_document(self):
        reply = self.lead.handle_admin_message("tolong bantu ya", agent_hint="document")
        self.assertEqual(reply.target, "document")
        self.document.handle.assert_called_once_with("tolong bantu ya")

    def test_finance_hint_routes_ambiguous_free_text_to_finance(self):
        reply = self.lead.handle_admin_message("tolong bantu ya", agent_hint="finance")
        self.assertEqual(reply.target, "finance")
        self.finance.handle.assert_called_once_with("tolong bantu ya")

    def test_lead_hint_behaves_exactly_like_no_hint(self):
        with_hint = self.lead.handle_admin_message("tolong bantu ya", agent_hint="lead")
        without_hint = self.lead.handle_admin_message("tolong bantu ya")
        self.assertEqual(with_hint.text, without_hint.text)
        self.document.handle.assert_not_called()
        self.finance.handle.assert_not_called()

    def test_explicit_finance_keyword_wins_over_document_hint(self):
        reply = self.lead.handle_admin_message("catat pengeluaran 50 ribu pakai BCA", agent_hint="document")
        self.assertEqual(reply.target, "finance")
        self.document.handle.assert_not_called()

    def test_slash_command_is_unaffected_by_hint_in_any_topic(self):
        for hint in (None, "lead", "document", "finance"):
            with self.subTest(hint=hint):
                self.document.handle.reset_mock()
                self.finance.handle.reset_mock()
                reply = self.lead.handle_admin_message("/status", agent_hint=hint)
                self.assertEqual(reply.target, "lead")
                self.document.handle.assert_not_called()
                self.finance.handle.assert_not_called()


class TopicDocumentIsolationTests(unittest.TestCase):
    """Kebutuhan #4: sesi Nara di topik itu tidak boleh bocor ke topik Lead Agent
    atau chat pribadi (agent_hint None), dan sebaliknya."""

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)

    def _document_agent(self, marker):
        agent = Mock()
        agent.session_active = False
        agent.handle.return_value = Mock(status="berhasil", text=f"balasan-{marker}")
        return agent

    def test_topic_document_factory_builds_a_separate_instance_for_nara(self):
        shared_document = self._document_agent("shared")
        built = {}

        def factory(topic_key):
            agent = self._document_agent(topic_key)
            built[topic_key] = agent
            return agent

        lead = LeadAgent(document=shared_document, topic_document_factory=factory)
        lead.handle_admin_message("susun dokumen tentang AI", agent_hint="document")
        self.assertIn("telegram-nara", built)
        built["telegram-nara"].handle.assert_called_once_with("susun dokumen tentang AI")
        shared_document.handle.assert_not_called()

    def test_lead_agent_topic_and_private_chat_keep_using_the_shared_instance(self):
        shared_document = self._document_agent("shared")
        lead = LeadAgent(document=shared_document, topic_document_factory=lambda key: self._document_agent(key))
        lead.handle_admin_message("susun dokumen tentang AI", agent_hint=None)
        shared_document.handle.assert_called_once_with("susun dokumen tentang AI")

    def test_active_nara_session_does_not_leak_into_lead_agent_topic_free_text(self):
        shared_document = self._document_agent("shared")
        shared_document.session_active = False
        nara_document = self._document_agent("nara")
        nara_document.session_active = True  # sesi susun makalah sedang berjalan di topik Nara

        lead = LeadAgent(document=shared_document, topic_document_factory=lambda key: nara_document)
        # Teks bebas ambigu di topik Lead Agent (agent_hint None) TIDAK boleh
        # jatuh ke sesi Nara yang sedang aktif di topik lain.
        reply = lead.handle_admin_message("halo apa kabar", agent_hint=None)
        nara_document.handle.assert_not_called()
        self.assertNotEqual(reply.target, "document")

    def test_without_topic_factory_nara_hint_falls_back_to_shared_document_agent(self):
        shared_document = self._document_agent("shared")
        lead = LeadAgent(document=shared_document)  # topic_document_factory belum diberikan
        lead.handle_admin_message("susun dokumen tentang AI", agent_hint="document")
        shared_document.handle.assert_called_once_with("susun dokumen tentang AI")


class RealDocumentIsolationIntegrationTests(unittest.TestCase):
    """Sama seperti TopicDocumentIsolationTests tapi memakai app.admin_runtime.create_admin_lead
    sungguhan (DocumentAgent + DocumentSessionStore nyata) — memastikan wiring
    topic_document_factory di app/admin_runtime.py benar-benar membuat sesi
    tersimpan terpisah di database, bukan cuma di memori."""

    def test_nara_topic_session_is_isolated_from_private_chat_session(self):
        import os
        from unittest.mock import patch
        from app.admin_runtime import create_admin_lead

        with tempfile.TemporaryDirectory() as tmp, patch.dict(os.environ, {
            "DATABASE_PATH": str(Path(tmp) / "assistant.db"), "DOCUMENT_WORKSPACE": str(Path(tmp) / "documents"),
            "DEEPSEEK_API_KEY": "", "GOOGLE_SHEETS_WEBHOOK_URL": "", "GOOGLE_SHEETS_SYNC_SECRET": "",
        }):
            lead = create_admin_lead(channel="telegram", document_scope="DOCSRC-TELEGRAM-topictest")
            lead.handle_admin_message("Saya mau makalah tentang Robotika, 6 halaman", agent_hint="document")
            self.assertIn("Robotika", lead._topic_documents["telegram-nara"].brief.topic_title)
            self.assertEqual(lead.document.brief.topic_title, "")


class DiscoverTopicsTests(unittest.TestCase):
    """--discover-topics (telegram_main.py): owner kirim kode pairing yang sama di
    tiap topik, program mencetak chat_id+thread_id supaya tinggal disalin ke .env."""

    def test_prints_chat_id_and_thread_id_for_each_topic_pairing_message(self):
        import io
        from contextlib import redirect_stdout
        from telegram_main import discover_topics

        client = Client()
        client.batches = [[
            {"update_id": 1, "message": group_message(thread_id=LEAD_THREAD, text="/hubungkan_topik CODE")["message"]},
            {"update_id": 2, "message": group_message(thread_id=NARA_THREAD, text="/hubungkan_topik CODE")["message"]},
            # kode salah -> diabaikan
            {"update_id": 3, "message": group_message(thread_id=LARAS_THREAD, text="/hubungkan_topik WRONG")["message"]},
        ]]
        with redirect_stdout(io.StringIO()) as out:
            self.assertEqual(discover_topics(client, challenge="CODE"), 0)
        output = out.getvalue()
        self.assertIn(f"TELEGRAM_ADMIN_GROUP_CHAT_ID={GROUP_CHAT_ID}", output)
        self.assertIn(f"thread_id={LEAD_THREAD}", output)
        self.assertIn(f"thread_id={NARA_THREAD}", output)
        self.assertNotIn(f"thread_id={LARAS_THREAD}", output)
        self.assertEqual(client.sent, [])

    def test_general_topic_message_has_no_thread_id_and_is_still_reported(self):
        import io
        from contextlib import redirect_stdout
        from telegram_main import discover_topics

        client = Client()
        client.batches = [[{"update_id": 1, "message": group_message(thread_id=None, text="/hubungkan_topik CODE")["message"]}]]
        with redirect_stdout(io.StringIO()) as out:
            discover_topics(client, challenge="CODE")
        self.assertIn("(topik General)", out.getvalue())


class OptionalSignedIntTests(unittest.TestCase):
    def test_accepts_negative_numbers_unlike_positive_int(self):
        from telegram_main import optional_signed_int
        self.assertEqual(optional_signed_int("X", "-1001234567890"), -1001234567890)
        self.assertEqual(optional_signed_int("X", "20"), 20)
        self.assertIsNone(optional_signed_int("X", ""))
        self.assertIsNone(optional_signed_int("X", None))

    def test_rejects_non_numeric_value(self):
        from telegram_main import optional_signed_int
        with self.assertRaises(ValueError):
            optional_signed_int("X", "abc")


if __name__ == "__main__":
    unittest.main()
