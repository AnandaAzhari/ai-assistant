"""Document/Makalah Agent v1.0.

Requirement dasar dan data cover dikumpulkan lokal tanpa token AI.
DeepSeek dipakai untuk outline dan, hanya setelah perintah eksplisit /draft, membuat
draft terstruktur yang memakai marker sumber R1/R2/... dari Source Registry.
"""

from __future__ import annotations

import os
import re
from dataclasses import dataclass

from app.document_cover import MakalahCoverData
from app.document_draft import DraftGenerator
from app.document_engine import DocumentEngine, MakalahSpec, demo_spec
from app.document_requirements import MakalahRequirements
from app.providers.base import ModelProvider
from app.research_manager import ResearchManager, ResearchResult
from app.source_registry import SourceRegistry


OUTLINE_PROMPT = """Kamu adalah Document/Makalah Agent Taqi DocuTech.
Requirement makalah sudah divalidasi oleh sistem.

Tugasmu pada tahap ini HANYA membuat ringkasan singkat dan outline makalah.
Aturan:
- gunakan bahasa Indonesia yang jelas dan ringkas;
- jangan gunakan tabel Markdown;
- ringkasan requirement cukup berupa bullet singkat;
- patuhi instruksi guru/dosen di atas template standar;
- jangan mengarang sumber atau daftar pustaka;
- struktur default: Halaman Awal, BAB I PENDAHULUAN, BAB II PEMBAHASAN, BAB III PENUTUP, dan Daftar Pustaka bila sumber tersedia;
- buat subbab bernomor yang relevan, tetapi jangan terlalu banyak;
- JANGAN meminta data cover pada jawaban ini; data cover dikumpulkan sistem lokal setelah outline disetujui;
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
        registry: SourceRegistry | None = None,
        history_limit: int = 10,
    ):
        self.provider = provider
        self.engine = engine
        self.research = research or ResearchManager.from_env()
        self.registry = registry or SourceRegistry.from_env()
        self.draft_generator = DraftGenerator(provider)
        self.history_limit = max(2, int(history_limit))
        self._history: list[dict[str, str]] = []
        self._last_research: ResearchResult | None = None
        self._outline_text = ""
        self._draft_spec: MakalahSpec | None = None
        self.requirements = MakalahRequirements()
        self.cover = MakalahCoverData()
        self.phase = "requirements"
        self.source_scope = os.environ.get("DOCUMENT_SOURCE_SCOPE", "DOCSRC-ADMIN-DEFAULT").strip() or "DOCSRC-ADMIN-DEFAULT"

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

    @property
    def draft_spec(self) -> MakalahSpec | None:
        return self._draft_spec

    def status(self) -> DocumentResult:
        engine_note = "Document Engine: siap" if self.engine_ready else "Document Engine: belum tersedia"
        research_note = self.research.status_text if self.research else "Research Manager: belum tersedia"
        registry_note = "Source Registry: siap (SQLite)" if self.registry else "Source Registry: belum tersedia"
        draft_note = "Draft Generator: siap" if self.configured else "Draft Generator: menunggu provider AI"
        if not self.configured:
            return DocumentResult(
                "belum_dikonfigurasi",
                "Document Agent tersedia. Requirement dan data cover diproses lokal, tetapi DeepSeek API belum dikonfigurasi.\n"
                + engine_note + "\n" + research_note + "\n" + registry_note + "\n" + draft_note,
            )
        return DocumentResult(
            "siap",
            f"Document Agent: siap memakai {self.model_label}.\n{engine_note}.\n{research_note}\n{registry_note}\n{draft_note}.\n"
            "Requirement + data cover diproses lokal tanpa token AI; model dipakai untuk outline/draft saja.",
        )

    def engine_status(self) -> DocumentResult:
        if not self.engine_ready:
            return DocumentResult("belum_dikonfigurasi", "Document Engine belum tersedia pada runtime ini.")
        return DocumentResult("siap", self.engine.status_text)

    def research_status(self) -> DocumentResult:
        if not self.research:
            return DocumentResult("belum_dikonfigurasi", "Research Manager belum tersedia pada runtime ini.")
        registry = "Source Registry siap." if self.registry else "Source Registry belum tersedia."
        return DocumentResult("siap", self.research.status_text + " " + registry)

    def research_search(self, raw: str) -> DocumentResult:
        if not self.research:
            return DocumentResult("belum_dikonfigurasi", "Research Manager belum tersedia pada runtime ini.")
        parts = raw.split(maxsplit=1)
        query = parts[1].strip() if len(parts) > 1 else ""
        if not query:
            query = (self.requirements.topic_title or "").strip()
        if not query:
            return DocumentResult("membutuhkan_bantuan", "Tulis topik setelah perintah, misalnya: `/research pencemaran lingkungan`.")
        result = self.research.search(query, limit=10)
        if result.status == "berhasil":
            self._last_research = result
        return DocumentResult(result.status, self.research.format_result(result))

    @staticmethod
    def _parse_source_selection(value: str, total: int) -> list[int]:
        text = (value or "").strip().casefold()
        if not text or text in {"all", "semua"}:
            return list(range(1, total + 1))
        selected: set[int] = set()
        for chunk in re.split(r"[,;\s]+", text):
            chunk = chunk.strip()
            if not chunk:
                continue
            range_match = re.fullmatch(r"(\d+)\s*[-–]\s*(\d+)", chunk)
            if range_match:
                start, end = int(range_match.group(1)), int(range_match.group(2))
                if start > end:
                    start, end = end, start
                selected.update(range(start, end + 1))
            elif chunk.isdigit():
                selected.add(int(chunk))
        return sorted(index for index in selected if 1 <= index <= total)

    def research_save(self, raw: str) -> DocumentResult:
        if not self.registry:
            return DocumentResult("belum_dikonfigurasi", "Source Registry belum tersedia.")
        if not self._last_research or self._last_research.status != "berhasil":
            return DocumentResult("membutuhkan_bantuan", "Belum ada hasil research. Jalankan `/research <topik>` terlebih dahulu.")
        parts = raw.split(maxsplit=1)
        selection_text = parts[1] if len(parts) > 1 else "all"
        indices = self._parse_source_selection(selection_text, len(self._last_research.sources))
        if not indices:
            return DocumentResult("membutuhkan_bantuan", "Contoh: `/research_save all` atau `/research_save 1,2,4-6`.")
        chosen = [self._last_research.sources[index - 1] for index in indices]
        added = self.registry.add_sources(self.source_scope, chosen)
        current = self.registry.list_sources(self.source_scope)
        if not added:
            return DocumentResult("berhasil", "Pilihan itu sudah ada di Source Registry.\n\n" + self.registry.format_sources(current))
        ids = ", ".join(source.ref_id for source in added)
        return DocumentResult(
            "berhasil",
            f"{len(added)} sumber disimpan sebagai **{ids}**. Proses ini tidak memakai token AI.\n\n"
            + self.registry.format_sources(current),
        )

    def source_list(self) -> DocumentResult:
        if not self.registry:
            return DocumentResult("belum_dikonfigurasi", "Source Registry belum tersedia.")
        return DocumentResult("berhasil", self.registry.format_sources(self.registry.list_sources(self.source_scope)))

    def build_demo(self) -> DocumentResult:
        if not self.engine_ready:
            return DocumentResult("belum_dikonfigurasi", "Document Engine belum tersedia pada runtime ini.")
        result = self.engine.build(demo_spec(), create_pdf=True)
        if result.status != "berhasil":
            return DocumentResult("gagal", result.warning or "Document Engine gagal membuat file demo.")
        lines = ["Document Engine berhasil membuat file demo tanpa memakai token AI.", f"DOCX: `{result.docx_path}`"]
        lines.append(f"PDF: `{result.pdf_path}`" if result.pdf_path else "PDF: belum dibuat otomatis.")
        if result.warning:
            lines.append(f"Catatan: {result.warning}")
        return DocumentResult("berhasil", "\n".join(lines))

    def reset(self) -> DocumentResult:
        self._history.clear()
        self._last_research = None
        self._outline_text = ""
        self._draft_spec = None
        self.requirements.reset()
        self.cover.reset()
        self.phase = "requirements"
        if self.registry:
            self.registry.clear_scope(self.source_scope)
        return DocumentResult(
            "berhasil",
            "Sesi Document Agent direset. Requirement awal akan dikumpulkan secara lokal tanpa token AI.",
        )

    @staticmethod
    def _usage_note_values(model: str, input_tokens: int, output_tokens: int) -> str:
        if not (input_tokens or output_tokens):
            return ""
        return (
            f"\n\n[Model: {model} | token masuk: {input_tokens:,} | token keluar: {output_tokens:,}]"
        ).replace(",", ".")

    @classmethod
    def _usage_note(cls, reply) -> str:
        return cls._usage_note_values(reply.model, reply.input_tokens, reply.output_tokens)

    def _outline_messages(self, raw: str, *, revision: bool = False) -> list[dict[str, str]]:
        messages = [{"role": "system", "content": OUTLINE_PROMPT}]
        messages.append({"role": "system", "content": "REQUIREMENT MAKALAH TERVALIDASI:\n" + self.requirements.structured_text()})
        if revision:
            messages.extend(self._history[-self.history_limit:])
            messages.append({"role": "user", "content": "Revisi outline sesuai permintaan ini:\n" + raw[:4000]})
        else:
            messages.append({"role": "user", "content": "Buat ringkasan requirement dan outline makalah sekarang."})
        return messages

    def _generate_outline(self, raw: str, *, revision: bool = False) -> DocumentResult:
        if not self.configured:
            return self.status()
        reply = self.provider.generate(self._outline_messages(raw, revision=revision), max_tokens=850, temperature=0.3, timeout=45)
        if reply.status != "berhasil":
            return DocumentResult(reply.status, reply.text)
        if revision:
            self._history.append({"role": "user", "content": raw[:4000]})
        self._outline_text = reply.text[:12000]
        self._history.append({"role": "assistant", "content": self._outline_text})
        self._history = self._history[-self.history_limit:]
        self.phase = "outline_confirmation"
        return DocumentResult("berhasil", reply.text + self._usage_note(reply))

    @staticmethod
    def _outline_approved(raw: str) -> bool:
        text = re.sub(r"\s+", " ", raw.strip().casefold())
        if "tidak setuju" in text or "belum sesuai" in text:
            return False
        return text in {"setuju", "sesuai", "lanjut", "oke", "ok", "ya", "iya"} or text.startswith(("setuju ", "sudah sesuai", "outline sudah sesuai"))

    @staticmethod
    def _member_tuple(value: str) -> tuple[str, ...]:
        parts = [item.strip() for item in re.split(r"[,;\n]+", value or "") if item.strip()]
        return tuple(parts)

    def generate_draft(self) -> DocumentResult:
        if self.phase not in {"ready_for_draft", "draft_ready"}:
            return DocumentResult("membutuhkan_bantuan", "Draft belum bisa dibuat. Lengkapi requirement, setujui outline, dan isi data cover terlebih dahulu.")
        if not self.registry:
            return DocumentResult("belum_dikonfigurasi", "Source Registry belum tersedia.")
        sources = self.registry.list_sources(self.source_scope)
        if not sources:
            return DocumentResult(
                "membutuhkan_sumber",
                "Source Registry masih kosong. Cari dan simpan sumber dulu dengan `/research <topik>` lalu `/research_save ...`. Tidak ada token AI yang dipakai pada langkah itu.",
            )
        result = self.draft_generator.generate(
            self.requirements.structured_text(), self.cover.structured_text(), self._outline_text, sources,
        )
        if result.status != "berhasil":
            return DocumentResult(result.status, (result.warning or "Draft belum berhasil dibuat.") + self._usage_note_values(result.model, result.input_tokens, result.output_tokens))

        teacher = self.cover.teacher_name
        if teacher.casefold() == "tidak dicantumkan":
            teacher = ""
        year = self.cover.academic_year
        if year.casefold() == "tidak dicantumkan":
            year = ""
        self._draft_spec = MakalahSpec(
            order_id="DRAFT-" + self.source_scope.replace("DOCSRC-", ""),
            title=self.requirements.topic_title,
            institution=self.cover.institution_name,
            class_semester=self.requirements.class_semester,
            subject=self.requirements.subject,
            author=self.cover.author_name,
            teacher=teacher,
            year=year,
            group_name=self.cover.group_name,
            members=self._member_tuple(self.cover.group_members),
            preface=result.preface,
            sections=result.sections,
        )
        self.phase = "draft_ready"
        section_titles = [section.title for section in result.sections if section.title]
        cited = sorted(set(re.findall(r"\[\[(R\d+)\]\]", "\n".join(
            paragraph for section in result.sections for paragraph in section.paragraphs
        ), flags=re.IGNORECASE)), key=lambda item: int(item[1:]))
        text = (
            "Draft terstruktur berhasil dibuat. Belum dibuat menjadi DOCX/PDF pada tahap ini.\n\n"
            f"Section: {len(section_titles)}\n"
            f"Sumber yang ditandai di draft: {', '.join(cited) if cited else 'belum ada marker sumber'}\n"
            "Formatting footnote dan daftar pustaka akan ditangani engine lokal, bukan AI."
        )
        return DocumentResult("draft_ready", text + self._usage_note_values(result.model, result.input_tokens, result.output_tokens))

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
        if command in {"/research_save", "/riset_simpan"}:
            return self.research_save(raw)
        if command in {"/sources", "/sumber"}:
            return self.source_list()
        if command in {"/draft", "/buat_draft"}:
            return self.generate_draft()

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
                + "\n\nJika sumber sudah ada di Source Registry, ketik `/draft` untuk membuat draft. Perintah `/draft` memakai token AI.",
            )

        if self.phase == "ready_for_draft":
            self.cover.update(raw)
            return DocumentResult(
                "ready_for_draft",
                "Requirement, outline, dan cover sudah siap. Ketik `/draft` jika ingin mulai membuat draft dengan AI. Saya tidak akan memakai token sampai perintah itu diberikan.",
            )

        if self.phase == "draft_ready":
            return DocumentResult(
                "draft_ready",
                "Draft terstruktur sudah tersedia di runtime. Tahap berikutnya (No. 5) adalah mengirim draft ini ke Citation Engine + Document Engine untuk menghasilkan DOCX/PDF final.",
            )

        return DocumentResult("membutuhkan_bantuan", "Status sesi dokumen tidak dikenali. Gunakan /makalah_baru untuk memulai ulang.")
