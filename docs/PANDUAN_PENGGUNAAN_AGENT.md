# Panduan Penggunaan AI Agent — v0.1

Dokumen ini menjelaskan **cara sehari-hari memakai** kelima AI agent yang sudah
dibangun: menjalankan runtime-nya, perintah apa saja yang tersedia, dan alur
kerja dasarnya. Untuk pertanyaan "provider AI mana + berapa harganya untuk
tiap agent", lihat file terpisah di `docs/providers/`. Langkah konfigurasi
detail (isi `.env`, daftar API key, dsb.) akan dibahas terpisah — dokumen ini
fokus pada **pemakaian**, bukan setup awal.

## Ringkasan lima agent

| Agent | Nama | Peran | Siapa yang berinteraksi |
| --- | --- | --- | --- |
| Lead Agent | **Taqi** | Router awal pelanggan (WhatsApp), pengatur alur, sekaligus panel command owner (Telegram) | Pelanggan (sapaan awal) + Owner (semua command admin) |
| Document Agent | **Nara** | Menyusun makalah/dokumen akademik bareng pelanggan (Taqi Desk) | Pelanggan |
| Finance Agent | **Laras** | Pencatatan transaksi, saldo, ringkasan keuangan | Owner saja (internal) |
| Social Media Agent | **Kirana** | Content Studio: draf ide & caption media sosial | Owner saja (internal, lewat command) |
| Desktop Agent | **Dimas** | Otomasi file lokal dasar (folder pesanan, buka file) | Owner saja (internal, sangat awal/belum ada AI) |

Detail kepribadian dan batasan tiap agent ada di `agents/<nama_agent>.md`
masing-masing (mis. `agents/social_media_agent.md`).

## 1. Menjalankan runtime

Semua runtime dijalankan lewat file `.bat` di folder utama (Windows):

- `JALANKAN_TELEGRAM.bat` — menjalankan Telegram Admin (Taqi + Laras + Nara +
  Kirana, semua lewat command Telegram). Ini yang paling sering dipakai
  sehari-hari.
- `CEK_TELEGRAM.bat` — cek cepat apakah token/koneksi Telegram sudah benar
  sebelum menjalankan bot sungguhan.
- `JALANKAN_WHATSAPP.bat` — menjalankan webhook WhatsApp Customer (jalur
  pelanggan asli lewat Taqi -> Nara). Ini proses OS terpisah dari Telegram,
  tapi berbagi database yang sama (`DATABASE_PATH`), jadi kill switch/price
  list/dll otomatis sinkron di kedua jalur.
- `CEK_WHATSAPP.bat` — cek konfigurasi WhatsApp sebelum menjalankan webhook
  sungguhan.
- `JALANKAN_WEB_ADMIN.bat` — panel admin berbasis web (alternatif Telegram
  untuk command owner).
- `TEMUKAN_TELEGRAM_ID.bat` — bantu cari `TELEGRAM_ADMIN_USER_ID`/`CHAT_ID`
  saat setup awal bot.
- `jalankan.bat` — CLI dasar Dimas (Desktop Agent), lihat
  `docs/PANDUAN_WINDOWS.md` untuk detailnya (folder pesanan, buka file, belum
  pakai AI).

Panduan Telegram paling lengkap (instalasi, cek koneksi, contoh command awal)
ada di `docs/telegram_admin_v1.md`.

## 2. Perintah Telegram Admin (Owner)

Kirim `/bantuan`, `/start`, atau `/help` ke bot untuk melihat daftar ini
langsung dari bot (isinya selalu sinkron dengan kode di `app/lead.py`):

### Status & sistem
- `/status` — cek sistem (Lead Agent, Document Agent, Finance, kill switch,
  dll aktif atau belum)
- `/dokumen_status` — cek Document Agent (Nara) secara spesifik
- `/dokumen_engine_status` — cek mesin pembuat DOCX/PDF lokal
- `/dokumen_demo` — buat DOCX/PDF demo tanpa memakai token AI (uji cepat mesin
  dokumen)
