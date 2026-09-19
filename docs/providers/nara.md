# Provider AI & Harga — Nara (Document Agent)

## Status kode saat ini

Nara **sudah aktif memakai AI** lewat `DeepSeekProvider.from_env()` (lihat
`app/admin_runtime.py`), dengan model default `deepseek-flash` (sesuai
`DEEPSEEK_MODEL` di `config/.env.example`). Ini dipakai untuk interpretasi
brief, penyusunan kerangka, dan penulisan isi makalah (`app/document_agent.py`,
`app/document_draft.py`, `app/document_intake.py`).

Catatan penting: model yang sama (`deepseek-flash`, tier termurah/tercepat)
saat ini dipakai untuk tugas menulis dokumen yang cukup kompleks — bukan
tier yang lebih kuat. Ini kemungkinan area untuk ditingkatkan begitu volume
pesanan bertambah dan kualitas tulisan jadi makin penting.

## Kenapa Nara butuh model yang lebih kuat

Menyusun makalah akademik (kerangka, isi berbab-bab, revisi mengikuti
koreksi pelanggan) adalah tugas yang jauh lebih kompleks dibanding
klasifikasi intent singkat ala Taqi. Kualitas tulisan, kemampuan mengikuti
instruksi panjang, dan konsistensi antar-revisi jadi lebih penting daripada
sekadar kecepatan/harga.

## Rekomendasi

| Peran | Model | Kapan dipakai |
| --- | --- | --- |
| Utama (kualitas terbaik) | Claude Sonnet 5 | Penyusunan kerangka & isi makalah — kualitas tulisan panjang paling diutamakan |
| Fallback (budget ketat) | DeepSeek V4 Pro (`deepseek-v4-pro`) | Saat budget API terbatas atau Claude tidak tersedia; masih jauh lebih kuat dari tier Flash saat ini |

Catatan implementasi: DeepSeek V4 Pro tinggal ganti nilai `DEEPSEEK_MODEL`
di `.env` (adapter kode sudah ada) — upgrade paling praktis dari kondisi
sekarang. Claude Sonnet 5 butuh adapter kode baru dulu
(`app/providers/anthropic.py` belum ada) sebelum bisa benar-benar dipasang.

## Harga (per 19 September 2026)

**Claude Sonnet 5** — sumber resmi
(`https://platform.claude.com/docs/en/about-claude/pricing`):
- Input: $2/juta token (cache hit $0.20/juta; cache write 5 menit $2.50/juta,
  cache write 1 jam $4/juta)
- Output: $10/juta token

**DeepSeek V4 Pro** (`deepseek-v4-pro`) — sumber: agregator pihak ketiga
(`benchlm.ai`), dengan catatan penting: halaman itu sendiri menyebut ada
selisih antara "nilai registry per 12 Agustus" ($0.435/juta input) dan
kemungkinan tarif jam sibuk yang lebih baru "per 17 September" ($1.32/juta
input, $3.96/juta output) yang belum sinkron di halaman mereka. Artinya
**angka DeepSeek Pro di bawah ini tidak sepenuhnya pasti** — cek
`https://api-docs.deepseek.com/quick_start/pricing` langsung sebelum
menganggarkan serius:
- Input (nilai registry): $0.435/juta token; cache-hit $0.003625/juta
- Output (nilai registry): $0.87/juta token
- Kemungkinan tarif jam sibuk lebih baru: ~$1.32/juta input / ~$3.96/juta
  output (belum terkonfirmasi resmi)

## Estimasi biaya bulanan (asumsi kasar)

Asumsi: ~30 dokumen/bulan, masing-masing ~20 pemanggilan AI (brief, kerangka,
revisi per bab, dst) dengan token sedang. Dengan Claude Sonnet 5, perkiraan
kasar sekitar **$8-10/bulan** — masih di dalam `MONTHLY_API_BUDGET_USD=20`
yang sudah ada, tapi ini agent dengan porsi budget terbesar dari kelima
agent. Dengan DeepSeek V4 Pro (fallback), biaya diperkirakan jauh lebih
murah tapi kualitas tulisan sedikit di bawah Claude Sonnet 5. Sesuaikan
setelah ada data pemakaian nyata.

## Variabel `.env` terkait (referensi, belum untuk diisi sekarang)

- `DEEPSEEK_API_KEY`, `DEEPSEEK_MODEL` (ganti ke `deepseek-v4-pro` untuk
  upgrade tanpa perubahan kode), `DEEPSEEK_BASE_URL`.
- `ANTHROPIC_API_KEY`, `ANTHROPIC_MODEL` — tempatnya sudah ada di
  `config/.env.example`, butuh adapter kode baru dulu.

Langkah pengisian/konfigurasi akan dibahas terpisah.
