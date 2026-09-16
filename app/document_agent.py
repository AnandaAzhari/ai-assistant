"""Document/Makalah Agent v0.1.

Tahap ini fokus pada percakapan requirement + outline/draft. Pembuatan DOCX/PDF
akan ditangani Document Engine terpisah agar formatting tidak memboroskan token.
"""

from __future__ import annotations

from dataclasses import dataclass

from app.providers.base import ModelProvider


SYSTEM_PROMPT = """Kamu adalah Document/Makalah Agent untuk Taqi DocuTech.
Gunakan bahasa Indonesia yang jelas dan ringkas.

Tugas utama:
- memahami permintaan makalah/dokumen pelanggan;
- mengumpulkan requirement yang masih kurang (jenjang, topik, panjang, format, deadline, referensi);
- membuat kerangka/outline dan membantu draft bila diminta;
- jangan mengaku sudah membuat file DOCX/PDF karena Document Engine belum dipanggil;
- jangan mengarang sumber atau daftar pustaka. Jika referensi belum tersedia, katakan perlu riset/sumber;
- untuk tugas sekolah/kuliah, bantu penyusunan dan drafting, tetapi minta pengguna meninjau isi agar sesuai instruksi guru/dosen.

Hemat token: jangan langsung menghasilkan makalah panjang hanya karena topik disebut. Jika requirement belum lengkap, tanyakan hanya informasi yang benar-benar dibutuhkan. Jika requirement cukup, tampilkan ringkasan requirement dan outline dahulu. Buat draft panjang hanya jika pengguna secara eksplisit meminta draft/isi.
"""


@dataclass(frozen=True)
class DocumentResult:
    status: str
    text: str


class DocumentAgent:
    def __init__(self, provider: ModelProvider, *, history_limit: int = 10):
        self.provider = provider
        self.history_limit = max(2, int(history_limit))
        self._history: list[dict[str, str]] = []

    @property
    def configured(self) -> bool:
        return bool(self.provider and self.provider.configured)

    @property
    def model_label(self) -> str:
        if not self.provider:
            return "belum tersedia"
        return f"{self.provider.provider_name} / {self.provider.model_name}"

    def status(self) -> DocumentResult:
        if not self.configured:
            return DocumentResult(
                "belum_dikonfigurasi",
                "Document Agent: tersedia, tetapi DeepSeek API belum dikonfigurasi. "
                "Isi DEEPSEEK_API_KEY pada .env lokal lalu restart Web Admin."
            )
        return DocumentResult(
            "siap",
            f"Document Agent: siap memakai {self.model_label}. Percakapan uji dapat dimulai dengan /makalah."
        )

    def reset(self) -> DocumentResult:
        self._history.clear()
        return DocumentResult("berhasil", "Sesi Document Agent direset. Silakan mulai permintaan dokumen baru.")

    def handle(self, message: str) -> DocumentResult:
        raw = (message or "").strip()
        if not raw:
            return DocumentResult("membutuhkan_bantuan", "Pesan dokumen kosong.")
        if not self.configured:
            return self.status()

        text = raw.casefold()
        if text.split(maxsplit=1)[0] in {"/dokumen_baru", "/makalah_baru"}:
            return self.reset()

        messages = [{"role": "system", "content": SYSTEM_PROMPT}]
        messages.extend(self._history[-self.history_limit:])
        messages.append({"role": "user", "content": raw[:8000]})

        reply = self.provider.generate(messages, max_tokens=1400, temperature=0.35, timeout=45)
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
