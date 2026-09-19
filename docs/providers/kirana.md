# Provider AI & Harga — Kirana (Social Media Agent / Content Studio)

## Status kode saat ini

Kirana **sudah aktif memakai AI** lewat `DeepSeekProvider.from_env()` (lihat
`app/admin_runtime.py`) — provider AI yang SAMA PERSIS dengan Nara (satu
konfigurasi DeepSeek dipakai bersama untuk seluruh runtime admin saat ini).
Model default: `deepseek-flash`. Ini dipakai untuk brainstorming ide dan
draf caption di `app/content_studio.py`, dengan guardrail deterministik
(bukan AI) yang membuang caption yang mengarang harga.

## Kenapa Kirana cocok dengan model yang murah/cepat

Berbeda dari Nara (menulis dokumen panjang berbab-bab), tugas Kirana adalah
brainstorming ide dan caption pendek — cocok dengan model cepat/murah untuk
draf awal, dengan opsi "polish" pakai model lebih kuat untuk versi final
sebelum disetujui.

## Rekomendasi

| Peran | Model | Kapan dipakai |
| --- | --- | --- |
| Default (draf ide & caption) | Kimi K2.6/K2.7 (Moonshot) atau DeepSeek V4.1 Flash (`deepseek-flash`, sudah dipakai sekarang) | Brainstorming ide, draf caption awal |
| Eskalasi (polish) | Claude Sonnet 5 | Merapikan/mempertajam versi final sebelum disetujui owner |

**Catatan koreksi dari `docs/core_architecture.md`:** tabel di dokumen itu
masih menyebut "Kimi K2.5" dengan harga $0.60/$3.00 — nama model itu sudah
berganti ke K2.6/K2.7 dengan harga yang lebih tinggi (lihat di bawah).
DeepSeek Flash yang sudah berjalan sekarang tetap pilihan yang valid dan
lebih murah dari Kimi untuk draf awal; Kimi K2.6/K2.7 dan Claude Sonnet 5
keduanya masih butuh adapter kode baru sebelum bisa benar-benar dipasang
(belum ada `app/providers/moonshot.py` atau `app/providers/anthropic.py`).

## Harga (per 19 September 2026)

**DeepSeek V4.1 Flash** (sedang dipakai sekarang) — sumber: agregator
pihak ketiga (`benchlm.ai`), cek halaman resmi DeepSeek untuk konfirmasi:
- Cache-miss input: $0.30/juta (jam sibuk) / $0.15/juta (luar jam sibuk)
- Cache-hit input: $0.006/juta (jam sibuk) / $0.003/juta (luar jam sibuk)
- Output: $1.20/juta (jam sibuk) / $0.60/juta (luar jam sibuk)

**Kimi K2.6** (Moonshot) — sumber resmi
(`https://platform.kimi.ai/docs/pricing/chat.md`):
- Cache-hit: $0.16/juta token
- Cache-miss: $0.95/juta token
- Output: $4.00/juta token

**Kimi K2.7-Code** (Moonshot) — sumber resmi:
- Cache-hit: $0.19/juta token
- Cache-miss: $0.95/juta token
- Output: $4.00/juta token

**Claude Sonnet 5** — sumber resmi
(`https://platform.claude.com/docs/en/about-claude/pricing`):
- Input: $2/juta token (cache hit $0.20/juta)
- Output: $10/juta token

## Estimasi biaya bulanan (asumsi kasar)

Asumsi: ~60 pemanggilan draf/bulan (mis. 2x/hari untuk beberapa usaha
sekaligus), token per panggilan relatif kecil (brief + 3 alternatif
caption). Dengan DeepSeek Flash yang sedang dipakai sekarang, perkiraan
kasar **di bawah $1/bulan**. Menambah tahap "polish" dengan Claude Sonnet 5
untuk versi final saja (bukan semua draf) tetap membuat total masih nyaman
di dalam `MONTHLY_API_BUDGET_USD=20`.

## Variabel `.env` terkait (referensi, belum untuk diisi sekarang)

- `DEEPSEEK_API_KEY`, `DEEPSEEK_MODEL`, `DEEPSEEK_BASE_URL` — sudah ada dan
  sudah aktif dipakai.
- Belum ada variabel Kimi/Moonshot di `config/.env.example` sama sekali —
  perlu ditambahkan (mis. `MOONSHOT_API_KEY`) begitu adapter kodenya dibuat.
- `ANTHROPIC_API_KEY`, `ANTHROPIC_MODEL` — tempatnya sudah ada, butuh
  adapter kode baru.

Langkah pengisian/konfigurasi akan dibahas terpisah.
