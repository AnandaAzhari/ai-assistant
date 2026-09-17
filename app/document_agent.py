"""Document/Makalah Agent v2.1.

MakalahBrief menjadi schema pusat kebutuhan pelanggan. AI dipakai lebih dulu untuk
memahami bahasa natural, typo, urutan acak, dan koreksi; kode deterministik tetap
memegang state, validasi, fallback lokal, cover, research registry, serta pembuatan
Word/PDF. DeepSeek dipakai untuk interpretasi briefing, kerangka, dan isi makalah.

Outline UX v2 memisahkan ringkasan pelanggan dari detail teknis internal. Jika fokus
belum diberikan pelanggan, model boleh mengusulkan fokus; usulan baru dikunci ke
MakalahBrief setelah pelanggan menyetujui kerangka.
"""

from __future__ import annotations

import os
import re
from dataclasses import dataclass

from app.citation_engine import CitationEngine
from app.document_cover import MakalahCoverData
from app.document_draft import DraftGenerator
from app.document_engine import DocumentEngine, MakalahSpec, demo_spec
from app.document_intake import IntakeInterpreter, IntakeResult
from app.document_policy import load_document_format_policy
from app.document_preferences import (
    DocumentPreferences,
    DocumentPreferenceStore,
    PreferenceParseResult,
)
from app.makalah_brief import MakalahBrief
from app.providers.base import ModelProvider
from app.research_manager import ResearchManager, ResearchResult
from app.source_registry import SourceRegistry


OUTLINE_MAX_TOKENS = 8000
OUTLINE_FOCUS_MARKER = "TAQI_PROPOSED_FOCUS"
OUTLINE_FOCUS_RE = re.compile(
    r"<!--\s*TAQI_PROPOSED_FOCUS\s*:\s*(.*?)\s*-->",
    re.IGNORECASE | re.DOTALL,
)
OUTLINE_ACTION_HINT = (
    "\n\n---\n"
    "Jika kerangkanya sudah sesuai, cukup balas dengan bahasa biasa seperti "
    "`lanjutkan`, `lanjut saja`, `sudah sesuai`, atau `oke lanjut`. "
    "Jika ingin diubah, tuliskan bagian yang perlu diperbaiki."
)

COVER_FIELD_LABELS = (
    ("institution_name", "Sekolah/kampus"),
    ("assignment_type", "Jenis tugas"),
    ("author_name", "Nama penyusun"),
    ("group_name", "Kelompok"),
    ("group_members", "Anggota kelompok"),
    ("academic_year", "Tahun ajaran"),
    ("teacher_name", "Guru/dosen"),
)

