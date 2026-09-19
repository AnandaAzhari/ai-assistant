import unittest

from app.document_agent import DocumentAgent
from app.lead import LeadAgent
from app.providers.base import ModelReply


class FakeProvider:
    """AI generik yang selalu menjawab dengan teks bebas (bukan JSON).

    Dipakai untuk menguji bahwa parser lokal (`apply_local_fallback`) tetap bekerja
    saat interpretasi AI gagal/tidak valid, dan bahwa MakalahBrief yang sudah
    terkumpul ikut dikirim sebagai konteks pada pemanggilan provider berikutnya.
    """

    configured = True
    provider_name = "FakeAI"
    model_name = "fake-model"

    def __init__(self):
        self.calls = []

    def generate(self, messages, *, max_tokens=1200, temperature=0.4, timeout=45):
        self.calls.append(messages)
        return ModelReply(
            "berhasil",
            "Baik. Berapa halaman dan apakah ada format khusus dari guru?",
            self.provider_name,
            self.model_name,
            120,
            18,
        )


class UnconfiguredProvider(FakeProvider):
    configured = False


class BriefCompletingProvider(FakeProvider):
    """Simulasikan AI yang berhasil mengisi data inti MakalahBrief pada intake pertama,
    lalu membuat kerangka makalah pada pemanggilan berikutnya.

    `topic_title` sengaja dibiarkan null: parser lokal deterministik di
    `app/document_requirements.py` yang mengisinya dari kalimat pelanggan
    (mis. `makalah tentang <topik>`), sesuai desain AI-first dengan fallback lokal
    di `app/document_agent.py`.
    """

    def generate(self, messages, *, max_tokens=1200, temperature=0.4, timeout=45):
        self.calls.append(messages)
        if len(self.calls) == 1:
            return ModelReply(
                "berhasil",
                '{"institution_level": "SMP", "class_semester": "Kelas 8", '
                '"subject": "IPA", "topic_title": null, "target_length": "8-12 halaman"}',
                self.provider_name, self.model_name, 80, 40,
            )
        return ModelReply(
            "berhasil",
            "## Kerangka Makalah\nBAB I Pendahuluan\nBAB II Pembahasan\nBAB III Penutup",
            self.provider_name, self.model_name, 120, 180,
        )


class DocumentAgentTests(unittest.TestCase):
    def test_document_agent_calls_provider(self):
        provider = BriefCompletingProvider()
        agent = DocumentAgent(provider)
        result = agent.handle("Saya mau membuat makalah tentang pencemaran lingkungan untuk kelas 8")
        self.assertEqual(result.status, "berhasil")
        # 1 panggilan untuk memahami pesan (intake), 1 lagi untuk membuat kerangka.
        self.assertEqual(len(provider.calls), 2)
        self.assertIn("Kerangka Makalah", result.text)

    def test_context_is_kept_for_admin_session(self):
        provider = FakeProvider()
        agent = DocumentAgent(provider)
        agent.handle("Saya mau membuat makalah tentang pencemaran lingkungan")
        agent.handle("Untuk kelas 8 dan sekitar 10 halaman")
        second_messages = provider.calls[1]
        self.assertTrue(any(
            item.get("role") == "user" and "pencemaran lingkungan" in item.get("content", "")
            for item in second_messages
        ))

    def test_unconfigured_provider_does_not_call_api(self):
        provider = UnconfiguredProvider()
        agent = DocumentAgent(provider)
        # Data inti lengkap lewat parser lokal saja (tanpa AI), supaya alur benar-benar
        # sampai ke tahap yang butuh provider (pembuatan kerangka) dan baru di situ
        # status "belum_dikonfigurasi" muncul.
        result = agent.handle(
            "Saya SMK kelas XII semester 2, mata pelajaran Informatika, "
            "mau bikin makalah tentang AI Agent, jumlah 8 halaman"
        )
        self.assertEqual(result.status, "belum_dikonfigurasi")
        self.assertEqual(provider.calls, [])

    def test_lead_routes_makalah_to_document_agent(self):
        provider = BriefCompletingProvider()
        document = DocumentAgent(provider)
        lead = LeadAgent(document=document)
        reply = lead.handle_admin_message("Saya mau membuat makalah tentang sampah plastik")
        self.assertEqual(reply.target, "document")
        self.assertEqual(reply.status, "berhasil")
        self.assertEqual(len(provider.calls), 2)

    def test_final_paths_are_empty_until_document_is_actually_finalized(self):
        # Properti ini dipakai pemanggil eksternal (LeadAgent/whatsapp_main.py) untuk
        # tahu kapan ada file sungguhan yang perlu dikirim ke pelanggan — harus kosong
        # selama dokumen belum sampai fase final_ready (lihat app/lead.py
        # `_continue_customer_document`).
        provider = FakeProvider()
        agent = DocumentAgent(provider)
        self.assertEqual(agent.final_docx_path, "")
        self.assertEqual(agent.final_pdf_path, "")
        agent.handle("Saya mau membuat makalah tentang pencemaran lingkungan")
        self.assertEqual(agent.final_docx_path, "")
        self.assertEqual(agent.final_pdf_path, "")

    def test_reset_clears_document_context(self):
        provider = FakeProvider()
        document = DocumentAgent(provider)
        document.handle("Makalah pertama")
        result = document.reset()
        self.assertEqual(result.status, "berhasil")
        self.assertEqual(document._history, [])


