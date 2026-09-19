"""Fase 5: Evaluasi & Observability (`docs/roadmap_customer_channel_v1.md`).

Menguji bahwa Interaction Log tersambung dengan benar ke jalur pelanggan
(`LeadAgent.handle_customer_message`, agent "taqi"/"nara"), ke Content Studio
(`ContentStudio.generate_draft`, agent "kirana"), dan ke perintah admin
`/eval_sample`, `/eval_tandai`, `/eval_status`. `tests/test_interaction_log.py`
sudah menguji `InteractionLogStore` itu sendiri secara terisolasi.
"""
import json
import tempfile
import unittest
from pathlib import Path

from app.approval_gate import ApprovalGate
from app.brand_profile import BrandProfileStore
from app.content_studio import ContentStudio
from app.interaction_log import InteractionLogStore
from app.lead import LeadAgent
from app.providers.base import ModelReply
from app.trust_layer import TrustLayer


class FakeProvider:
    def __init__(self, reply: ModelReply, *, configured: bool = True):
        self._reply = reply
        self._configured = configured

    @property
    def configured(self) -> bool:
        return self._configured

    @property
    def provider_name(self) -> str:
        return "Fake"

    @property
    def model_name(self) -> str:
        return "fake-model"

    def generate(self, messages, *, max_tokens=1200, temperature=0.7, timeout=45):
        return self._reply


class CustomerMessageInteractionLogTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.db = Path(self.temp.name) / "assistant.db"
        self.interaction_log = InteractionLogStore(self.db)
        self.lead = LeadAgent(
            trust_layer=TrustLayer(self.db), approval_gate=ApprovalGate(self.db),
            interaction_log=self.interaction_log,
        )

    def test_customer_reply_is_logged_as_taqi(self):
        self.lead.handle_customer_message("628111", "Halo kak, mau tanya-tanya jasa cetak")
        entries = self.interaction_log.sample_for_review("taqi")
        self.assertEqual(len(entries), 1)
        self.assertEqual(entries[0].scope, "628111")
        self.assertEqual(entries[0].channel, "whatsapp")

    def test_logging_does_not_change_the_reply(self):
        without_log = LeadAgent(trust_layer=TrustLayer(self.db), approval_gate=ApprovalGate(self.db))
        reply_a = without_log.handle_customer_message("628222", "Kak, harga cetak skripsi berapa?")
        reply_b = self.lead.handle_customer_message("628222", "Kak, harga cetak skripsi berapa?")
        self.assertEqual(reply_a.status, reply_b.status)
        self.assertEqual(reply_a.target, reply_b.target)

    def test_no_logging_happens_when_interaction_log_not_configured(self):
        lead = LeadAgent(trust_layer=TrustLayer(self.db), approval_gate=ApprovalGate(self.db))
        lead.handle_customer_message("628333", "Halo")
        self.assertEqual(self.interaction_log.sample_for_review("taqi"), [])


class LeadAgentEvalAdminCommandTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.db = Path(self.temp.name) / "assistant.db"
        self.interaction_log = InteractionLogStore(self.db)
        self.lead = LeadAgent(admin_channel="telegram", interaction_log=self.interaction_log)

    def test_without_interaction_log_configured_reports_unavailable(self):
        lead = LeadAgent(admin_channel="telegram")
        self.assertEqual(lead.handle_admin_message("/eval_sample").status, "belum_dikonfigurasi")
        self.assertEqual(lead.handle_admin_message("/eval_status").status, "belum_dikonfigurasi")

    def test_eval_sample_shows_unreviewed_entries(self):
        entry = self.interaction_log.log("nara", "628111", "whatsapp", "Bantu buat makalah", "Boleh, jenjang apa?")
        reply = self.lead.handle_admin_message("/eval_sample nara")
        self.assertEqual(reply.status, "berhasil")
        self.assertIn(entry.id, reply.text)

    def test_eval_sample_with_no_entries_reports_empty(self):
        reply = self.lead.handle_admin_message("/eval_sample")
        self.assertEqual(reply.status, "berhasil")
        self.assertIn("Tidak ada", reply.text)

    def test_eval_tandai_marks_entry_reviewed(self):
        entry = self.interaction_log.log("nara", "628111", "whatsapp", "pesan", "balasan")
        reply = self.lead.handle_admin_message(f"/eval_tandai {entry.id} | baik | jawaban jelas dan ramah")
        self.assertEqual(reply.status, "berhasil")
        updated = self.interaction_log.get(entry.id)
        self.assertTrue(updated.reviewed)
        self.assertEqual(updated.review_label, "baik")
        self.assertEqual(updated.review_note, "jawaban jelas dan ramah")

    def test_eval_tandai_with_invalid_label_reports_format_error(self):
        entry = self.interaction_log.log("nara", "628111", "whatsapp", "pesan", "balasan")
        reply = self.lead.handle_admin_message(f"/eval_tandai {entry.id} | luar_biasa")
        self.assertEqual(reply.status, "format_salah")

    def test_eval_tandai_unknown_id_reports_format_error(self):
        reply = self.lead.handle_admin_message("/eval_tandai tidak-ada | baik")
        self.assertEqual(reply.status, "format_salah")

    def test_eval_status_reports_summary(self):
        e1 = self.interaction_log.log("nara", "1", "whatsapp", "a", "b")
        self.interaction_log.mark_reviewed(e1.id, "baik")
        self.interaction_log.log("nara", "2", "whatsapp", "a", "b")
        reply = self.lead.handle_admin_message("/eval_status nara")
        self.assertEqual(reply.status, "berhasil")
        self.assertIn("Total interaksi: 2", reply.text)
        self.assertIn("Sudah ditinjau: 1", reply.text)


class ContentStudioInteractionLogTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        root = Path(self.temp.name)
        brand_root = root / "brand_profiles"
        brand_root.mkdir()
        (brand_root / "risol_mamqi.md").write_text("""## Usaha
Risol Mamqi

## Tone of Voice
Ceria dan menggugah selera.

## Larangan Tema/Kata
- Tidak mengklaim manfaat kesehatan.
""", encoding="utf-8")
        self.interaction_log = InteractionLogStore(root / "assistant.db")
        provider = FakeProvider(ModelReply("berhasil", json.dumps({"captions": ["Risol anget nih!"]}), "Fake", "fake-model"))
        self.studio = ContentStudio(
            provider, brand_profiles=BrandProfileStore(brand_root), interaction_log=self.interaction_log,
        )

    def test_successful_draft_is_logged_as_kirana(self):
        self.studio.generate_draft("Risol Mamqi", "instagram", "promo weekend")
        entries = self.interaction_log.sample_for_review("kirana")
        self.assertEqual(len(entries), 1)
        self.assertIn("Risol anget nih!", entries[0].output_text)
        self.assertEqual(entries[0].status, "draft")


if __name__ == "__main__":
    unittest.main()
