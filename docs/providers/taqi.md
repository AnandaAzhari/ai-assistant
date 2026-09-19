# Provider AI & Harga — Taqi (Lead Agent)

## Status kode saat ini

Taqi (router pesan pelanggan + panel command owner) **belum terhubung ke
provider AI apa pun**. Routing saat ini murni aturan/rule-based di
`app/lead.py` (lihat `/status`: baris "Lead AI model: belum dihubungkan").
Ini bukan bug — router aturan sudah cukup untuk volume dan pola pesan yang
ada sekarang, dan menghindari biaya API untuk setiap pesan masuk.

## Kenapa Taqi butuh AI (nanti)

Taqi dipanggil di **setiap pesan pelanggan yang masuk** — titik dengan volume
tertinggi di seluruh sistem. AI akan berguna untuk dua hal: (1) klasifikasi
intent yang lebih fleksibel dari aturan kaku saat ini, dan (2) menilai
pesan yang ambigu/mencurigakan (indikasi scam atau percobaan
prompt-injection) yang tidak aman diputuskan hanya oleh aturan sederhana.

## Rekomendasi

| Peran | Model | Kapan dipakai |
| --- | --- | --- |
| Default (klasifikasi rutin) | DeepSeek V4.1 Flash (`deepseek-flash`) | Semua pesan masuk — volume tinggi, tugas sederhana, harus murah/cepat |
| Eskalasi | Claude Haiku 4.5 | Pesan ambigu/berpotensi scam, atau perintah admin bebas dari Telegram yang bukan slash command tetap |

DeepSeek sudah punya adapter kode siap pakai (`app/providers/deepseek.py`),
jadi ini yang paling praktis untuk dipasang duluan. Claude Haiku 4.5 untuk
eskalasi masih perlu adapter baru ditulis dulu (belum ada `app/providers/anthropic.py`)
sebelum benar-benar bisa dipakai — jadi ini rekomendasi untuk tahap
berikutnya, bukan sesuatu yang tinggal diaktifkan hari ini.

## Harga (per 19 September 2026)

**DeepSeek V4.1 Flash** (`deepseek-flash`) — sumber: agregator pihak ketiga
(`benchlm.ai`), halaman resmi DeepSeek tidak bisa diverifikasi otomatis
karena render JS. Cek `https://api-docs.deepseek.com/quick_start/pricing`
langsung sebelum menganggarkan serius.
- Cache-miss input: $0.30/juta token (jam sibuk) / $0.15/juta (luar jam sibuk)
- Cache-hit input: $0.006/juta (jam sibuk) / $0.003/juta (luar jam sibuk)
- Output: $1.20/juta (jam sibuk) / $0.60/juta (luar jam sibuk)
- Jam sibuk (UTC): 01:00-04:00 dan 06:00-10:00, Senin-Jumat. Di luar itu =
  harga luar jam sibuk (separuh harga jam sibuk).

**Claude Haiku 4.5** — sumber resmi
(`https://platform.claude.com/docs/en/about-claude/pricing`):
- Input: $1/juta token (cache hit $0.10/juta; cache write 5 menit $1.25/juta,
  cache write 1 jam $2/juta)
- Output: $5/juta token

## Estimasi biaya bulanan (asumsi kasar)

Asumsi: ~100 pesan pelanggan/hari, sebagian besar ditangani DeepSeek Flash
(pesan pendek, klasifikasi ringan), sebagian kecil (~5%) eskalasi ke Claude
Haiku. Dengan volume segini, biaya diperkirakan **jauh di bawah $1-2/bulan**
— nyaman di dalam `MONTHLY_API_BUDGET_USD=20` yang sudah dikonfigurasi. Ini
perkiraan kasar, sesuaikan setelah ada data pemakaian nyata.

## Variabel `.env` terkait (referensi, belum untuk diisi sekarang)

- `DEEPSEEK_API_KEY`, `DEEPSEEK_MODEL` (default `deepseek-flash`),
  `DEEPSEEK_BASE_URL` — sudah ada di `config/.env.example`.
- `ANTHROPIC_API_KEY`, `ANTHROPIC_MODEL` — sudah ada tempatnya di
  `config/.env.example` (masih kosong), tapi butuh adapter kode baru dulu
  sebelum benar-benar berfungsi (lihat catatan di atas).

Langkah pengisian/konfigurasi akan dibahas terpisah.
