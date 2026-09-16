"""Document/Makalah Agent v0.8.

Requirement dasar dan data cover dikumpulkan secara lokal tanpa token AI.
DeepSeek dipakai hanya untuk pekerjaan bernalar seperti menyusun/revisi outline.
Research Manager mencari metadata sumber akademik nyata tanpa token model AI.
Formatting DOCX/PDF tetap ditangani Document Engine lokal.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from app.document_cover import MakalahCoverData
from app.document_engine import DocumentEngine, demo_spec
from app.document_requirements import MakalahRequirements
from app.providers.base import ModelProvider
from app.research_manager import ResearchManager


OUTLINE_PROMPT = """Kamu adalah Document/Makalah Agent Taqi DocuTech.
Requirement makalah sudah divalidasi oleh sistem.

Tugasmu pada tahap ini HANYA membuat ringkasan singkat dan outline makalah.
Aturan:
- gunakan bahasa Indonesia yang jelas dan ringkas;
- jangan gunakan tabel Markdown karena UI admin belum merender tabel dengan baik;
- ringkasan requirement cukup berupa bullet singkat;
- patuhi instruksi guru/dosen di atas template standar;
- jangan mengarang sumber atau daftar pustaka;
- struktur default: Halaman Awal, BAB I PENDAHULUAN, BAB II PEMBAHASAN, BAB III PENUTUP, dan Daftar Pustaka bila sumber tersedia;
- buat subbab bernomor yang relevan, tetapi jangan terlalu banyak;
- JANGAN meminta data cover pada jawaban ini; data cover akan dikumpulkan sistem lokal setelah outline disetujui;
- JANGAN membuat draft panjang;
- akhiri dengan kalimat: `Jika outline ini sudah sesuai, balas: setuju.`
"""


@dataclass(frozen=True)
class DocumentResult:
    status: str
    text: str


class DocumentAgent:
    def __init__(
        self,
        provider: ModelProvider,
        *,
        engine: DocumentEngine | None = None,
        research: ResearchManager | None = None,
        history_limit: int = 10,
    ):
        self.provider = provider
        self.engine = engine
        self.research = research or ResearchManager.from_env()
        self.history_limit = max(2, int(history_limit))
        self._history: list[dict[str, str]] = []
        self.requirements = MakalahRequirements()
        self.cover = MakalahCoverData()
        self.phase = "requirements"

    @property
    def configured(self) -> bool:
        return bool(self.provider and self.provider.configured)

    @property
    def engine_ready(self) -> bool:
        return self.engine is not None

    @property
    def model_label(self) -> str:
        if not self.provider:
            return "belum tersedia"
        return f"{self.provider.provider_name} / {self.provider.model_name}"

    @property
    def session_active(self) -> bool:
        if self.phase != "requirements":
            return True
        labels = getattr(self.requirements, "FIELD_LABELS", {})
        return any(bool(getattr(self.requirements, key, "")) for key in labels)

    def status(self) -> DocumentResult:
        engine_note = "Document Engine: siap" if self.engine_ready else "Document Engine: belum tersedia"
        research_note = self.research.status_text if self.research else "Research Manager: belum tersedia"
        if not self.configured:
            return DocumentResult(
                "belum_dikonfigurasi",
                "Document Agent tersedia. Requirement dan data cover diproses lokal, tetapi DeepSeek API belum dikonfigurasi. "
                "Isi DEEPSEEK_API_KEY pada .env lokal lalu restart Web Admin.\n"
                + engine_note + "\n" + research_note,
            )
        return DocumentResult(
            "siap",
            f"Document Agent: siap memakai {self.model_label}.\n{engine_note}.\n{research_note}\n"
            "Requirement + data cover diproses lokal tanpa token AI; model dipakai untuk outline/draft saja.",
        )

    def engine_status(self) -> DocumentResult:
        if not self.engine_ready:
            return DocumentResult("belum_dikonfigurasi", "Document Engine belum tersedia pada runtime ini.")
        return DocumentResult("siap", self.engine.status_text)

    def research_status(self) -> DocumentResult:
        if not self.research:
            return DocumentResult("belum_dikonfigurasi", "Research Manager belum tersedia pada runtime ini.")
        return DocumentResult("siap", self.research.status_text)

    def research_search(self, raw: str) -> DocumentResult:
        if not self.research:
            return DocumentResult("belum_dikonfigurasi", "Research Manager belum tersedia pada runtime ini.")
        parts = raw.split(maxsplit=1)
        query = parts[1].strip() if len(parts) > 1 else ""
        if not query:
            query = (self.requirements.topic_title or "").strip()
        if not query:
            return DocumentResult(
                "membutuhkan_bantuan",
                "Tulis topik setelah perintah, misalnya: `/research pencemaran lingkungan`, atau mulai sesi makalah dahulu.",
            )
        result = self.research.search(query, limit=10)
        return DocumentResult(result.status, self.research.format_result(result))

    def build_demo(self) -> DocumentResult:
        if not self.engine_ready:
            return DocumentResult("belum_dikonfigurasi", "Document Engine belum tersedia pada runtime ini.")
        result = self.engine.build(demo_spec(), create_pdf=True)
        if result.status != "berhasil":
            return DocumentResult("gagal", result.warning or "Document Engine gagal membuat file demo.")

        lines = [
            "Document Engine berhasil membuat file demo tanpa memakai token AI.",
            f"DOCX: `{result.docx_path}`",
        ]
        if result.pdf_path:
            lines.append(f"PDF: `{result.pdf_path}`")
        else:
            lines.append("PDF: belum dibuat otomatis.")
        if result.warning:
            lines.append(f"Catatan: {result.warning}")
        return DocumentResult("berhasil", "\n".join(lines))

    def reset(self) -> DocumentResult:
        self._history.clear()
        self.requirements.reset()
        self.cover.reset()
        self.phase = "requirements"
        return DocumentResult(
            "berhasil",
            "Sesi Document Agent direset. Silakan mulai permintaan dokumen baru. "
            "Requirement awal akan dikumpulkan secara lokal tanpa token AI.",
        )

    @staticmethod
    def _usage_note(reply) -> str:
        if not (reply.input_tokens or reply.output_tokens):
            return ""
        return (
            f"\n\n[Model: {reply.model} | token masuk: {reply.input_tokens:,} | "
            f"token keluar: {reply.output_tokens:,}]"
        ).replace(",", ".")

    def _outline_messages(self, raw: str, *, revision: bool = False) -> list[dict[str, str]]:
        messages = [{"role": "system", "content": OUTLINE_PROMPT}]
        messages.append({
            "role": "system",
            "content": "REQUIREMENT MAKALAH TERVALIDASI:\n" + self.requirements.structured_text(),
        })
        if revision:
            messages.extend(self._history[-self.history_limit:])
            messages.append({"role": "user", "content": "Revisi outline sesuai permintaan ini:\n" + raw[:4000]})
        else:
            messages.append({"role": "user", "content": "Buat ringkasan requirement dan outline makalah sekarang."})
        return messages

    def _generate_outline(self, raw: str, *, revision: bool = False) -> DocumentResult:
        if not self.configured:
            return self.status()
        reply = self.provider.generate(
            self._outline_messages(raw, revision=revision),
            max_tokens=850,
            temperature=0.3,
            timeout=45,
        )
        if reply.status != "berhasil":
            return DocumentResult(reply.status, reply.text)

        if revision:
            self._history.append({"role": "user", "content": raw[:4000]})
        self._history.append({"role": "assistant", "content": reply.text[:10000]})
        self._history = self._history[-self.history_limit:]
        self.phase = "outline_confirmation"
        return DocumentResult("berhasil", reply.text + self._usage_note(reply))

    @staticmethod
    def _outline_approved(raw: str) -> bool:
        text = re.sub(r"\s+", " ", raw.strip().casefold())
        if "tidak setuju" in text or "belum sesuai" in text:
            return False
        return text in {"setuju", "sesuai", "lanjut", "oke", "ok", "ya", "iya"} or text.startswith(
            ("setuju ", "sudah sesuai", "outline sudah sesuai")
        )

    def handle(self, message: str) -> DocumentResult:
        raw = (message or "").strip()
        if not raw:
            return DocumentResult("membutuhkan_bantuan", "Pesan dokumen kosong.")

        text = raw.casefold()
        command = text.split(maxsplit=1)[0]
        if command in {"/dokumen_baru", "/makalah_baru"}:
            return self.reset()
        if command == "/dokumen_engine_status":
            return self.engine_status()
        if command == "/dokumen_demo":
            return self.build_demo()
        if command in {"/research_status", "/riset_status"}:
            return self.research_status()
        if command in {"/research", "/riset"}:
            return self.research_search(raw)

        if self.phase == "requirements":
            self.requirements.update(raw)
            if not self.requirements.complete:
                return DocumentResult("needs_requirements", self.requirements.question_text())
            return self._generate_outline(raw)

        if self.phase == "outline_confirmation":
            if self._outline_approved(raw):
                self.phase = "cover"
                self.cover.update(raw)
                return DocumentResult("needs_cover", self.cover.question_text())
            return self._generate_outline(raw, revision=True)

        if self.phase == "cover":
            self.cover.update(raw)
            if not self.cover.complete:
                return DocumentResult("needs_cover", self.cover.question_text())
            self.phase = "ready_for_draft"
            return DocumentResult(
                "cover_complete",
                "Data cover utama sudah lengkap dan tersimpan lokal tanpa token AI.\n\n"
                + self.cover.structured_text()
                + "\n\nTahap berikutnya adalah pembuatan draft makalah dan penyambungan hasilnya ke DOCX/PDF.",
            )

        if self.phase == "ready_for_draft":
            self.cover.update(raw)
            return DocumentResult(
                "ready_for_draft",
                "Requirement dan data cover sudah siap. Tahap berikutnya adalah generator draft + DOCX/PDF; "
                "kita belum memanggil model lagi pada pesan ini.",
            )

        return DocumentResult("membutuhkan_bantuan", "Status sesi dokumen tidak dikenali. Gunakan /makalah_baru untuk memulai ulang.")