- `/sync_status` — status Google Sheets Sync
- `/sync` — sinkronkan ledger ke Google Sheets secara manual

### Keuangan (Laras)
- `/saldo` — saldo ledger per akun
- `/akun` — daftar akun dan saldo awal
- `/kategori` — kategori transaksi yang sudah dipelajari
- `/hari_ini [usaha]` — ringkasan transaksi hari ini, opsional filter satu usaha
  (mis. `/hari_ini Risol Mamqi`); tanpa argumen = semua usaha digabung
- `/minggu_ini [usaha]` — ringkasan minggu ini (Senin-Minggu)
- `/bulan_ini [usaha]` — ringkasan transaksi bulan ini
- `/laba_rugi [usaha]` — laba/rugi bulan ini: total pendapatan, rincian pengeluaran
  per kategori, dan laba/rugi bersih (pendapatan dikurangi seluruh pengeluaran
  tercatat — bukan laporan akuntansi formal)
- `/arus_kas [akun]` — saldo awal, total masuk, total keluar, dan saldo akhir bulan
  ini per akun (mis. `/arus_kas BCA`); tanpa argumen = semua akun aktif ditampilkan
- Ketik bebas untuk MENCATAT: `Catat pengeluaran 150 ribu beli tinta pakai BNI` —
  Laras akan memparsing dan mencatat otomatis
- Koreksi: `Koreksi transaksi terakhir, akun seharusnya BNI`
- **Tanya jawab bebas (BARU, 19 September 2026)** — tidak perlu command sama sekali,
  cukup tanya seperti mengobrol biasa, mis. "pemasukan bulan lalu Risol Mamqi
  berapa?", "untung bulan ini berapa?", "saldo BCA sekarang berapa?". Laras
  memakai AI hanya untuk memahami MAKSUD pertanyaannya (jenis laporan/periode/usaha/
  akun) — angka jawabannya selalu diambil langsung dari data asli, tidak pernah
  dikarang AI. Kalau pertanyaannya di luar yang bisa dijawab (mis. tren 12 bulan)
  atau AI sedang tidak bisa diandalkan, Laras akan bilang belum bisa menjawab
  otomatis, bukan menebak-nebak.

Belum ada: piutang/utang, tren 12 bulan, dan pencatatan otomatis dari foto struk
(masih di rencana, lihat `docs/finance_saas_v1.md`).

### Riset & dokumen akademik (Nara)
- `/research <topik>` — cari sumber akademik tanpa token AI
- `/research_status` — cek Research Manager
- `/research_save all` atau `/research_save 1,2,4-6` — simpan hasil riset
  sebagai referensi R1/R2/...
- `/sources` — lihat Source Registry sesi saat ini
- `/makalah <permintaan>` — bicara langsung dengan Nara dari sisi owner (mis.
  untuk uji coba)
- `/dokumen_baru` — reset konteks percakapan dokumen (mulai sesi baru)

### Kill switch & kontrol otomatis
- `/matikan_otomatis [whatsapp] <alasan>` — hentikan proses otomatis balasan
  ke pelanggan (dipakai saat mau menjawab manual dulu)
- `/nyalakan_otomatis [whatsapp]` — nyalakan kembali
- `/status_otomatis` — cek status kill switch saat ini

### Harga & status pesanan
- `/harga_set <layanan> | <harga> | <catatan opsional>` — simpan/ubah harga
  layanan (dipakai Taqi/Nara agar tidak mengarang harga ke pelanggan)
- `/harga_hapus <layanan>` — hapus harga layanan
- `/harga_list` — lihat semua harga tersimpan
- `/status_set <nomor_wa> <order_id> | <status>` — catat status pesanan
  pelanggan tertentu
- `/status_lihat <nomor_wa>` — lihat riwayat status order pelanggan tsb

