"""Perintah /cari_riwayat (Lead Agent mencari lintas Nara/Kirana/Laras sekaligus).

Lihat app/lead.py (_search_history, _label_document_scope, _label_content_scope)
dan app/document_session.py / app/content_session.py / app/finance.py (masing-masing
method `search`). Dipicu oleh permintaan Ananda supaya sesi makalah yang sedang
berjalan di topik Nara tidak menghalangi dia bertanya bebas di topik lain, dan
supaya Lead Agent tetap bisa "menjadi otak" yang mencari data dari agen lain kalau
diminta lewat command eksplisit.
"""
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

from app.content_session import ContentSessionStore
from app.document_session import DocumentSessionStore
from app.finance import FinanceService
from app.lead import LeadAgent


class LabelHelpersTests(unittest.TestCase):
    def test_label_document_scope_for_nara_topic(self):
        label = LeadAgent._label_document_scope("DOCSRC-TELEGRAM-bot1-1-1-TOPIC-telegram-nara")
        self.assertEqual(label, "Nara (topik Telegram)")

    def test_label_document_scope_for_shared_scope(self):
        label = LeadAgent._label_document_scope("DOCSRC-TELEGRAM-bot1-1-1")
        self.assertEqual(label, "Nara (chat pribadi / topik Lead Agent / topik Laras)")

    def test_label_document_scope_for_whatsapp_customer(self):
        label = LeadAgent._label_document_scope("DOCSRC-WHATSAPP-6281234567890")
        self.assertEqual(label, "Nara (pelanggan WhatsApp 6281234567890)")

    def test_label_content_scope(self):
        label = LeadAgent._label_content_scope("risol_mamqi:instagram:content-1")
        self.assertEqual(label, "Kirana (risol_mamqi/instagram)")

    def test_label_content_scope_falls_back_when_unrecognized(self):
        self.assertEqual(LeadAgent._label_content_scope(""), "Kirana (Content Studio)")


