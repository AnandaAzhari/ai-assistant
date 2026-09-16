"""Document/Makalah Agent v0.6.

Enam requirement dasar dikumpulkan secara lokal tanpa memanggil model AI.
DeepSeek baru dipakai setelah data dasar lengkap. Formatting DOCX/PDF tetap
ditangani Document Engine lokal.
"""

from __future__ import annotations

from dataclasses import dataclass

from app.document_engine import DocumentEngine, demo_spec
from app.document_requirements import MakalahRequirements
from app.providers.base import ModelProvider


WORK_PROMPT = """Kamu adalah Document/Makalah Agent Taqi DocuTech.
Requirement dasar makalah sudah divalidasi oleh sistem dan akan diberikan secara terstruktur.
Gunakan bahasa Indonesia yang jelas dan ringkas. Jika nama pelanggan belum diketahui, gunakan sapaan `Anda`, bukan Bapak/Ibu.

Aturan kerja:
- patuhi instruksi guru/dosen di atas template standar;
- jangan mengarang sumber/daftar pustaka;
- setelah requirement lengkap, tampilkan ringkasan singkat dan outline terlebih dahulu;
- jangan membuat draft panjang sebelum outline dikonfirmasi, kecuali pengguna secara eksplisit meminta langsung dibuatkan draft;
- struktur default: Cover, Kata Pengantar, Daftar Isi, BAB I PENDAHULUAN (1.1 dst), BAB II PEMBAHASAN (2.1 dst), BAB III PENUTUP (3.1 Kesimpulan, 3.2 Saran bila sesuai), Daftar Pustaka bila sumber tersedia;
- sebelum file final, kumpulkan data cover yang belum ada: nama sekolah/kampus, individu/kelompok, nama penyusun/anggota, dan tahun ajaran bila relevan; nama guru/dosen opsional;
- jangan mengaku DOCX/PDF sudah dibuat sebelum Document Engine benar-benar dipanggil.
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
        history_limit: int = 10,
    ):
        self.provider = provider
        self.engine = engine
        self.history_limit = max(2, int(history_limit))
        self._history: list[dict[str, str]] = []
        self.requirements = MakalahRequirements()

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

    def status(self) -> DocumentResult:
        engine_note = "Document Engine: siap" if self.engine_ready else "Document Engine: belum tersedia"
        if not self.configured:
            return DocumentResult(
                "belum_dikonfigurasi",
                "Document Agent tersedia. Pengumpul requirement lokal aktif, tetapi DeepSeek API belum dikonfigurasi. "
                "Isi DEEPSEEK_API_KEY pada .env lokal lalu restart Web Admin.\n"
                + engine_note,
            )
        return DocumentResult(
            "siap",
            f"Document Agent: siap memakai {self.model_label}.\n{engine_note}.\n"
            "Pengumpulan enam requirement dasar diproses lokal tanpa token AI; model baru dipanggil setelah datanya lengkap.",
        )

    def engine_status(self) -> DocumentResult:
        if not self.engine_ready:
            return DocumentResult("belum_dikonfigurasi", "Document Engine belum tersedia pada runtime ini.")
        return DocumentResult("siap", self.engine.status_text)

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
        return DocumentResult(
            "berhasil",
            "Sesi Document Agent direset. Silakan mulai permintaan dokumen baru. "
            "Requirement awal akan dikumpulkan secara lokal tanpa token AI.",
        )

    def _model_messages(self, raw: str) -> list[dict[str, str]]:
        messages = [{"role": "system", "content": WORK_PROMPT}]
        messages.append({
            "role": "system",
            "content": "REQUIREMENT MAKALAH TERVALIDASI:\n" + self.requirements.structured_text(),
        })
        messages.extend(self._history[-self.history_limit:])
        messages.append({"role": "user", "content": raw[:8000]})
        return messages

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

        # Tahap pengumpulan requirement tidak memanggil AI sama sekali.
        self.requirements.update(raw)
        if not self.requirements.complete:
            return DocumentResult("needs_requirements", self.requirements.question_text())

        if not self.configured:
            return self.status()

        reply = self.provider.generate(
            self._model_messages(raw),
            max_tokens=1400,
            temperature=0.35,
            timeout=45,
        )
        if reply.status != "berhasil":
            return DocumentResult(reply.status, reply.text)

        self._history.append({"role": "user", "content": raw[:8000]})
        self._history.append({"role": "assistant", "content": reply.text[:12000]})
        self._history = self._history[-self.history_limit:]

        usage_note = ""
        if reply.input_tokens or reply.output_tokens:
            usage_note = (
                f"\n\n[Model: {reply.model} | token masuk: {reply.input_tokens:,} | "
                f"token keluar: {reply.output_tokens:,}]"
            ).replace(",", ".")
        return DocumentResult("berhasil", reply.text + usage_note)