OUTLINE_PROMPT = """Kamu adalah Document/Makalah Agent Taqi DocuTech.
MakalahBrief sudah diperiksa sistem dan data inti sudah cukup.

Tugasmu pada tahap ini HANYA membuat bagian customer-facing berikut:
1. `## Usulan Fokus` — HANYA jika fokus MakalahBrief masih kosong.
2. `## Kerangka Makalah` — struktur makalah yang ringkas dan sesuai target panjang.

JANGAN membuat `Ringkasan Data` atau `Ringkasan Kebutuhan`; sistem Python menambahkannya sendiri agar tidak mencampur data pelanggan dengan default internal.

ATURAN UX CUSTOMER:
- gunakan bahasa Indonesia yang jelas dan sesuai jenjang pelanggan;
- jangan tampilkan detail teknis internal seperti policy, Heading 1/2/3/4, reset nomor halaman, field Word, TOC, engine, token, atau alasan implementasi;
- jangan membuat bagian `Catatan Penyusunan`, `Catatan Teknis`, `Aturan Teknis`, atau penjelasan internal lain;
- jangan menulis petunjuk `balas lanjutkan/setuju`; sistem menambahkannya secara deterministik;
- jangan mengulang nilai default seolah-olah pelanggan pernah memintanya;
- jangan menyebut gaya sitasi default bila pelanggan tidak memintanya;
- jangan mengarang sumber atau daftar pustaka;
- jangan meminta data cover pada jawaban ini;
- jangan membuat isi makalah lengkap pada tahap ini.

ATURAN FOKUS:
- jika `Fokus pembahasan` pada MakalahBrief SUDAH berisi nilai, gunakan fokus itu dan JANGAN membuat `## Usulan Fokus`;
- jika fokus masih kosong, buat satu usulan fokus yang singkat, spesifik, sesuai topik, jenjang, mata pelajaran, dan target panjang;
- setelah usulan fokus, tambahkan marker HTML berikut PERSIS di akhir respons:
  `<!-- TAQI_PROPOSED_FOCUS: isi fokus satu baris -->`
- marker hanya metadata mesin. Jangan jelaskan marker kepada pelanggan;
- jika fokus sudah ada, jangan menambahkan marker usulan fokus.

ATURAN KERANGKA:
- jika ada arahan guru/dosen/sekolah/kampus, arahan itu lebih penting daripada template standar;
- gunakan fokus, tingkat bahasa, ketentuan sumber, hal wajib/larangan, dan pedoman resmi dari MakalahBrief bila tersedia;
- WAJIB mengikuti policy format dokumen yang dikirim pada system message berikutnya;
- default Makalah memakai hierarki BAB I -> A. -> 1. -> a.; level 1. dan a. hanya dipakai bila benar-benar diperlukan;
- jangan mengganti default menjadi BAB I -> 1.1 -> 1.1.1 atau I. -> A. -> 1. -> a. tanpa instruksi resmi;
- hormati target jumlah halaman dan jangan membuat terlalu banyak subbagian untuk dokumen pendek;
- sertakan COVER, KATA PENGANTAR, DAFTAR ISI, BAB I, BAB II, BAB III, dan DAFTAR PUSTAKA;
- selesaikan seluruh kerangka; jangan sengaja memotong bagian akhir.
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
        preference_store: DocumentPreferenceStore | None = None,
        history_limit: int = 10,
    ):
        self.provider = provider
        self.engine = engine
        self.research = research or ResearchManager.from_env()
        self.registry = registry or SourceRegistry.from_env()
        self.draft_generator = DraftGenerator(provider)
        self.intake_interpreter = IntakeInterpreter(provider)
        self.citation_engine = CitationEngine(engine) if engine is not None else None
        self.preference_store = preference_store or DocumentPreferenceStore.from_env()
        self.history_limit = max(2, int(history_limit))
        self._history: list[dict[str, str]] = []
        self._last_research: ResearchResult | None = None
        self._outline_text = ""
        self._proposed_focus = ""
        self._draft_spec: MakalahSpec | None = None
        self._final_docx_path = ""
        self._final_pdf_path = ""
        self._last_intake_result: IntakeResult | None = None
        self.brief = MakalahBrief()
        # Alias sementara agar modul lama yang membaca `requirements` tetap kompatibel.
        self.requirements = self.brief
        self.cover = MakalahCoverData()
        self.phase = "requirements"
        self.source_scope = os.environ.get("DOCUMENT_SOURCE_SCOPE", "DOCSRC-ADMIN-DEFAULT").strip() or "DOCSRC-ADMIN-DEFAULT"
        self.preferences = self.preference_store.load(self.source_scope)

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
        labels = getattr(self.brief, "FIELD_LABELS", {})
        return any(bool(getattr(self.brief, key, "")) for key in labels)

    @property
    def draft_spec(self) -> MakalahSpec | None:
        return self._draft_spec

    @property
    def citation_repeat_mode(self) -> str:
        return self.preferences.citation_repeat_mode

    def status(self) -> DocumentResult:
        engine_note = "Document Engine: siap" if self.engine_ready else "Document Engine: belum tersedia"
        research_note = self.research.status_text if self.research else "Research Manager: belum tersedia"
        registry_note = "Source Registry: siap (SQLite)" if self.registry else "Source Registry: belum tersedia"
        draft_note = "Pembuat isi makalah: siap" if self.configured else "Pembuat isi makalah: menunggu provider AI"
        intake_note = "MakalahBrief: AI-first + validasi/fallback lokal" if self.configured else "MakalahBrief: fallback lokal"
        policy_note = "Format makalah: policy Markdown aktif"
        preference_note = f"Preferensi sitasi: {self.preferences.citation_repeat_mode}"
        final_note = "Pembuat Word/PDF + catatan kaki: siap" if self.citation_engine else "Pembuat Word/PDF + catatan kaki: belum tersedia"
        if not self.configured:
            return DocumentResult(
                "belum_dikonfigurasi",
                "Document Agent tersedia. MakalahBrief masih dapat memakai fallback lokal, tetapi provider AI belum dikonfigurasi.\n"
                + engine_note + "\n" + research_note + "\n" + registry_note + "\n" + draft_note + "\n" + intake_note + "\n" + policy_note + "\n" + preference_note + "\n" + final_note,
            )
        return DocumentResult(
            "siap",
            f"Document Agent: siap memakai {self.model_label}.\n{engine_note}.\n{research_note}\n{registry_note}\n{draft_note}.\n{intake_note}.\n{policy_note}.\n{preference_note}.\n{final_note}.\n"
            "AI memahami bahasa pelanggan terlebih dahulu; kode deterministik memvalidasi dan menyimpan state.",
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
            query = (self.brief.topic_title or "").strip()
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
        self._proposed_focus = ""
        self._draft_spec = None
        self._final_docx_path = ""
        self._final_pdf_path = ""
        self._last_intake_result = None
        self.brief.reset()
        self.cover.reset()
        self.preference_store.reset(self.source_scope)
        self.preferences = DocumentPreferences()
        self.phase = "requirements"
        if self.registry:
            self.registry.clear_scope(self.source_scope)
        return DocumentResult(
            "berhasil",
            "Sesi dokumen dimulai ulang. Saya akan memahami kebutuhan makalah dari percakapan biasa.",
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

    def _apply_intake_ai_first(self, raw: str) -> IntakeResult | None:
        """AI memahami pesan dulu; parser lokal hanya mengisi celah jika AI gagal/lewat."""
        result: IntakeResult | None = None
        if self.configured:
            result = self.intake_interpreter.interpret(raw, self.brief.structured_text())
            self._last_intake_result = result
            if result.status == "berhasil":
                self.brief.apply_ai_values(result.values)
        # Fallback tidak menimpa nilai yang sudah dipahami AI.
        self.brief.apply_local_fallback(raw)
        return result

    def _apply_preferences(self, raw: str) -> PreferenceParseResult:
        updated, result = self.preference_store.apply_message(self.source_scope, raw)
        self.preferences = updated
        if result.changed and self.phase == "final_ready":
            self._final_docx_path = ""
            self._final_pdf_path = ""
            self.phase = "draft_ready"
        return result

    @staticmethod
    def _preference_only_message(raw: str) -> bool:
        clean = re.sub(r"\s+", " ", (raw or "").strip().casefold())
        workflow_or_data_terms = (
            "halaman", "kelas", "semester", "mapel", "mata pelajaran", "mata kuliah",
            "topik", "judul", "tentang", "tema", "cover", "nama", "sekolah", "kampus",
            "universitas", "smk", "sma", "smp", "sd", "setuju", "sesuai", "lanjut",
            "buat file", "buat word", "buat pdf", "word", "pdf",
        )
        return not any(term in clean for term in workflow_or_data_terms)

    def _outline_messages(self, raw: str, *, revision: bool = False) -> list[dict[str, str]]:
        messages = [
            {"role": "system", "content": OUTLINE_PROMPT},
            {"role": "system", "content": "POLICY FORMAT DOKUMEN WAJIB:\n" + load_document_format_policy()},
            {"role": "system", "content": "MAKALAHBRIEF AKTIF:\n" + self.brief.structured_text()},
        ]
        if revision:
            messages.extend(self._history[-self.history_limit:])
            messages.append({"role": "user", "content": "Perbaiki fokus/kerangka sesuai permintaan pelanggan ini:\n" + raw[:4000]})
        else:
            messages.append({"role": "user", "content": "Buat usulan fokus bila diperlukan dan kerangka makalah sekarang."})
        return messages

    def _customer_outline_summary(self) -> str:
        """Ringkasan deterministik: hanya data pelanggan/brief, bukan default internal."""
        lines = [
            "## Ringkasan Kebutuhan",
            f"- Jenjang: {self.brief.institution_level}",
            f"- Kelas/semester: {self.brief.class_semester}",
            f"- Mata pelajaran/mata kuliah: {self.brief.subject}",
            f"- Topik/judul: {self.brief.topic_title}",
            f"- Target: {self.brief.target_length}",
        ]
        optional = (
            ("Fokus pembahasan", self.brief.focus),
            ("Arahan guru/dosen", self.brief.teacher_instructions),
            ("Tingkat bahasa", self.brief.language_level),
            ("Ketentuan sumber", self.brief.source_requirements),
            ("Gaya sitasi", self.brief.citation_style),
            ("Wajib dimasukkan", self.brief.must_include),
            ("Harus dihindari", self.brief.must_avoid),
            ("Pedoman/template resmi", self.brief.official_guideline),
        )
        for label, value in optional:
            clean = (value or "").strip()
            if not clean or clean.casefold() in {"tidak disebutkan", "tidak ada arahan khusus"}:
                continue
            lines.append(f"- {label}: {clean}")
        if self.preferences.citation_repeat_mode == "short":
            lines.append("- Preferensi sitasi: tanpa Ibid.; pengulangan memakai short note")
        return "\n".join(lines)

    @staticmethod
    def _strip_outline_noise(text: str) -> str:
        """Guardrail output: sembunyikan metadata dan bagian teknis bila model melanggar prompt."""
        clean = OUTLINE_FOCUS_RE.sub("", text or "")
        clean = re.sub(
            r"\n#{1,6}\s*(?:\d+\.\s*)?(?:Catatan Penyusunan|Catatan Teknis|Aturan Teknis|Detail Teknis)\b.*?(?=\n#{1,6}\s|\Z)",
            "",
            clean,
            flags=re.IGNORECASE | re.DOTALL,
        )
        return clean.strip()

    @classmethod
    def _parse_outline_response(cls, text: str, *, focus_already_set: bool) -> tuple[str, str]:
        proposed_focus = ""
        if not focus_already_set:
            match = OUTLINE_FOCUS_RE.search(text or "")
            if match:
                proposed_focus = re.sub(r"\s+", " ", match.group(1).strip())[:700]
        visible = cls._strip_outline_noise(text)
        return visible, proposed_focus

    def _generate_outline(self, raw: str, *, revision: bool = False) -> DocumentResult:
        if not self.configured:
            return self.status()
        messages = self._outline_messages(raw, revision=revision)
        reply = self.provider.generate(messages, max_tokens=OUTLINE_MAX_TOKENS, temperature=0.3, timeout=45)
        if reply.status != "berhasil" and "kosong" in (reply.text or "").casefold():
            reply = self.provider.generate(messages, max_tokens=OUTLINE_MAX_TOKENS, temperature=0.2, timeout=45)
        if reply.status != "berhasil":
            return DocumentResult(
                "sementara_gagal",
                "Kerangka makalah belum berhasil dibuat. Data yang Anda kirim tetap tersimpan. Cukup kirim `lanjut` untuk mencoba lagi.",
            )

        visible_outline, proposed_focus = self._parse_outline_response(
            reply.text,
            focus_already_set=bool(self.brief.focus),
        )
        if not visible_outline:
            return DocumentResult(
                "sementara_gagal",
                "Kerangka makalah belum berhasil dibaca dengan lengkap. Data Anda tetap tersimpan; kirim `lanjut` untuk mencoba lagi.",
            )

        if revision:
            self._history.append({"role": "user", "content": raw[:4000]})
        self._proposed_focus = proposed_focus if not self.brief.focus else ""
        self._outline_text = visible_outline
        self._history.append({"role": "assistant", "content": self._outline_text})
        self._history = self._history[-self.history_limit:]
        self.phase = "outline_confirmation"

        customer_text = self._customer_outline_summary() + "\n\n" + visible_outline.rstrip()
        return DocumentResult("berhasil", customer_text + OUTLINE_ACTION_HINT + self._usage_note(reply))

    @staticmethod
    def _outline_approved(raw: str) -> bool:
        text = re.sub(r"\s+", " ", raw.strip().casefold())
        text = text.strip(" .,!?:;")
        if not text:
            return False

        rejection_or_revision = (
            "tidak setuju", "belum sesuai", "tidak sesuai", "belum pas", "jangan lanjut",
            "jangan lanjutkan", "tahan dulu", "jangan dulu", "ubah ", "revisi", "perbaiki",
            "ganti ", "kurang ", "tambahkan", "hapus ", "hilangkan",
        )
        if any(term in text for term in rejection_or_revision):
            return False

        exact = {
            "setuju", "sesuai", "lanjut", "lanjutkan", "lanjut aja", "lanjut saja",
            "oke", "ok", "ya", "iya", "boleh", "sudah sesuai", "sudah pas", "udah pas",
            "oke lanjut", "oke lanjutkan", "ok lanjut", "ok lanjutkan", "boleh lanjut",
            "boleh lanjutkan", "silakan lanjut", "silahkan lanjut", "gas", "gas lanjut",
        }
        if text in exact:
            return True

        approval_prefixes = (
            "setuju ", "sudah sesuai ", "sudah pas ", "udah pas ",
            "kerangka sudah sesuai", "outline sudah sesuai", "kerangkanya sudah sesuai",
            "lanjut aja ", "lanjut saja ", "oke lanjut ", "oke lanjutkan ",
            "ok lanjut ", "ok lanjutkan ", "boleh lanjut ", "boleh lanjutkan ",
            "silakan lanjut ", "silahkan lanjut ",
        )
        return text.startswith(approval_prefixes)

    @staticmethod
    def _member_tuple(value: str) -> tuple[str, ...]:
        parts = [item.strip() for item in re.split(r"[,;\n]+", value or "") if item.strip()]
        return tuple(parts)

    @staticmethod
    def _cover_snapshot(cover: MakalahCoverData) -> dict[str, str]:
        return {key: str(getattr(cover, key, "") or "") for key, _ in COVER_FIELD_LABELS}

    @staticmethod
    def _cover_display_value(value: str) -> str:
        return value.strip() if value and value.strip() else "Tidak dicantumkan"

    @classmethod
    def _cover_update_message(cls, before: dict[str, str], after: dict[str, str]) -> str:
        changed = [
            (key, label, after.get(key, ""))
            for key, label in COVER_FIELD_LABELS
            if before.get(key, "") != after.get(key, "")
        ]
        if not changed:
            return ""
        lines = ["Data cover berhasil diperbarui:"]
        for _, label, value in changed:
            lines.append(f"- {label}: {cls._cover_display_value(value)}")
        lines.append(
            "\nJika masih ada data cover yang ingin ditambahkan atau diubah, kirim saja kapan pun sebelum file final dibuat."
        )
        lines.append(
            "Jika sudah cukup, lanjutkan proses dengan bahasa biasa seperti `lanjutkan` atau `sudah cukup`."
        )
        return "\n".join(lines)

    @staticmethod
    def _join_cover_messages(*parts: str) -> str:
        return "\n\n".join(part.strip() for part in parts if part and part.strip())

    def generate_draft(self) -> DocumentResult:
        if self.phase not in {"ready_for_draft", "draft_ready"}:
            return DocumentResult("membutuhkan_bantuan", "Isi makalah belum bisa dibuat. Lengkapi MakalahBrief, setujui kerangka, dan isi data cover terlebih dahulu.")
        if not self.registry:
            return DocumentResult("belum_dikonfigurasi", "Daftar sumber belum tersedia.")
        sources = self.registry.list_sources(self.source_scope)
        if not sources:
            return DocumentResult(
                "membutuhkan_sumber",
                "Belum ada sumber yang disimpan. Cari sumber terlebih dahulu sebelum membuat isi makalah.",
            )
        result = self.draft_generator.generate(
            self.brief.structured_text(), self.cover.structured_text(), self._outline_text, sources,
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
            title=self.brief.topic_title,
            institution=institution,
            class_semester=self.brief.class_semester,
            subject=self.brief.subject,
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

        result = self.citation_engine.build(
            self._draft_spec,
            sources,
            create_pdf=True,
            citation_repeat_mode=self.preferences.citation_repeat_mode,
        )
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
        if self.preferences.citation_repeat_mode == "short":
            lines.append("Pengulangan catatan kaki: tanpa Ibid.; memakai short note.")
        else:
            lines.append("Pengulangan catatan kaki: Ibid. boleh dipakai bila sumber langsung berurutan.")
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

        preference_result = self._apply_preferences(raw)
        if preference_result.ambiguous:
            return DocumentResult("needs_preference", preference_result.message)
        if preference_result.matched and self._preference_only_message(raw):
            extra = ""
            if preference_result.changed and self.phase == "draft_ready" and not self._final_docx_path:
                extra = "\nPreferensi ini akan dipakai saat file Word/PDF dibuat."
            return DocumentResult("preference_updated", preference_result.message + extra)

        if self.phase == "requirements":
            self._apply_intake_ai_first(raw)
            if not self.brief.complete:
                return DocumentResult("needs_requirements", self.brief.question_text())
            return self._generate_outline(raw)

        if self.phase == "outline_confirmation":
            if self._outline_approved(raw):
                approved_focus = ""
                if self._proposed_focus and self.brief.approve_focus(self._proposed_focus):
                    approved_focus = self.brief.focus
                self._proposed_focus = ""
                self.phase = "cover"
                prefix = f"Fokus kerangka disetujui: **{approved_focus}**\n\n" if approved_focus else ""
                return DocumentResult("needs_cover", prefix + self.cover.question_text())

            # Revisi natural seperti `fokuskan ke penggunaan AI Agent di sekolah`
            # juga boleh memperbarui MakalahBrief sebelum model menyusun ulang kerangka.
            self._apply_intake_ai_first(raw)
            return self._generate_outline(raw, revision=True)

        if self.phase == "cover":
            before = self._cover_snapshot(self.cover)
            expected_field = self.cover.next_required_field()
            clarification = self.cover.update(raw, expected_field=expected_field)
            after = self._cover_snapshot(self.cover)
            confirmation = self._cover_update_message(before, after)
            question = self.cover.question_text()

            if clarification:
                return DocumentResult(
                    "needs_cover_clarification",
                    self._join_cover_messages(confirmation, clarification, question),
                )
            if not self.cover.complete:
                return DocumentResult("needs_cover", self._join_cover_messages(confirmation, question))

            self.phase = "ready_for_draft"
            return DocumentResult(
                "cover_complete",
                self._join_cover_messages(
                    confirmation,
                    "Data utama untuk cover sudah cukup.\n\n" + self.cover.structured_text(),
                    "Data cover tetap boleh ditambahkan atau diubah kapan saja sebelum file final dibuat. "
                    "Jika sudah cukup, lanjutkan proses dengan bahasa biasa. Untuk pengujian admin saat ini, `/draft` tetap tersedia.",
                ),
            )

        if self.phase == "ready_for_draft":
            before = self._cover_snapshot(self.cover)
            clarification = self.cover.update(raw, expected_field="")
            after = self._cover_snapshot(self.cover)
            confirmation = self._cover_update_message(before, after)
            if clarification:
                return DocumentResult(
                    "needs_cover_clarification",
                    self._join_cover_messages(confirmation, clarification),
                )
            if confirmation:
                return DocumentResult("cover_updated", confirmation)
            return DocumentResult(
                "ready_for_draft",
                "Semua data utama sudah siap. Data cover masih boleh ditambahkan atau diubah kapan saja sebelum file final dibuat. "
                "Jika sudah cukup, lanjutkan proses dengan bahasa biasa. Untuk pengujian admin saat ini, `/draft` tetap tersedia.",
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
