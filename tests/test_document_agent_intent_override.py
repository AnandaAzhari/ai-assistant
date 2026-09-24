"""Regresi untuk bug "setuju" yang salah dibaca AI (branch `fix-nara-intent-override`).

Ditemukan lewat tes live di Telegram: setelah kerangka makalah diajukan (data
MakalahBrief SUDAH lengkap), admin membalas "setuju" -- AI intake interpreter
(`app/document_intake.py`) salah mengklasifikasikan intent-nya (bukan
approve/continue) dan membuat balasan sendiri yang ngawur ("...saya masih
menunggu data jenjang...") padahal data itu sudah lengkap sejak awal.

`DocumentAgent._deterministic_gate_intent` (app/document_agent.py) adalah
backstop-nya: kalau pesan COCOK PERSIS salah satu frasa tegas yang sudah lama
dikenal aman (`_outline_approved`/`_wants_research`/`_wants_final_file` --
semuanya menolak pesan bernegasi/revisi/tanda tanya), intent itu WAJIB menang
di atas apa pun hasil AI, dan balasan buatan AI yang salah baca itu dibuang,
tidak pernah ditampilkan ke pengguna.

Tes di sini SENGAJA mensimulasikan AI yang salah (FakeMisreadingProvider)
untuk membuktikan backstop-nya benar-benar menang, dan sebaliknya membuktikan
AI tetap yang memutuskan untuk pesan yang TIDAK cocok persis (revisi asli,
pertanyaan asli)."""

import json
import unittest

from app.document_agent import DocumentAgent
from app.providers.base import ModelReply


class FakeMisreadingProvider:
    """Selalu balas dengan schema percakapan baru (intent explisit), dengan intent
    dan reply/clarification yang BISA diatur test -- meniru AI yang salah baca."""

    configured = True
    provider_name = "FakeAI"
    model_name = "fake-model"

    def __init__(self, *, intent: str, reply: str = "", clarification: str = "",
                 intent_evidence: str = ""):
        self.intent = intent
        self.reply = reply
        self.clarification = clarification
        self.intent_evidence = intent_evidence
        self.calls: list[list[dict[str, str]]] = []

    def generate(self, messages, *, max_tokens=1200, temperature=0.4, timeout=45):
        self.calls.append(messages)
        payload = {
            "brief": {}, "cover": {}, "evidence": {},
            "intent": self.intent, "intent_evidence": self.intent_evidence,
            "reply": self.reply, "clarification": self.clarification,
        }
        return ModelReply(
            "berhasil", json.dumps(payload), self.provider_name, self.model_name, 40, 20,
        )


def _complete_brief_agent(provider) -> DocumentAgent:
    """Agent dengan MakalahBrief + cover SUDAH lengkap dan kerangka SUDAH diajukan --
    persis kondisi live di Telegram saat bug "setuju" ditemukan (fase
    outline_confirmation, menunggu persetujuan)."""
    agent = DocumentAgent(provider)
    agent.brief.apply_ai_values({
        "institution_level": "SMK", "class_semester": "XII Semester 2",
        "subject": "Fisika", "topic_title": "Energi Terbarukan", "target_length": "8 halaman",
    })
    agent._outline_text = "## Kerangka Makalah\nBAB I\nBAB II\nBAB III\nDAFTAR PUSTAKA"
    agent.phase = "outline_confirmation"
    return agent


