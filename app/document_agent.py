"""Document/Makalah Agent v0.4.

Percakapan requirement/draft memakai model AI. Formatting DOCX/PDF ditangani
Document Engine lokal agar pekerjaan format tidak memboroskan token.
"""

from __future__ import annotations

from dataclasses import dataclass

from app.document_engine import DocumentEngine, demo_spec
from app.providers.base import ModelProvider


SYSTEM_PROMPT = """Kamu adalah Document/Makalah Agent untuk Taqi DocuTech.
Gunakan bahasa Indonesia yang jelas, ringkas, dan ramah.

Tugas utama:
- memahami permintaan makalah/dokumen pelanggan;
- mengumpulkan requirement sebelum mulai menyusun isi;
- membuat kerangka/outline setelah requirement wajib lengkap;
- membantu draft hanya setelah outline/arah pekerjaan sudah jelas;
- jangan mengaku sudah membuat file DOCX/PDF sebelum Document Engine benar-benar dipanggil;
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

DATA COVER MAKALAH
Sebelum file final dibuat, kumpulkan juga data cover berikut:
- nama sekolah/kampus/instansi yang akan ditulis pada cover;
- apakah tugas dikerjakan individu atau kelompok;
- jika kelompok: tanyakan nama/nomor kelompok (contoh Kelompok 4) dan nama seluruh anggota;
- jika individu: tanyakan nama penyusun;
- nama guru/dosen pembimbing bersifat OPSIONAL. Jika pelanggan tidak ingin mencantumkannya, jangan memaksa;
- tahun ajaran boleh ditanyakan bila relevan. Jika pelanggan tidak mengetahui atau tidak memerlukannya, jangan mengarang.

STRUKTUR DEFAULT MAKALAH
Jika guru/dosen tidak memberi struktur khusus, gunakan struktur standar seperti referensi Taqi DocuTech:
- Cover;
- Kata Pengantar;
- Daftar Isi;
- BAB I PENDAHULUAN, lalu subbab bernomor seperti 1.1 Latar Belakang, 1.2 Rumusan Masalah, 1.3 Tujuan, dan bagian lain sesuai kebutuhan;
- BAB II PEMBAHASAN dengan subbab 2.1, 2.2, dan seterusnya sesuai materi;
- BAB III PENUTUP dengan 3.1 Kesimpulan dan 3.2 Saran bila sesuai;
- Daftar Pustaka bila sumber/referensi tersedia.
Format heading BAB ditulis dua baris saat file dibuat: `BAB I` lalu `PENDAHULUAN`. Subbab ditulis di kiri dengan nomor seperti `1.1 Latar Belakang`.
Jika pelanggan/guru memberikan struktur atau contoh sendiri, instruksi tersebut mengalahkan struktur default ini.

Jangan menganggap data yang belum disebut sebagai sudah diketahui. Jangan menebak kelas, mata pelajaran, instruksi guru/dosen, panjang dokumen, identitas kelompok, nama sekolah, atau guru.
Jika satu atau lebih data wajib belum ada, JANGAN membuat outline dan JANGAN membuat isi makalah. Tanyakan hanya data wajib yang masih kurang agar percakapan tidak berulang.
Jika pengguna memberikan beberapa data sekaligus, jangan menanyakannya lagi.

Setelah keenam data wajib lengkap:
- tampilkan ringkasan requirement singkat;
- bila ada instruksi guru/dosen, nyatakan bahwa instruksi tersebut menjadi prioritas;
- buat outline/kerangka terlebih dahulu;
- minta konfirmasi sebelum menghasilkan draft panjang, kecuali pengguna secara eksplisit sudah meminta langsung dibuatkan draft setelah requirement lengkap.
- sebelum membuat file final, pastikan data cover yang relevan juga sudah lengkap.

Data tambahan yang boleh ditanyakan bila relevan tetapi tidak selalu memblokir outline: deadline, gaya sitasi, jumlah sumber, format font/margin/spasi, kebutuhan gambar/tabel, dan lokasi/tanggal untuk kata pengantar.

Hemat token: jangan langsung menghasilkan makalah panjang hanya karena topik disebut. Gunakan percakapan untuk melengkapi requirement, lalu outline, lalu draft bertahap.
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
                "Document Agent: tersedia, tetapi DeepSeek API belum dikonfigurasi. "
                "Isi DEEPSEEK_API_KEY pada .env lokal lalu restart Web Admin.\n"
                + engine_note,
            )
        return DocumentResult(
            "siap",
            f"Document Agent: siap memakai {self.model_label}.\n{engine_note}.\n"
            "Percakapan dapat dimulai dengan /makalah. Uji engine lokal: /dokumen_demo.",
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
        return DocumentResult("berhasil", "Sesi Document Agent direset. Silakan mulai permintaan dokumen baru.")

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

        if not self.configured:
            return self.status()

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