### Content Studio (Kirana)
- `/konten_baru <usaha> | <platform> | <brief>` — minta Kirana membuat draf
  ide + caption. Contoh: `/konten_baru Risol Mamqi | instagram | promo
  weekend, tema ceria`. Hasilnya SELALU berupa draf yang perlu ditinjau/edit
  dulu — belum ada auto-publish ke media sosial.

### Evaluasi kualitas (Fase 5)
- `/eval_sample [agent] [n]` — ambil sampel interaksi produksi (default 5)
  untuk ditinjau kualitasnya. Contoh: `/eval_sample taqi 10`
- `/eval_tandai <id> | <baik/perlu_perbaikan/tidak_baik> | <catatan opsional>`
  — catat hasil tinjauan satu interaksi
- `/eval_status [agent]` — ringkasan tren kualitas dari semua tinjauan yang
  sudah dicatat

## 3. Alur pelanggan (WhatsApp)

1. Pelanggan mengirim pesan ke nomor WhatsApp bisnis.
2. **Taqi** (Lead Agent) menerima dulu — memeriksa kill switch, lalu
   melakukan routing awal (menyapa, menentukan kebutuhan pelanggan termasuk
   apakah ini permintaan dokumen akademik).
3. Jika kebutuhan berupa dokumen akademik, Taqi mengalihkan sesi ke **Nara**
   (Document Agent), yang lanjut mengumpulkan brief, membuat kerangka, revisi,
   sampai dokumen jadi (lihat `agents/document_agent.md` untuk gaya
   percakapan Nara).
4. Semua interaksi pelanggan otomatis tercatat di Interaction Log untuk
   ditinjau lewat `/eval_sample` (lihat bagian Evaluasi di atas).

Owner bisa memantau/menghentikan proses otomatis ini kapan saja lewat
`/matikan_otomatis` bila ingin menjawab manual.

## 4. Mengedit Brand Profile (untuk Kirana)

File `brand_profiles/<nama_usaha>.md` (mis. `brand_profiles/risol_mamqi.md`)
berisi tone of voice, target audiens, larangan tema/kata, dan contoh caption
untuk tiap usaha. Kirana **tidak akan membuat draf** untuk usaha yang brand
profile-nya belum lengkap (lihat Skenario 2 di
`eval/scenarios/social_media_agent.md`).

Cara mengedit: buka file `.md` yang sesuai dengan editor teks biasa (Notepad,
VS Code, dll), isi/ubah bagian yang relevan mengikuti format
`brand_profiles/BRAND_PROFILE_TEMPLATE.md`, simpan. Tidak perlu restart
runtime — file dibaca ulang setiap kali `/konten_baru` dipanggil.

## 5. Provider AI & harga

Setiap agent butuh provider AI yang berbeda (atau tidak butuh sama sekali,
untuk Dimas). Rincian rekomendasi provider, model, dan harga per agent ada di
file terpisah:

- `docs/providers/taqi.md`
- `docs/providers/nara.md`
- `docs/providers/laras.md`
- `docs/providers/kirana.md`
- `docs/providers/dimas.md`

Langkah konfigurasi (isi API key di `.env`, dll) akan dibahas terpisah — file
di atas hanya menjelaskan **provider mana + kenapa + berapa harganya**, plus
nama variabel `.env` untuk referensi nanti.

## 6. Uji otomatis (opsional, untuk developer/verifikasi)

Semua perubahan kode di repo ini dijaga oleh test suite:

```powershell
py -3 -m unittest discover -s tests -v
```

Ini tidak wajib dijalankan untuk pemakaian sehari-hari — berguna kalau ada
perubahan kode dan ingin memastikan tidak ada yang rusak.

## Status dokumen

v0.1 — dibuat 19 September 2026. Perintah dan alur di atas mengikuti kode
`app/lead.py` per tanggal ini; kalau ada command baru yang ditambahkan nanti,
jalankan `/bantuan` di bot untuk daftar paling akurat dan update dokumen ini
menyusul.
