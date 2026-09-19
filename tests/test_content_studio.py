import json
import tempfile
import unittest
from pathlib import Path

from app.brand_profile import BrandProfileStore
from app.content_learning import ContentLearningStore
from app.content_session import ContentSessionStore
from app.content_studio import ContentStudio
from app.lead import LeadAgent
from app.providers.base import ModelReply


class FakeProvider:
    def __init__(self, reply: ModelReply, *, configured: bool = True):
        self._reply = reply
        self._configured = configured
        self.calls: list[list[dict[str, str]]] = []

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
        self.calls.append(messages)
        return self._reply


def _reply(payload: dict, *, status: str = "berhasil") -> ModelReply:
    return ModelReply(status, json.dumps(payload), "Fake", "fake-model", 10, 5)


class ContentStudioTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        root = Path(self.temp.name)
        self.brand_root = root / "brand_profiles"
        self.brand_root.mkdir()
        (self.brand_root / "risol_mamqi.md").write_text("""## Usaha
Risol Mamqi

## Deskripsi Singkat
Usaha kuliner rumahan.

## Tone of Voice
Ceria dan menggugah selera.

## Target Audiens
Warga sekitar.

## Larangan Tema/Kata
- Tidak mengklaim manfaat kesehatan.

## Contoh Caption Favorit
- Risol anget nih!
""", encoding="utf-8")
        self.brand_profiles = BrandProfileStore(self.brand_root)
        self.content_learning = ContentLearningStore(root / "assistant.db")
        self.content_session = ContentSessionStore(root / "assistant.db")

    def _studio(self, provider) -> ContentStudio:
        return ContentStudio(
            provider, brand_profiles=self.brand_profiles,
            content_learning=self.content_learning, content_session=self.content_session,
        )

    def test_unconfigured_provider_returns_not_configured_without_calling_it(self):
        provider = FakeProvider(_reply({"captions": ["a"]}), configured=False)
        studio = self._studio(provider)
        result = studio.generate_draft("Risol Mamqi", "instagram", "promo weekend")
        self.assertEqual(result.status, "belum_dikonfigurasi")
        self.assertEqual(provider.calls, [])

    def test_none_provider_is_treated_as_not_configured(self):
        studio = self._studio(None)
        self.assertFalse(studio.configured)
        result = studio.generate_draft("Risol Mamqi", "instagram", "promo weekend")
        self.assertEqual(result.status, "belum_dikonfigurasi")

    def test_missing_business_or_platform_returns_format_error(self):
        studio = self._studio(FakeProvider(_reply({"captions": ["a"]})))
        self.assertEqual(studio.generate_draft("", "instagram", "brief").status, "format_salah")
        self.assertEqual(studio.generate_draft("Risol Mamqi", "", "brief").status, "format_salah")

    def test_empty_brief_returns_format_error(self):
        studio = self._studio(FakeProvider(_reply({"captions": ["a"]})))
        result = studio.generate_draft("Risol Mamqi", "instagram", "   ")
        self.assertEqual(result.status, "format_salah")

    def test_brand_profile_not_ready_returns_needs_review(self):
        studio = self._studio(FakeProvider(_reply({"captions": ["a"]})))
        result = studio.generate_draft("Usaha Belum Terdaftar", "instagram", "promo weekend")
        self.assertEqual(result.status, "needs_review")
        self.assertIn("belum lengkap", result.note)

    def test_successful_generation_returns_draft_and_saves_working_memory(self):
        provider = FakeProvider(_reply({"captions": ["Risol anget, isian melimpah!", "Ngemil sore makin seru."]}))
        studio = self._studio(provider)
        result = studio.generate_draft("Risol Mamqi", "instagram", "promo risol sore ini")
        self.assertEqual(result.status, "draft")
        self.assertEqual(len(result.captions), 2)
        self.assertTrue(result.content_id)
        loaded = self.content_session.load(result.scope)
        self.assertEqual(loaded["stage"], "draft")
        self.assertEqual(loaded["captions"], list(result.captions))

    def test_invalid_json_returns_gagal(self):
        provider = FakeProvider(ModelReply("berhasil", "bukan json", "Fake", "fake-model"))
        studio = self._studio(provider)
        result = studio.generate_draft("Risol Mamqi", "instagram", "promo weekend")
        self.assertEqual(result.status, "gagal")

    def test_provider_failure_status_is_passed_through(self):
        provider = FakeProvider(ModelReply("timeout", "", "Fake", "fake-model"))
        studio = self._studio(provider)
        result = studio.generate_draft("Risol Mamqi", "instagram", "promo weekend")
        self.assertEqual(result.status, "timeout")

    def test_caption_with_price_not_in_brief_is_filtered_out(self):
        provider = FakeProvider(_reply({"captions": ["Cuma Rp5000 aja, order sekarang!"]}))
        studio = self._studio(provider)
        result = studio.generate_draft("Risol Mamqi", "instagram", "promo risol tanpa sebut harga")
        self.assertEqual(result.status, "needs_review")
        self.assertIn("harga", result.note)

    def test_caption_with_price_present_in_brief_is_allowed(self):
        provider = FakeProvider(_reply({"captions": ["Promo spesial cuma Rp5000, buruan order!"]}))
        studio = self._studio(provider)
        result = studio.generate_draft("Risol Mamqi", "instagram", "Promo risol Rp5000 khusus weekend ini")
        self.assertEqual(result.status, "draft")
        self.assertEqual(len(result.captions), 1)

    def test_partial_price_filtering_keeps_safe_alternatives_and_notes_dropped_count(self):
        provider = FakeProvider(_reply({
            "captions": ["Risol anget, order sekarang!", "Cuma Rp99999, buruan!"],
        }))
        studio = self._studio(provider)
        result = studio.generate_draft("Risol Mamqi", "instagram", "promo risol tanpa sebut harga")
        self.assertEqual(result.status, "draft")
        self.assertEqual(result.captions, ("Risol anget, order sekarang!",))
        self.assertIn("1 alternatif dibuang", result.note)

    def test_recurring_feedback_patterns_are_injected_into_prompt(self):
        for _ in range(2):
            self.content_learning.record_feedback(
                "Risol Mamqi", "instagram", "edited", "cta", note="owner selalu minta CTA order langsung",
            )
        provider = FakeProvider(_reply({"captions": ["Order sekarang, ya!"]}))
        studio = self._studio(provider)
        studio.generate_draft("Risol Mamqi", "instagram", "promo weekend")
        system_prompt = provider.calls[0][0]["content"]
        self.assertIn("owner selalu minta CTA order langsung", system_prompt)

    def test_content_id_defaults_to_generated_value_when_not_given(self):
        provider = FakeProvider(_reply({"captions": ["Risol anget nih!"]}))
        studio = self._studio(provider)
        result = studio.generate_draft("Risol Mamqi", "instagram", "promo weekend")
        self.assertTrue(result.content_id)

    def test_explicit_content_id_is_used_for_scope(self):
        provider = FakeProvider(_reply({"captions": ["Risol anget nih!"]}))
        studio = self._studio(provider)
        result = studio.generate_draft("Risol Mamqi", "instagram", "promo weekend", content_id="content-42")
        self.assertEqual(result.content_id, "content-42")
        self.assertEqual(result.scope, "Risol Mamqi:instagram:content-42")