class DeterministicGateOverrideTests(unittest.TestCase):
    def test_ai_misreading_setuju_as_unclear_is_overridden_to_approve(self):
        provider = FakeMisreadingProvider(
            intent="unclear",
            clarification=(
                "Maksud 'setuju' ini untuk bagian yang mana ya? Saat ini saya masih "
                "menunggu data jenjang (mis. SMA/SMK/kuliah), kelas dan/atau semester, "
                "serta mata pelajaran atau mata kuliah."
            ),
        )
        agent = _complete_brief_agent(provider)
        result = agent.handle("setuju")

        # Backstop deterministik menang: fase maju (bukan macet di outline_confirmation
        # dengan pertanyaan ngawur), dan teks salah baca AI itu TIDAK PERNAH tampil.
        self.assertNotEqual(result.status, "needs_clarification")
        self.assertNotIn("masih menunggu data jenjang", result.text)
        self.assertNotEqual(agent.phase, "outline_confirmation")

    def test_ai_misreading_setuju_as_question_is_overridden_to_approve(self):
        provider = FakeMisreadingProvider(
            intent="question",
            reply="Bagian mana yang dimaksud dengan setuju?",
        )
        agent = _complete_brief_agent(provider)
        result = agent.handle("setuju")

        self.assertNotEqual(result.status, "answered")
        self.assertNotIn("Bagian mana yang dimaksud", result.text)
        self.assertNotEqual(agent.phase, "outline_confirmation")

    def test_overridden_approve_actually_advances_to_cover_phase(self):
        # Bukti positif, bukan cuma "tidak menampilkan teks salah": begitu di-override
        # ke approve, alur normal fase outline_confirmation -> cover harus benar jalan.
        provider = FakeMisreadingProvider(intent="unclear", clarification="Maksudnya apa ya?")
        agent = _complete_brief_agent(provider)
        result = agent.handle("setuju")
        self.assertEqual(agent.phase, "cover")
        self.assertEqual(result.status, "needs_cover")

    def test_lanjutkan_in_ready_for_draft_is_overridden_to_continue(self):
        provider = FakeMisreadingProvider(intent="unclear", clarification="Maksudnya lanjut apa ya?")
        agent = _complete_brief_agent(provider)
        agent.cover.assignment_type = "individu"
        agent.cover.author_name = "Siswa Uji"
        agent.phase = "ready_for_draft"

        result = agent.handle("lanjutkan")

        # _research_and_draft() ikut terpanggil (bukan macet di klarifikasi ngawur) --
        # research/registry belum di-setup di tes ini jadi hasilnya gagal riset, tapi
        # yang penting alurnya BENAR masuk ke sana, bukan berhenti di "unclear".
        self.assertNotIn("Maksudnya lanjut apa ya?", result.text)
        self.assertNotEqual(result.status, "needs_clarification")

    def test_lanjutkan_in_draft_ready_is_overridden_to_continue(self):
        provider = FakeMisreadingProvider(intent="unclear", clarification="Lanjut ke mana maksudnya?")
        agent = _complete_brief_agent(provider)
        agent.phase = "draft_ready"
        agent._draft_spec = object()  # cukup untuk lolos guard fase awal build_final()

        result = agent.handle("lanjutkan")

        self.assertNotIn("Lanjut ke mana maksudnya?", result.text)
        # build_final() tetap butuh citation_engine/registry -- di tes ini belum ada,
        # jadi hasilnya "belum_dikonfigurasi", TAPI itu bukti alurnya sampai ke
        # build_final() (bukan berhenti di klarifikasi ngawur "unclear").
        self.assertEqual(result.status, "belum_dikonfigurasi")


class AiIntentStillWinsForAmbiguousMessagesTests(unittest.TestCase):
    """Pastikan backstop-nya SEMPIT: hanya menang untuk frasa tegas yang sudah lama
    dikenal aman -- pesan revisi/pertanyaan asli tetap sepenuhnya diputuskan AI,
    tidak ikut ter-override."""

    def test_real_revision_request_is_not_overridden(self):
        provider = FakeMisreadingProvider(
            intent="revise", intent_evidence="fokuskan ke energi surya saja",
            reply="",
        )
        agent = _complete_brief_agent(provider)
        result = agent.handle("Tolong fokuskan ke energi surya saja")
        # "fokuskan" ada di daftar kata negasi/revisi _outline_approved -> TIDAK cocok
        # deterministik -> intent AI ("revise") tetap dipakai apa adanya, jadi TIDAK
        # ikut di-approve/maju ke fase cover begitu saja.
        self.assertNotEqual(agent.phase, "cover")

    def test_real_question_with_question_mark_is_not_overridden(self):
        provider = FakeMisreadingProvider(
            intent="question", reply="Bab II itu wajib ada berapa sub-bab ya?",
        )
        agent = _complete_brief_agent(provider)
        result = agent.handle("Bab II itu wajib ada berapa sub-bab?")
        # Tanda tanya membuat _outline_approved menolak cocok -> tidak di-override ->
        # balasan AI yang sesungguhnya (bukan hasil paksaan) yang tampil.
        self.assertEqual(result.status, "answered")
        self.assertIn("Bab II itu wajib ada berapa sub-bab ya?", result.text)
        self.assertEqual(agent.phase, "outline_confirmation")

    def test_ai_approve_intent_matching_deterministic_result_is_unaffected(self):
        # Kasus normal (AI benar membaca "setuju" sebagai approve) tidak berubah sama
        # sekali oleh perubahan ini -- no-op murni.
        provider = FakeMisreadingProvider(intent="approve", intent_evidence="setuju")
        agent = _complete_brief_agent(provider)
        result = agent.handle("setuju")
        self.assertEqual(agent.phase, "cover")
        self.assertEqual(result.status, "needs_cover")


if __name__ == "__main__":
    unittest.main()
