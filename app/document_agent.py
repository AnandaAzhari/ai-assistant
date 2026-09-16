"""Document/Makalah Agent v1.2.

Data awal dan data cover dikumpulkan lokal tanpa token AI.
DeepSeek dipakai untuk kerangka makalah dan, hanya setelah perintah admin eksplisit
/draft, membuat isi makalah terstruktur dengan sumber R1/R2/... dari Source Registry.
Sesudah isi siap, CitationEngine + DocumentEngine membuat catatan kaki, daftar pustaka,
DOCX, dan PDF secara lokal tanpa memanggil model AI lagi.
"""

from __future__ import annotations

import os
import re
from dataclasses import dataclass

from app.citation_engine import CitationEngine
from app.document_cover import MakalahCoverData
from app.document_draft import DraftGenerator
from app.document_engine import DocumentEngine, MakalahSpec, demo_spec
from app.document_requirements import MakalahRequirements
from app.providers.base import ModelProvider
from app.research_manager import ResearchManager, ResearchResult
from app.source_registry import SourceRegistry


OUTLINE_PROMPT = """Kamu adalah Document/Makalah Agent Taqi DocuTech.
Data utama makalah sudah diperiksa oleh sistem.

Tugasmu pada tahap ini HANYA membuat ringkasan singkat dan kerangka makalah.
Aturan:
- gunakan bahasa Indonesia yang jelas, sederhana, dan mudah dipahami siswa/i;
- jangan gunakan istilah teknis bila ada kata yang lebih mudah;
- jangan gunakan tabel Markdown;
- ringkasan data cukup berupa bullet singkat;
- jika ada arahan guru/dosen, arahan itu lebih penting daripada template standar;
- jangan mengarang sumber atau daftar pustaka;
- struktur default: Halaman Awal, BAB I PENDAHULUAN, BAB II PEMBAHASAN, BAB III PENUTUP, dan Daftar Pustaka bila sumber tersedia;
- buat subbab bernomor yang relevan, tetapi jangan terlalu banyak;
- JANGAN meminta data cover pada jawaban ini; data cover dikumpulkan sistem lokal setelah kerangka disetujui;
- JANGAN membuat isi makalah lengkap pada tahap ini;
- akhiri dengan kalimat: `Jika kerangka ini sudah sesuai, balas: setuju.`
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
        self.citation_engine = CitationEngine(engine) if engine is not None else None
        self.history_limit = max(2, int(history_limit))
        self._history: list[dict[str, str]] = []
        self._last_research: ResearchResult | None = None
        self._outline_text = ""
        self._draft_spec: MakalahSpec | None = None
        self._final_docx_path = ""
        self._final_pdf_path = ""
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
        draft_note = "Pembuat isi makalah: siap" if self.configured else "Pembuat isi makalah: menunggu provider AI"
        final_note = "Pembuat Word/PDF + catatan kaki: siap" if self.citation_engine else "Pembuat Word/PDF + catatan kaki: belum tersedia"
        if not self.configured:
            return DocumentResult(
                "belum_dikonfigurasi",
                "Document Agent tersedia. Data awal dan data cover diproses lokal, tetapi DeepSeek API belum dikonfigurasi.\n"
                + engine_note + "\n" + research_note + "\n" + registry_note + "\n" + draft_note + "\n" + final_note,
            )
        return DocumentResult(
            "siap",
            f"Document Agent: siap memakai {self.model_label}.\n{engine_note}.\n{research_note}\n{registry_note}\n{draft_note}.\n{final_note}.\n"
            "Data awal + data cover diproses lokal tanpa token AI; model dipakai untuk kerangka dan isi makalah saja.",
        )

    def engine_status(self) -> DocumentResult:
        if not self.engine_ready:
            return DocumentResult("belum_dikonfigurasi", "Document Engine belum tersedia pada runtime ini.")
        citation_note = self.citation_engine.status_text if self.citation_engine else "Catatan kaki belum tersedia."
        return DocumentResult("siap", self.engine.status_text + "\n" + citation_note)

    def research_status(self) -> DocumentResult:
        if not self.research:
            return DocumentResult("belum_dikonfigurasi", "Research Manager belum tersedia pada runtime ini.")
        registry = "Daftar sumber siap." if self.registry else "Daftar sumber belum tersedia."
        return DocumentResult("siap", self.research.status_text + " " + registry)

    def research_search(self, raw: str) -> DocumentResult:
        if not self.research:
            return DocumentResult("belum_dikonfigurasi", "Research Manager belum tersedia pada runtime ini.")
        parts = raw.split(maxsplit=1)
        query = parts[1].strip() if len(parts) > 1 else ""
        if not query:
            query = (self.requirements.topic_title or "").strip()
        if not query:
            return DocumentResult("membutuhkan_bantuan", "Tulis topik yang ingin dicari sumbernya.")
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
            return DocumentResult("belum_dikonfigurasi", "Daftar sumber belum tersedia.")
        if not self._last_research or self._last_research.status != "berhasil":
            return DocumentResult("membutuhkan_bantuan", "Belum ada hasil pencarian sumber. Cari sumber terlebih dahulu.")
        parts = raw.split(maxsplit=1)
        selection_text = parts[1] if len(parts) > 1 else "all"
        indices = self._parse_source_selection(selection_text, len(self._last_research.sources))
        if not indices:
            return DocumentResult("membutuhkan_bantuan", "Pilihan sumber tidak dikenali.")
        chosen = [self._last_research.sources[index - 1] for index in indices]
        added = self.registry.add_sources(self.source_scope, chosen)
        current = self.registry.list_sources(self.source_scope)
        if not added:
            return DocumentResult("berhasil", "Sumber yang dipilih sudah tersimpan.\n\n" + self.registry.format_sources(current))
        ids = ", ".join(source.ref_id for source in added)
        return DocumentResult(
            "berhasil",
            f"{len(added)} sumber disimpan sebagai **{ids}**. Proses ini tidak memakai token AI.\n\n"
            + self.registry.format_sources(current),
        )

    def source_list(self) -> DocumentResult:
        if not self.registry:
            return DocumentResult("belum_dikonfigurasi", "Daftar sumber belum tersedia.")
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
        self._final_docx_path = ""
        self._final_pdf_path = ""
        self.requirements.reset()
        self.cover.reset()
        self.phase = "requirements"
        if self.registry:
            self.registry.clear_scope(self.source_scope)
        return DocumentResult(
            "berhasil",
            "Sesi dokumen dimulai ulang. Saya akan meminta data yang benar-benar diperlukan saja.",
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
        messages.append({"role": "system", "content": "DATA MAKALAH YANG SUDAH LENGKAP:\n" + self.requirements.structured_text()})
        if revision:
            messages.extend(self._history[-self.history_limit:])
            messages.append({"role": "user", "content": "Perbaiki kerangka makalah sesuai permintaan ini:\n" + raw[:4000]})
        else:
            messages.append({"role": "user", "content": "Buat ringkasan data dan kerangka makalah sekarang."})
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
        return text in {"setuju", "sesuai", "lanjut", "oke", "ok", "ya", "iya"} or text.startswith(("setuju ", "sudah sesuai", "kerangka sudah sesuai", "outline sudah sesuai"))

    @staticmethod
    def _member_tuple(value: str) -> tuple[str, ...]:
        parts = [item.strip() for item in re.split(r"[,;\n]+", value or "") if item.strip()]
        return tuple(parts)

    def generate_draft(self) -> DocumentResult:
        if self.phase not in {"ready_for_draft", "draft_ready"}:
            return DocumentResult("membutuhkan_bantuan", "Isi makalah belum bisa dibuat. Lengkapi data utama, setujui kerangka, dan isi data cover terlebih dahulu.")
        if not self.registry:
            return DocumentResult("belum_dikonfigurasi", "Daftar sumber belum tersedia.")
        sources = self.registry.list_sources(self.source_scope)
        if not sources:
            return DocumentResult(
                "membutuhkan_sumber",
                "Belum ada sumber yang disimpan. Cari sumber terlebih dahulu sebelum membuat isi makalah.",
            )
        result = self.draft_generator.generate(
            self.requirements.structured_text(), self.cover.structured_text(), self._outline_text, sources,
        )
        if result.status != "berhasil":
            return DocumentResult(result.status, (result.warning or "Isi makalah belum berhasil dibuat.") + self._usage_note_values(result.model, result.input_tokens, result.output_tokens))

        teacher = self.cover.teacher_name
        if teacher.casefold() == "tidak dicantumkan":
            teacher = ""
        year = self.cover.academic_year
        if year.casefold() == "tidak dicantumkan":
            year = ""
        institution = self.cover.institution_name
        if institution.casefold() == "tidak dicantumkan":
            institution = ""
        group_name = self.cover.group_name
        if group_name.casefold() == "tidak dicantumkan":
            group_name = ""
        self._draft_spec = MakalahSpec(
            order_id="DRAFT-" + self.source_scope.replace("DOCSRC-", ""),
            title=self.requirements.topic_title,
            institution=institution,
            class_semester=self.requirements.class_semester,
            subject=self.requirements.subject,
            author=self.cover.author_name,
            teacher=teacher,
            year=year,
            group_name=group_name,
            members=self._member_tuple(self.cover.group_members),
            preface=result.preface,
            sections=result.sections,
        )
        self._final_docx_path = ""
        self._final_pdf_path = ""
        self.phase = "draft_ready"
        section_titles = [section.title for section in result.sections if section.title]
        cited = sorted(set(re.findall(r"\[\[(R\d+)\]\]", "\n".join(
            paragraph for section in result.sections for paragraph in section.paragraphs
        ), flags=re.IGNORECASE)), key=lambda item: int(item[1:]))
        text = (
            "Isi makalah berhasil dibuat. Belum dijadikan file Word/PDF pada tahap ini.\n\n"
            f"Jumlah bagian: {len(section_titles)}\n"
            f"Sumber yang dipakai: {', '.join(cited) if cited else 'belum ada sumber yang ditandai'}\n"
            "Catatan kaki dan daftar pustaka akan dibuat otomatis."
        )
        return DocumentResult("draft_ready", text + self._usage_note_values(result.model, result.input_tokens, result.output_tokens))

    def build_final(self) -> DocumentResult:
        """No. 5: isi makalah -> catatan kaki -> daftar pustaka -> DOCX + PDF.

        Tahap ini sepenuhnya lokal dan tidak memanggil provider AI.
        """
        if self.phase == "final_ready" and self._final_docx_path:
            lines = ["File makalah sudah tersedia.", f"Word: `{self._final_docx_path}`"]
            lines.append(f"PDF: `{self._final_pdf_path}`" if self._final_pdf_path else "PDF: belum berhasil dibuat.")
            return DocumentResult("final_ready", "\n".join(lines))

        if self.phase != "draft_ready" or self._draft_spec is None:
            return DocumentResult("membutuhkan_bantuan", "Isi makalah belum siap. Selesaikan pembuatan isi makalah terlebih dahulu.")
        if not self.citation_engine or not self.engine_ready:
            return DocumentResult("belum_dikonfigurasi", "Mesin Word/PDF dan catatan kaki belum tersedia.")
        if not self.registry:
            return DocumentResult("belum_dikonfigurasi", "Daftar sumber belum tersedia.")

        sources = self.registry.list_sources(self.source_scope)
        if not sources:
            return DocumentResult("membutuhkan_sumber", "Daftar sumber kosong, sehingga catatan kaki dan daftar pustaka belum bisa dibuat.")

        result = self.citation_engine.build(self._draft_spec, sources, create_pdf=True)
        if result.status != "berhasil":
            lines = ["File makalah belum berhasil dibuat."]
            if result.docx_path:
                lines.append(f"Word sementara: `{result.docx_path}`")
            if result.warning:
                lines.append(f"Catatan: {result.warning}")
            return DocumentResult("gagal", "\n".join(lines))

        self._final_docx_path = result.docx_path
        self._final_pdf_path = result.pdf_path
        self.phase = "final_ready"

        lines = [
            "File makalah berhasil dibuat tanpa memakai token AI tambahan.",
            f"Word: `{result.docx_path}`",
        ]
        if result.pdf_path:
            lines.append(f"PDF: `{result.pdf_path}`")
        else:
            lines.append("PDF: belum berhasil dibuat otomatis, tetapi file Word sudah tersedia.")
        if result.used_refs:
            lines.append("Sumber yang benar-benar dipakai: " + ", ".join(result.used_refs))
        lines.append("Catatan kaki dan daftar pustaka dibuat otomatis dari sumber yang dipakai di isi makalah.")
        if result.warning:
            lines.append("Catatan: " + result.warning)
        return DocumentResult("final_ready", "\n".join(lines))

    @staticmethod
    def _wants_final_file(text: str) -> bool:
        clean = re.sub(r"\s+", " ", (text or "").strip().casefold())
        if clean in {"ya", "iya", "boleh", "lanjut", "oke", "ok", "setuju"}:
            return True
        phrases = (
            "buat file", "buatkan file", "buat word", "buatkan word", "buat pdf", "buatkan pdf",
            "jadikan word", "jadikan pdf", "lanjut buat file", "lanjutkan jadi file", "simpan ke word",
        )
        return any(phrase in clean for phrase in phrases)

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
        if command in {"/final", "/buat_file", "/word_pdf"}:
            return self.build_final()

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
                "Data utama untuk cover sudah cukup.\n\n"
                + self.cover.structured_text()
                + "\n\nUntuk pengujian admin saat ini, ketik `/draft` jika ingin membuat isi makalah. Pelanggan nantinya tidak perlu memakai perintah seperti ini.",
            )

        if self.phase == "ready_for_draft":
            self.cover.update(raw)
            return DocumentResult(
                "ready_for_draft",
                "Semua data utama sudah siap. Untuk pengujian admin saat ini, ketik `/draft` untuk membuat isi makalah. Pelanggan nantinya cukup menjawab dengan bahasa biasa.",
            )

        if self.phase == "draft_ready":
            if self._wants_final_file(raw):
                return self.build_final()
            return DocumentResult(
                "draft_ready",
                "Isi makalah sudah tersedia. Jika ingin dibuatkan file Word dan PDF lengkap dengan catatan kaki serta daftar pustaka, cukup jawab `lanjut buat file`.",
            )

        if self.phase == "final_ready":
            return self.build_final()

        return DocumentResult("membutuhkan_bantuan", "Status sesi dokumen tidak dikenali. Mulai ulang sesi makalah untuk mencoba lagi.")