class DocumentAgentTopicRestrictionTests(unittest.TestCase):
    """Topic restriction lintas-agent (guardrail bersama `app/topic_guard.py`) untuk
    pertanyaan di luar topik yang muncul DI TENGAH sesi dokumen — menutup gap di
    `eval/scenarios/nara.md` Skenario 7 dengan guardrail kode, bukan cuma persona AI."""

    def test_off_topic_message_is_redirected_without_calling_provider(self):
        provider = FakeProvider()
        agent = DocumentAgent(provider)
        agent.handle("Saya mau membuat makalah tentang fotosintesis untuk kelas 8")
        calls_before = len(provider.calls)
        result = agent.handle("Eh iya kak, sekalian tanya, kalau print foto buat photobooth bisa juga gak di sini?")
        self.assertEqual(result.status, "di_luar_topik")
        self.assertNotIn("photobooth", result.text.casefold())
        # Backstop deterministik: AI sama sekali tidak dipanggil untuk pesan ini.
        self.assertEqual(len(provider.calls), calls_before)

    def test_off_topic_message_does_not_change_brief_or_phase(self):
        provider = FakeProvider()
        agent = DocumentAgent(provider)
        agent.handle("Saya mau membuat makalah tentang fotosintesis untuk kelas 8")
        phase_before = agent.phase
        brief_before = agent.brief.structured_text()
        agent.handle("Btw ada servis laptop juga gak di sini?")
        self.assertEqual(agent.phase, phase_before)
        self.assertEqual(agent.brief.structured_text(), brief_before)

    def test_document_session_continues_normally_after_redirect(self):
        provider = FakeProvider()
        agent = DocumentAgent(provider)
        agent.handle("Saya mau membuat makalah tentang fotosintesis untuk kelas 8")
        agent.handle("Ada servis komputer juga gak?")
        calls_before = len(provider.calls)
        agent.handle("Oke lanjut aja, targetnya 10 halaman")
        # Pesan berikutnya yang relevan tetap diproses AI seperti biasa (guardrail
        # tidak "menyangkut" sesi ke status di_luar_topik selamanya).
        self.assertGreater(len(provider.calls), calls_before)

    def test_off_topic_check_does_not_block_slash_commands(self):
        provider = FakeProvider()
        agent = DocumentAgent(provider)
        result = agent.handle("/dokumen_engine_status")
        self.assertNotEqual(result.status, "di_luar_topik")


if __name__ == "__main__":
    unittest.main()