class SearchHistoryCommandTests(unittest.TestCase):
    """Unit-level: memakai store asli (SQLite sungguhan di tmp dir) tapi document/
    content_studio berupa stand-in ringan (cukup atribut yang dipakai _search_history),
    supaya tidak perlu menyalakan AI provider/engine sungguhan."""

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        db = Path(self.temp.name) / "assistant.db"
        self.doc_store = DocumentSessionStore(db)
        self.content_store = ContentSessionStore(db)
        self.finance = FinanceService(db)

    def _lead(self, *, with_document=True, with_content=True, with_finance=True):
        document = SimpleNamespace(session_store=self.doc_store) if with_document else None
        content_studio = SimpleNamespace(content_session=self.content_store) if with_content else None
        finance = self.finance if with_finance else None
        return LeadAgent(document=document, content_studio=content_studio, finance=finance)

    def test_requires_keyword_when_missing(self):
        lead = self._lead()
        reply = lead.handle_admin_message("/cari_riwayat")
        self.assertEqual(reply.status, "membutuhkan_bantuan")
        self.assertIn("/cari_riwayat", reply.text)

    def test_requires_keyword_when_only_whitespace(self):
        lead = self._lead()
        reply = lead.handle_admin_message("/cari_riwayat    ")
        self.assertEqual(reply.status, "membutuhkan_bantuan")

    def test_no_agents_configured_at_all(self):
        lead = LeadAgent()
        reply = lead.handle_admin_message("/cari_riwayat kopi")
        self.assertEqual(reply.status, "belum_dikonfigurasi")

    def test_finds_document_session_hit(self):
        self.doc_store.save("DOCSRC-TELEGRAM-x-TOPIC-telegram-nara", {
            "version": 1, "phase": "outline_confirmation",
            "brief": {"subject": "Kewirausahaan", "topic_title": "Proposal usaha kopi keliling"},
        })
        lead = self._lead()
        reply = lead.handle_admin_message("/cari_riwayat kopi keliling")
        self.assertEqual(reply.target, "lead")
        self.assertEqual(reply.status, "berhasil")
        self.assertIn("Nara/dokumen", reply.text)
        self.assertIn("Nara (topik Telegram)", reply.text)
        self.assertIn("Proposal usaha kopi keliling", reply.text)

    def test_finds_content_session_hit(self):
        scope = self.content_store.build_scope("risol_mamqi", "instagram", "content-1")
        self.content_store.save(scope, {"version": 1, "caption": "Promo risol pedas minggu ini"})
        lead = self._lead()
        reply = lead.handle_admin_message("/cari_riwayat risol pedas")
        self.assertIn("Kirana/konten", reply.text)
        self.assertIn("Kirana (risol_mamqi/instagram)", reply.text)
        self.assertIn("Promo risol pedas minggu ini", reply.text)

    def test_finds_finance_hit(self):
        self.finance.record(
            kind="expense", amount=80000, account="BCA", business="Taqi Desk",
            category="Perlengkapan", description="Beli tinta printer",
        )
        lead = self._lead()
        reply = lead.handle_admin_message("/cari_riwayat tinta printer")
        self.assertIn("Laras/keuangan", reply.text)
        self.assertIn("Rp80.000", reply.text)
        self.assertIn("Beli tinta printer", reply.text)

    def test_combines_all_three_sections_when_all_configured(self):
        self.doc_store.save("DOCSRC-ADMIN-DEFAULT", {
            "version": 1, "phase": "requirements",
            "brief": {"subject": "-", "topic_title": "Riset pasar kopi"},
        })
        scope = self.content_store.build_scope("risol_mamqi", "instagram", "content-2")
        self.content_store.save(scope, {"version": 1, "caption": "Giveaway kopi susu"})
        self.finance.record(
            kind="income", amount=50000, account="Cash", business="Risol Mamqi",
            category="Penjualan", description="Jual kopi susu kemasan",
        )
        lead = self._lead()
        reply = lead.handle_admin_message("/cari_riwayat kopi")
        self.assertIn("Nara/dokumen", reply.text)
        self.assertIn("Kirana/konten", reply.text)
        self.assertIn("Laras/keuangan", reply.text)

    def test_shows_no_match_per_section_when_nothing_found(self):
        lead = self._lead()
        reply = lead.handle_admin_message("/cari_riwayat topik-yang-tidak-pernah-ada")
        self.assertEqual(reply.status, "berhasil")
        self.assertIn("(tidak ada yang cocok)", reply.text)

    def test_skips_section_for_unconfigured_agent(self):
        lead = self._lead(with_content=False)
        reply = lead.handle_admin_message("/cari_riwayat apa saja")
        self.assertNotIn("Kirana/konten", reply.text)

    def test_command_works_from_any_topic_hint(self):
        self.finance.record(
            kind="expense", amount=15000, account="Cash", business="Personal",
            category="Lain-lain", description="Beli pulsa",
        )
        lead = self._lead()
        for hint in (None, "lead", "document", "finance"):
            reply = lead.handle_admin_message("/cari_riwayat pulsa", agent_hint=hint)
            self.assertIn("Beli pulsa", reply.text, msg=f"gagal untuk agent_hint={hint!r}")


class RealCrossTopicSearchIntegrationTests(unittest.TestCase):
    """Memakai app.admin_runtime.create_admin_lead sungguhan (sama seperti
    RealDocumentIsolationIntegrationTests di tests/test_telegram_topics.py):
    memastikan sesi makalah yang dimulai di topik Nara tetap bisa ditemukan dari
    /cari_riwayat yang dikirim dari topik Lead Agent — bukan cuma isolasi satu arah."""

    def test_search_from_lead_agent_topic_finds_session_started_in_nara_topic(self):
        import os
        from unittest.mock import patch
        from app.admin_runtime import create_admin_lead

        with tempfile.TemporaryDirectory() as tmp, patch.dict(os.environ, {
            "DATABASE_PATH": str(Path(tmp) / "assistant.db"), "DOCUMENT_WORKSPACE": str(Path(tmp) / "documents"),
            "DEEPSEEK_API_KEY": "", "GOOGLE_SHEETS_WEBHOOK_URL": "", "GOOGLE_SHEETS_SYNC_SECRET": "",
        }):
            lead = create_admin_lead(channel="telegram", document_scope="DOCSRC-TELEGRAM-searchtest")
            lead.handle_admin_message("Saya mau makalah tentang Robotika, 6 halaman", agent_hint="document")

            reply = lead.handle_admin_message("/cari_riwayat Robotika", agent_hint="lead")
            self.assertIn("Nara (topik Telegram)", reply.text)
            self.assertIn("Robotika", reply.text)


if __name__ == "__main__":
    unittest.main()
