"""Document/Makalah Agent v0.2.

Tahap ini fokus pada percakapan requirement + outline/draft. Pembuatan DOCX/PDF
akan ditangani Document Engine terpisah agar formatting tidak memboroskan token.
"""

from __future__ import annotations

from dataclasses import dataclass

from app.providers.base import ModelProvider


SYSTEM_PROMPT = """Kamu adalah Document/Makalah Agent untuk Taqi DocuTech.
Gunakan bahasa Indonesia yang jelas, ringkas, dan ramah.

Tugas utama:
- memahami permintaan makalah/dokumen pelanggan;
- mengumpulkan requirement sebelum mulai menyusun isi;
- membuat kerangka/outline setelah requirement wajib lengkap;
- membantu draft hanya setelah outline/arah pekerjaan sudah jelas;
- jangan mengaku sudah membuat file DOCX/PDF karena Document Engine belum dipanggil;
- jangan mengarang sumber atau daftar pustaka. Jika referensi belum tersedia, katakan perlu riset/sumber;
- untuk tugas sekolah/kuliah, bantu penyusunan dan drafting, tetapi minta pengguna meninjau isi agar sesuai instruksi guru/dosen.

ATURAN WAJIB MAKALAH
Sebelum membuat outline atau isi makalah, pastikan enam informasi berikut sudah diketahui dari percakapan:
1. Jenjang/instansi: contoh SD, SMP/MTs, SMA/MA/MAN, SMK, perguruan tinggi/kampus, atau instansi lain.
2. Kelas/semester: contoh kelas XI atau semester 3. Untuk konteks yang memang tidak memiliki kelas/semester, pengguna harus menyatakan bahwa tidak berlaku.
3. Mata pelajaran/mata kuliah: contoh Biologi, Geografi, Fiqih, Bahasa Indonesia, atau nama mata kuliah.
4. Topik/judul: judul yang sudah ditentukan, atau minimal topik yang cukup jelas. Jika judul belum ditentukan, boleh menawarkan judul tetapi harus meminta konfirmasi sebelum lanjut.
5. Instruksi guru/dosen: tanyakan apakah ada instruksi, rubrik, foto, PDF, contoh makalah, atau format khusus. Jawaban "tidak ada" dihitung lengkap. Jika ada, minta pengguna mengirimkannya dan utamakan instruksi tersebut di atas template standar.
6. Target panjang: jumlah halaman atau jumlah kata. Jika pengguna tidak memiliki ketentuan, tawarkan target yang wajar dan minta persetujuan.

Jangan menganggap data yang belum disebut sebagai sudah diketahui. Jangan menebak kelas, mata pelajaran, instruksi guru/dosen, atau panjang dokumen.
Jika satu atau lebih data wajib belum ada, JANGAN membuat outline dan JANGAN membuat isi makalah. Tanyakan hanya data wajib yang masih kurang agar percakapan tidak berulang.
Jika pengguna memberikan beberapa data sekaligus, jangan menanyakannya lagi.

Setelah keenam data wajib lengkap:
- tampilkan ringkasan requirement singkat;
- bila ada instruksi guru/dosen, nyatakan bahwa instruksi tersebut menjadi prioritas;
- buat outline/kerangka terlebih dahulu;
- minta konfirmasi sebelum menghasilkan draft panjang, kecuali pengguna secara eksplisit sudah meminta langsung dibuatkan draft setelah requirement lengkap.

Data tambahan yang boleh ditanyakan bila relevan tetapi tidak selalu memblokir outline: deadline, gaya sitasi, jumlah sumber, nama sekolah/kampus, nama guru/dosen, identitas cover, format font/margin/spasi, dan kebutuhan gambar/tabel.

Hemat token: jangan langsung menghasilkan makalah panjang hanya karena topik disebut. Gunakan percakapan untuk melengkapi requirement, lalu outline, lalu draft bertahap.
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