class LeadAgentContentStudioAdminCommandTests(unittest.TestCase):
    """Command admin (`app/lead.py` `handle_admin_message`) untuk Content Studio."""

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        root = Path(self.temp.name)
        self.brand_root = root / "brand_profiles"
        self.brand_root.mkdir()
        (self.brand_root / "risol_mamqi.md").write_text("""## Usaha
Risol Mamqi

## Tone of Voice
Ceria dan menggugah selera.

## Larangan Tema/Kata
- Tidak mengklaim manfaat kesehatan.
""", encoding="utf-8")
        self.brand_profiles = BrandProfileStore(self.brand_root)
        self.db = root / "assistant.db"

    def _lead(self, provider) -> LeadAgent:
        content_studio = ContentStudio(
            provider, brand_profiles=self.brand_profiles,
            content_learning=ContentLearningStore(self.db), content_session=ContentSessionStore(self.db),
        )
        return LeadAgent(admin_channel="telegram", content_studio=content_studio)

    def test_without_content_studio_configured_reports_unavailable(self):
        lead = LeadAgent(admin_channel="telegram")
        reply = lead.handle_admin_message("/konten_baru Risol Mamqi | instagram | promo weekend")
        self.assertEqual(reply.status, "belum_dikonfigurasi")

    def test_konten_baru_without_pipe_separator_reports_format_error(self):
        lead = self._lead(FakeProvider(_reply({"captions": ["a"]})))
        reply = lead.handle_admin_message("/konten_baru Risol Mamqi instagram promo weekend")
        self.assertEqual(reply.status, "format_salah")

    def test_konten_baru_returns_draft_captions(self):
        provider = FakeProvider(_reply({"captions": ["Risol anget nih, order sekarang!"]}))
        lead = self._lead(provider)
        reply = lead.handle_admin_message("/konten_baru Risol Mamqi | instagram | promo risol sore ini")
        self.assertEqual(reply.status, "berhasil")
        self.assertIn("Risol anget nih, order sekarang!", reply.text)
        self.assertIn("draft", reply.text.casefold())

    def test_konten_baru_with_unready_brand_profile_reports_needs_review(self):
        provider = FakeProvider(_reply({"captions": ["a"]}))
        lead = self._lead(provider)
        reply = lead.handle_admin_message("/konten_baru Pixiva.ID | instagram | promo weekend")
        self.assertEqual(reply.status, "needs_review")


if __name__ == "__main__":
    unittest.main()
