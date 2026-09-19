# Provider AI & Harga — Laras (Finance Agent)

## Status kode saat ini (diperbarui 19 September 2026)

Laras **sekarang memakai AI**, tapi untuk satu hal spesifik saja: mengklasifikasikan
**pertanyaan keuangan bebas** dari owner lewat Telegram (mis. "pemasukan bulan lalu
Risol Mamqi berapa?", "untung bulan ini berapa?") — lihat `app/finance_query.py`
(`FinanceQueryInterpreter`), dipanggil dari `FinanceService.handle()` sebelum jatuh
ke command tetap/parsing pencatatan deterministik. Ini milestone pertama Laras
benar-benar terhubung ke provider AI di produksi.

Yang TIDAK berubah — tetap 100% deterministik, tidak pernah lewat AI:
- **Mencatat transaksi baru** (mis. "Catat pengeluaran 80 ribu beli tinta pakai
  BCA") — parsing regex/aturan di `app/finance.py` seperti sebelumnya.
- **Seluruh command tetap** (`/hari_ini`, `/bulan_ini`, `/laba_rugi`, `/arus_kas`,
  `/saldo`, dst) — tidak pernah memanggil AI sama sekali.
- **Angka jawaban itu sendiri** — AI HANYA mengklasifikasikan field pertanyaan
  (jenis laporan, periode, usaha, akun, income/expense); semua angka tetap
  dihitung `FinanceService` dari database asli, sama seperti agent lain
  (lihat "Hallucination Prevention & Topic Restriction" di
  `policies/security_policy.md`). Kalau AI gagal/tidak dikonfigurasi/hasilnya
  tidak valid, sistem jatuh ke jalur lama tanpa macet.

Provider yang dipakai: DeepSeek (`app/providers/deepseek.py`), instance yang
dibuat khusus untuk Laras di `app/admin_runtime.py::create_admin_lead` (konfigurasi
env sama dengan Nara/Kirana: `DEEPSEEK_API_KEY`, dst, tapi instance terpisah).

## Kenapa Laras (nanti) bisa butuh AI

Dua kebutuhan yang cocok untuk AI:
1. [x] **Pertanyaan bebas soal laporan keuangan** (SELESAI 19 September 2026,
   lihat status di atas) — BUKAN parsing pencatatan transaksi baru (itu tetap
   deterministik selamanya), melainkan klasifikasi pertanyaan LAPORAN bebas
   dari owner.
2. [ ] **Membaca struk lewat foto (vision)** — masih belum ada, kebutuhan yang
   benar-benar butuh AI karena bukan sekadar parsing teks, melainkan membaca
   gambar (lihat `docs/finance_saas_v1.md` "Receipt AI Flow").

## Rekomendasi (untuk saat diaktifkan nanti)

| Tugas | Model default | Model eskalasi |
| --- | --- | --- |
| Parsing teks transaksi | DeepSeek V4.1 Flash (`deepseek-flash`) | DeepSeek V4 Pro (`deepseek-v4-pro`), untuk kalimat rumit/ambigu |
| Membaca struk (vision) | Gemini 3.5 Flash-Lite | Gemini 3.8 Flash, untuk struk buram/tulisan tangan |

DeepSeek untuk parsing teks bisa dipasang dengan adapter yang sudah ada
(`app/providers/deepseek.py`) begitu keputusan diambil untuk mengaktifkan
AI di Laras. Gemini untuk vision struk butuh adapter kode baru
(`app/providers/gemini.py` belum ada).

## Harga (per 19 September 2026)

**DeepSeek V4.1 Flash** — sumber: agregator pihak ketiga (`benchlm.ai`),
cek `https://api-docs.deepseek.com/quick_start/pricing` untuk konfirmasi:
- Cache-miss input: $0.30/juta (jam sibuk) / $0.15/juta (luar jam sibuk)
- Cache-hit input: $0.006/juta (jam sibuk) / $0.003/juta (luar jam sibuk)
- Output: $1.20/juta (jam sibuk) / $0.60/juta (luar jam sibuk)

**DeepSeek V4 Pro** — sama seperti di atas, ada catatan ketidakpastian harga
(lihat `docs/providers/nara.md` untuk detail lengkapnya): sekitar
$0.435/juta input (nilai registry) hingga kemungkinan $1.32/juta (tarif
jam sibuk lebih baru, belum terkonfirmasi resmi); output $0.87/juta.

**Gemini 3.5 Flash-Lite** — sumber resmi
(`https://ai.google.dev/gemini-api/docs/pricing`):
- Input: $0.30/juta token
- Output: $2.50/juta token

**Gemini 3.8 Flash** (standard) — sumber resmi:
- Input: $0.75/juta token (naik jadi $1.50/juta mulai 1 Januari 2027)
- Output: $3.75/juta token (naik jadi $7.50/juta mulai 1 Januari 2027)

## Estimasi biaya bulanan

Belum ada data trafik produksi nyata untuk fitur pertanyaan bebas ini (baru
diaktifkan 19 September 2026), jadi masih perkiraan kasar. Satu klasifikasi
pertanyaan = satu panggilan singkat (`max_tokens=300`, prompt pendek, tanpa
riwayat percakapan berantai), jadi biaya per pertanyaan jauh lebih kecil
dibanding satu putaran percakapan Nara — kemungkinan besar tidak signifikan
terhadap `MONTHLY_API_BUDGET_USD=20` bahkan dengan pemakaian harian oleh
owner.

## Variabel `.env` terkait

- `DEEPSEEK_API_KEY`, `DEEPSEEK_MODEL`, `DEEPSEEK_BASE_URL` — sudah ada dan
  SEKARANG aktif dipakai fitur pertanyaan bebas Laras (sama seperti yang
  dipakai Nara/Kirana).
- `GEMINI_API_KEY` — tempatnya sudah ada di `config/.env.example` (masih
  kosong), butuh adapter kode baru dulu untuk vision struk (belum
  diaktifkan).
