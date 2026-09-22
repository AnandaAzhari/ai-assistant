# AI Assistant — Taqi

Asisten untuk operasional usaha dan kebutuhan pribadi: dokumen akademik, pencatatan keuangan, pengelolaan pelanggan, dan draft konten. Owner memakai **Telegram Admin atau Web Admin**; pelanggan dilayani melalui **WhatsApp Business Platform Cloud API**.

Aplikasi dan penyimpanan dapat berjalan di komputer sendiri atau server. Pemahaman bahasa dan pembuatan teks memakai **DeepSeek API**. Runtime saat ini ditulis dengan Python standard library, **tanpa LangChain dan tanpa model lokal/Ollama**.

README ini merangkum implementasi pada **20 September 2026**, termasuk Customer Book, kompresi PDF, dan pengiriman DOCX + PDF ke WhatsApp. Ketersediaan kode tidak berarti layanan eksternal sudah dikonfigurasi atau diuji pada setiap mesin.

## Agen dan kemampuan saat ini

| Agen | Peran | Implementasi |
| --- | --- | --- |
| **Taqi** | Lead Agent | Memahami intent pelanggan WhatsApp dengan AI, lalu mengarahkan ke layanan. Router admin masih menggunakan perintah dan kata kunci; AI belum menggantikan seluruh routing. |
| **Nara** | Document Agent | Memahami brief dan data cover, mengusulkan fokus/kerangka, menerima persetujuan atau revisi, mencari sumber, membuat draft, lalu DOCX/PDF. Fokus alur yang tersedia adalah makalah. |
| **Laras** | Finance Agent | Mencatat pemasukan/pengeluaran, saldo awal, kategori, koreksi akun, serta laporan per usaha/akun. AI memahami pertanyaan laporan; angka dihitung dari SQLite. |
| **Kirana** | Social Media Agent | Membuat alternatif caption berdasarkan brief, profil brand, dan pola koreksi tersimpan. Hasil berupa draft untuk ditinjau owner. |
| **Dimas** | Desktop Agent | CLI Windows untuk membuat folder dan meminta Windows membuka file di dalam workspace. Belum menggunakan AI. |

Nama usaha saat ini **Taqi Desk**; nama lama **Taqi DocuTech** masih dikenali sebagai alias pada keuangan. Integrasi dengan aplikasi terpisah [taqi-desk](https://github.com/AnandaAzhari/taqi-desk) belum diaktifkan.

Otomatisasi pelanggan saat ini ditujukan untuk **Taqi Desk/Nara**. Risol Mamqi serta Pixiva.ID/servis komputer tetap dibalas manual sesuai [keputusan channel per usaha](docs/multi_business_channels_v1.md). Pencatatan keuangan dan draft konten untuk usaha tersebut tetap dapat digunakan oleh owner.

## Arsitektur dan prinsip AI-first

| Jalur | Entry point | Tugas |
| --- | --- | --- |
| Telegram Admin | [telegram_main.py](telegram_main.py) | Polling chat pribadi owner; perintah admin, keuangan, Nara, dan Kirana. |
| Web Admin | [app/web_admin.py](app/web_admin.py) | Chat admin di browser, status, input suara dan pembacaan jawaban bila didukung browser. |
| WhatsApp pelanggan | [whatsapp_main.py](whatsapp_main.py) | Webhook pelanggan, intent AI, sesi Nara per pelanggan, penerimaan lampiran dan pengiriman file. |
| CLI desktop | [main.py](main.py) | Operasi folder/file terbatas melalui Dimas di Windows. |

Telegram dan Web Admin memakai [runtime admin bersama](app/admin_runtime.py). WhatsApp memakai runtime tersendiri; semua perlu menunjuk ke **database SQLite yang sama** agar harga, status order, profil pelanggan, dan kill switch konsisten. Sesi dokumen Telegram, Web Admin, dan masing-masing pelanggan WhatsApp memiliki scope terpisah.

AI-first berarti AI memahami bahasa pelanggan terlebih dahulu pada jalur yang sudah mendukungnya. Python memvalidasi keluaran, menjaga fase pekerjaan, menyimpan data, menghitung laporan, dan menjalankan alat. Sebagian jalur masih memiliki parser atau fallback deterministik ketika AI tidak tersedia atau jawabannya tidak valid.

### Persona, skill, dan memory

- [agents/](agents/) mendefinisikan nama, karakter, peran, dan batas tiap agen.
- Nara benar-benar memuat [persona](agents/document_agent.md), [skill percakapan](skills/document_academic/CONVERSATION.md), serta policy/skill akademik ke prompt.
- [skills/document_academic/](skills/document_academic/) dan [policies/](policies/) memuat pedoman brief, cover, struktur, format, serta sitasi. Sebagian policy ditegakkan melalui kode; keberadaan file Markdown saja tidak mengaktifkan fitur.
- Kirana membaca [brand_profiles/](brand_profiles/) dan pola koreksi berulang dari penyimpanan feedback.
- SQLite menyimpan state dokumen, preferensi, ledger, data pelanggan, serta log interaksi/evaluasi. Penyimpanan feedback dan performa konten tersedia, tetapi seluruh alur pengisian feedback melalui UI belum lengkap.

“Belajar” di sini adalah memakai konteks, kategori, dan koreksi yang disimpan. Sistem **belum melatih ulang model secara otomatis** dari semua chat pelanggan. Tidak semua file persona agen sudah dimuat otomatis oleh runtime.

## Mulai di Windows

### 1. Siapkan proyek

Gunakan **Python 3.11+** dan jalankan perintah dari folder proyek. Untuk checkout baru:

```powershell
git clone https://github.com/AnandaAzhari/ai-assistant.git
cd ai-assistant
py -3 --version
```

Untuk instalasi yang sudah ada, ambil pembaruan dengan `git pull --ff-only` setelah menyimpan perubahan lokal. Pertahankan konfigurasi dan database yang sudah dipakai.

Runtime utama tidak membutuhkan paket Python tambahan. Aplikasi eksternal untuk PDF dan paket pengujian dijelaskan di bawah.

### 2. Konfigurasi lokal

Salin template **hanya jika belum memiliki konfigurasi**:

```powershell
if (-not (Test-Path .env)) { Copy-Item config/.env.example .env }
notepad .env
```

Konfigurasi dasar Nara/Kirana dan pertanyaan AI Laras:

```dotenv
DATABASE_PATH=data/assistant.db
DEEPSEEK_API_KEY=ISI_DI_KOMPUTER_SENDIRI
DEEPSEEK_MODEL=deepseek-flash
DEEPSEEK_BASE_URL=https://api.deepseek.com
DOCUMENT_WORKSPACE=workspace/documents
```

`deepseek-flash` adalah nilai default dalam kode; akses model dan saldo harus sesuai akun provider yang digunakan. Simpan key/token hanya pada konfigurasi lokal, bukan di chat, screenshot, atau GitHub. Nilai environment proses yang sudah ada didahulukan daripada file `.env`.

| Kebutuhan | Variabel |
| --- | --- |
| Telegram | `TELEGRAM_BOT_TOKEN`, `TELEGRAM_ADMIN_USER_ID`, `TELEGRAM_ADMIN_CHAT_ID` |
| WhatsApp | `WHATSAPP_API_TOKEN`, `WHATSAPP_PHONE_NUMBER_ID`, `WHATSAPP_WEBHOOK_VERIFY_TOKEN`, `WHATSAPP_APP_SECRET` |
| Google Sheets | `GOOGLE_SHEETS_WEBHOOK_URL`, `GOOGLE_SHEETS_SYNC_SECRET` |
| Riset | `OPENALEX_API_KEY`, `CROSSREF_MAILTO`, `RESEARCH_HTTP_TIMEOUT` |
| Lokasi file | `DOCUMENT_WORKSPACE`, `ATTACHMENT_QUARANTINE_DIR`, `PDF_COMPRESS_WORKSPACE` |
| Kunci Web Admin opsional | `WEB_ADMIN_KEY` |

Lihat [template konfigurasi](config/.env.example). `PDF_COMPRESS_WORKSPACE` dan `WEB_ADMIN_KEY` didukung kode tetapi belum dicantumkan dalam template. Untuk lokasi kompresi dan karantina, gunakan path absolut pada mesin yang menjalankan layanan agar tidak bergantung pada direktori kerja proses eksternal.

**Provider yang terhubung baru DeepSeek.** Variabel Anthropic/OpenAI/Gemini dalam template merupakan persiapan; mengisinya saja belum mengaktifkan provider tersebut. Pemilihan provider berbeda per agen, Kimi, dan Ollama masih membutuhkan implementasi. Variabel `DAILY_API_BUDGET_USD` dan `MONTHLY_API_BUDGET_USD` juga **belum menjadi pembatas biaya yang ditegakkan runtime**.

### 3. Jalankan Telegram Admin

1. Isi token bot yang sudah dimiliki pada `TELEGRAM_BOT_TOKEN`.
2. Jika ID owner belum tersedia, jalankan `TEMUKAN_TELEGRAM_ID.bat`, kirim kode pairing yang ditampilkan ke chat pribadi bot, lalu salin ID hasilnya ke konfigurasi lokal.
3. Jalankan `CEK_TELEGRAM.bat`.
4. Jalankan `JALANKAN_TELEGRAM.bat`, kemudian kirim `/status` dan `/bantuan` ke bot.

Alternatif terminal:

```powershell
py -3 telegram_main.py --check
py -3 telegram_main.py
```

`--check` memeriksa koneksi bot dan konfigurasi; tidak menguji panggilan AI atau kecocokan owner melalui pesan masuk. Saat berjalan, hanya user ID dan chat pribadi yang diizinkan yang diproses.

Runtime menyimpan jurnal update/balasan ke SQLite dan membatasi proses polling ganda pada checkout yang sama. Jika pekerjaan terputus sebelum hasilnya pasti, periksa status dahulu sebelum mengirim ulang tindakan.

### 4. Autostart Telegram

| File | Fungsi |
| --- | --- |
| `SETUP_AUTOSTART_TELEGRAM.bat` | Mendaftarkan task `TaqiAI_TelegramBot` agar berjalan saat **login Windows**. |
| `JALANKAN_TELEGRAM_HIDDEN.vbs` | Menjalankan bot tanpa jendela terminal. |
| `JALANKAN_TELEGRAM_BACKGROUND.bat` | Menulis output proses ke `logs/telegram_background.log`. |
| `HENTIKAN_TELEGRAM_BACKGROUND.bat` | Menghentikan proses dengan command line `telegram_main.py`; cakupannya tidak terbatas pada satu checkout. |
| `HAPUS_AUTOSTART_TELEGRAM.bat` | Menghapus pendaftaran task autostart. |

PC tetap perlu menyala, terhubung internet, dan tidak tidur. Autostart ini bukan layanan hosting ketika PC mati, serta belum menyediakan pemulihan otomatis setelah proses crash. Gunakan satu runtime bot aktif; jika sudah memakai server lain, jangan menyalakan polling bot yang sama di PC.

### 5. Jalankan Web Admin

Klik `JALANKAN_WEB_ADMIN.bat`, lalu buka [http://localhost:8081](http://localhost:8081).

Peluncur bawaan memakai `127.0.0.1:8081`. Web Admin memiliki manifest/service worker dasar; pemrosesan AI tetap memerlukan backend dan internet. Speech recognition serta text-to-speech bergantung browser, bukan jaminan pemrosesan suara lokal/offline.

`WEB_ADMIN_KEY` dapat melindungi endpoint API dengan header `X-Admin-Key`, tetapi UI bawaan belum menyediakan input/pengiriman key tersebut. Mengaktifkannya memerlukan penyesuaian client agar chat UI tetap dapat mengakses API. Belum ada peluncur LAN/HTTPS siap pakai; pengaturan akses tablet atau internet perlu ditangani tersendiri.

## WhatsApp pelanggan

Adapter memakai **Meta Cloud API**, terpisah dari bot Telegram. Satu runtime dikonfigurasi untuk satu `WHATSAPP_PHONE_NUMBER_ID`; routing beberapa nomor usaha belum tersedia.

Isi empat variabel WhatsApp pada tabel konfigurasi, lalu jalankan:

```powershell
py -3 whatsapp_main.py --check
py -3 whatsapp_main.py --host 127.0.0.1 --port 8443
```

Di Windows tersedia `CEK_WHATSAPP.bat` dan `JALANKAN_WHATSAPP.bat`. Mode `--check` memeriksa konfigurasi dan komponen lokal, **bukan verifikasi token atau pengiriman pesan nyata ke Meta**.

Arahkan endpoint HTTPS publik ke `/webhook` melalui reverse proxy atau tunnel. Server Python sendiri melayani HTTP; port `8443` tidak otomatis mengaktifkan TLS. Gunakan argumen `--host`/`--port` untuk mengubah bind secara eksplisit.

Webhook memvalidasi challenge GET dan tanda tangan POST sebelum memproses JSON. Jalur pelanggan memakai trust/spam checks, pembatasan command admin, pemeriksaan topik, serta Approval Gate. Lampiran diunduh melalui adapter, diklasifikasikan, dan disimpan ke karantina; pemeriksaan dasar ini belum merupakan pemindaian malware penuh.

## Alur Nara: brief sampai file

1. Pelanggan menyampaikan kebutuhan: jenjang, kelas/semester, mata pelajaran, topik, target halaman, dan ketentuan.
2. Nara menampilkan ringkasan, usulan fokus bila diperlukan, serta kerangka.
3. Pelanggan menyetujui atau meminta revisi dengan bahasa biasa. Fokus usulan baru menjadi keputusan setelah persetujuan.
4. Data cover dilengkapi; beberapa field boleh dikirim sekaligus.
5. AI menyusun kueri riset; Research Manager mencari kandidat melalui OpenAlex/Crossref. Sumber terpilih disimpan dalam Source Registry.
6. Draft dibuat menggunakan sumber terdaftar dan diperiksa penanda sitasinya.
7. Setelah diminta melanjutkan ke file, Document Engine/Citation Engine membuat DOCX, catatan kaki, daftar pustaka, dan PDF bila converter tersedia.

Contoh awal di Telegram/Web Admin:

```text
/makalah Saya ingin makalah tentang AI Agent, 8 halaman, untuk SMK kelas XII semester 1, pelajaran Informatika, tanpa Ibid.
```

Riset otomatis saat ini menilai **metadata dan abstrak**, belum memverifikasi teks penuh setiap sumber. Target halaman tetap perlu dicek dari hasil render. Policy KTI/skripsi sudah tersedia, tetapi bukan jaminan seluruh alur penelitian atau pedoman kampus telah ditangani.

Jika sumber belum cukup atau layanan gagal, draft dapat tertahan dengan alasan yang ditampilkan. Periksa pesan tersebut; kegagalan riset tidak selalu berarti persetujuan kerangka ditolak.

### DOCX, PDF, dan kompresi

| Hasil | Kebutuhan |
| --- | --- |
| DOCX | Dibuat langsung sebagai Open XML oleh Python; tidak membutuhkan Word untuk pembuatan file. |
| PDF di Windows | Microsoft Word desktop melalui COM/PowerShell. |
| PDF di Linux/non-Windows | LibreOffice headless, ditemukan sebagai `soffice` atau `libreoffice` di PATH. |
| Kompresi PDF | Ghostscript di PATH: `gs`, `gswin64c`, atau `gswin32c`. |

Pada Ubuntu/Debian, kebutuhan PDF dapat dipasang dengan:

```bash
sudo apt install libreoffice ghostscript
```

Jika konversi PDF gagal, DOCX tetap tersedia disertai keterangan. Jalur **WhatsApp** mengunggah dan mengirim DOCX serta PDF yang berhasil dibuat. **Telegram/Web Admin saat ini memberikan balasan teks dan lokasi file lokal**, belum mengirim lampiran dokumen otomatis.

Pelanggan WhatsApp dapat mengirim PDF dan menyebut target seperti `kompres jadi 500 KB`. Jika ukuran belum disebutkan, sistem memintanya. Kompresi mencoba beberapa preset dan melaporkan bila target tidak tercapai; kualitas gambar dapat turun. Periksa kesiapan melalui `/kompres_pdf_status`. Permintaan kompresi yang masih menunggu ukuran disimpan dalam memori proses, belum dipulihkan setelah restart.

## Keuangan, pelanggan, dan konten

### Laras: pencatatan per usaha dan akun

Unit pencatatan: **Taqi Desk, Pixiva.ID, Computer Service, Risol Mamqi, dan Personal**. Akun yang tersedia: Cash, BCA, BNI, SeaBank, Jago, QRIS, DANA, GoPay, dan ShopeePay.

```text
Catat pengeluaran 80 ribu beli tinta untuk Taqi Desk pakai BCA
/bulan_ini Risol Mamqi
/laba_rugi Taqi Desk
/arus_kas BCA
Pemasukan bulan lalu Risol Mamqi berapa?
Koreksi transaksi terakhir, akun seharusnya BNI
```

Pencatatan transaksi masih menggunakan parser deterministik. Koreksi akun menyimpan jejak transaksi lama sebagai reversed dan membuat penggantinya. Saldo adalah **saldo ledger dari catatan**, bukan saldo bank yang diambil otomatis. Laba/rugi masih berupa pendapatan dikurangi pengeluaran tercatat.

Google Sheets menjadi mirror satu arah untuk transaksi, akun, dan kategori melalui Apps Script. SQLite tetap sumber utama. Auto-sync dipanggil setelah perubahan keuangan berhasil; `/sync` tersedia untuk pengulangan manual. Lihat [setup Google Sheets](docs/google_sheets_webhook_setup.md).

### Customer Book dan status pesanan

Kontak masuk mencatat identitas pengirim, waktu kontak, dan jumlah kontak. Nama/bisnis serta order terstruktur diisi admin:

```text
/pelanggan_nama 628111222333 | Budi | Taqi Desk
/pelanggan_catat 628111222333 Taqi Desk | Makalah dan cetak | 50000
/pelanggan_riwayat 628111222333
/pelanggan_ringkasan Taqi Desk
/status_set 628111222333 ORD-001 | Menunggu review pelanggan
```

Nomor di atas hanya contoh. Customer Book, status antrean, dan ledger keuangan merupakan catatan berbeda. **Mencatat order tidak otomatis mencatat pemasukan atau memastikan pembayaran diterima.** Ringkasan nominal order juga bukan bukti uang telah masuk.

### Kirana: draft caption

```text
/konten_baru Risol Mamqi | instagram | Perkenalkan varian ayam pedas dengan bahasa hangat
```

Lengkapi profil brand terlebih dahulu. Runtime membaca ulang file profil saat membuat draft. Kirana belum menerbitkan konten, menjadwalkan posting, atau menarik analytics media sosial secara otomatis.

## Perintah admin utama

Ketik `/bantuan` untuk daftar yang berasal langsung dari runtime.

| Kebutuhan | Perintah |
| --- | --- |
| Status | `/status`, `/dokumen_status`, `/dokumen_engine_status`, `/kompres_pdf_status` |
| Keuangan | `/saldo`, `/akun`, `/kategori`, `/hari_ini [usaha]`, `/minggu_ini [usaha]`, `/bulan_ini [usaha]`, `/laba_rugi [usaha]`, `/arus_kas [akun]` |
| Dokumen/riset | `/makalah <permintaan>`, `/dokumen_baru`, `/dokumen_demo`, `/research <topik>`, `/research_status`, `/research_save all`, `/sources` |
| Harga | `/harga_set <layanan> \| <harga> \| <catatan>`, `/harga_list`, `/harga_hapus <layanan>` |
| Status order | `/status_set <nomor_wa> <order_id> \| <status>`, `/status_lihat <nomor_wa>` |
| Pelanggan | `/pelanggan_nama`, `/pelanggan_catat`, `/pelanggan_riwayat`, `/pelanggan_ringkasan` dengan format contoh di atas |
| Konten | `/konten_baru <usaha> \| <platform> \| <brief>` |
| Sinkronisasi | `/sync_status`, `/sync` |
| Kontrol otomatis | `/matikan_otomatis [whatsapp] <alasan>`, `/nyalakan_otomatis [whatsapp]`, `/status_otomatis` |
| Evaluasi | `/eval_sample [agent] [n]`, `/eval_tandai <id> \| <baik/perlu_perbaikan/tidak_baik> \| <catatan>`, `/eval_status [agent]` |

Kill switch menghentikan alur otomatis pelanggan dan dapat menghasilkan pesan pemberitahuan; bukan menghentikan proses server. Pemeriksaan lampiran pada adapter berlangsung sebelum routing Lead.

## Batas implementasi dan pekerjaan berikutnya

- **Persetujuan fokus Nara** sudah menjadi bagian alur dokumen. **Approval Gate admin** menyimpan keputusan/pending request, tetapi notifikasi owner, command `/approve`/`/reject`, dan eksekusi lanjutan belum tersambung lengkap ke runtime admin.
- Pemilihan provider/model per agen dan integrasi Gemini/Claude/OpenAI/Kimi/Ollama belum tersedia.
- Integrasi order/antrean dengan aplikasi TaqiDesk, routing beberapa nomor WhatsApp, dan Discord masih rencana.
- OCR struk, piutang/utang, tren keuangan 12 bulan, serta transaksi bank otomatis belum tersedia.
- Content Calendar, penerbitan konten, pembuatan visual, dan analytics otomatis masih rencana.
- WhatsApp belum memiliki jurnal pengiriman/recovery persisten seperti Telegram; retry webhook dan kegagalan pengiriman belum ditangani sebagai antrean pekerjaan tahan restart.
- Scanner malware eksternal belum disambungkan. Pemeriksaan ekstensi, aturan topik, dan validasi keluaran AI tetap memiliki keterbatasan.
- Pesan status “siap” umumnya menunjukkan konfigurasi/komponen tersedia, bukan bukti seluruh layanan eksternal telah lulus uji langsung.

## Data dan struktur proyek

| Lokasi | Isi |
| --- | --- |
| [app/](app/) | Routing, layanan agen, penyimpanan, adapter channel, dan alat dokumen. |
| [app/providers/](app/providers/) | Interface provider dan implementasi DeepSeek. |
| [agents/](agents/), [skills/](skills/), [policies/](policies/) | Persona, skill, dan aturan. |
| [brand_profiles/](brand_profiles/) | Profil usaha untuk konten. |
| [web_admin/](web_admin/) | UI browser, voice, dan aset PWA. |
| [integrations/google_sheets/](integrations/google_sheets/) | Apps Script mirror keuangan. |
| [config/.env.example](config/.env.example) | Template konfigurasi tanpa secret. |
| [tests/](tests/), [eval/scenarios/](eval/scenarios/) | Tes otomatis dan skenario review kualitas. |
| [docs/](docs/) | Panduan, keputusan arsitektur, dan roadmap. |
| `data/assistant.db` | Default database runtime; tidak masuk Git. |
| `workspace/documents/`, `workspace/pdf_compressed/` | Default hasil dokumen dan kompresi. |
| `data/quarantine/`, `logs/` | Default karantina lampiran dan log runtime. |

Cadangkan database dan hasil kerja sebelum memindahkan mesin atau melakukan perubahan besar. Konfigurasi lokal, database, lampiran, dan log tidak ikut Git. Log interaksi memuat input/output percakapan untuk evaluasi; perlakukan sebagai data pelanggan.

Dokumen lanjutan:

- [Panduan penggunaan agen](docs/PANDUAN_PENGGUNAAN_AGENT.md)
- [Telegram dan autostart](docs/telegram_admin_v1.md)
- [CLI Windows/Dimas](docs/PANDUAN_WINDOWS.md)
- [Outline UX v2, Focus Approval, riset dan draft](docs/outline_ux_v2_research_draft.md)
- [Arsitektur](docs/core_architecture.md) dan [memory](docs/agent_memory_v1.md)
- [Roadmap channel pelanggan](docs/roadmap_customer_channel_v1.md)
- [Keuangan](docs/finance_saas_v1.md) dan [konten sosial](docs/social_media_v1.md)
- [Keamanan](policies/security_policy.md) dan [kebijakan approval](policies/approval_policy.md)
- [Rencana provider per agen](docs/providers/)

Beberapa dokumen memuat rancangan atau checkpoint lama. Untuk status operasional, cocokkan dengan implementasi dan batas pada README ini. Angka harga dalam catatan provider perlu diperiksa kembali sebelum memilih paket.

## Pengujian

Suite berisi tes `unittest` dan tes fungsi/marker `pytest`; gunakan **pytest** untuk menjalankan keduanya:

```powershell
py -3 -m pip install pytest
py -3 -m pytest -q
```

Untuk tes kompresi PDF sungguhan, pasang Ghostscript serta paket pembuat PDF uji:

```powershell
py -3 -m pip install numpy Pillow reportlab
```

Tes konversi/kompresi eksternal memiliki kondisi skip sesuai alat yang tersedia. `unittest discover` saja tidak mengumpulkan semua tes fungsi dan tidak menerapkan marker pytest.

Tes menggunakan banyak provider/client pengganti. Hasilnya tidak membuktikan koneksi API nyata, pengiriman WhatsApp/Telegram, perilaku Word COM, tampilan browser, atau kualitas dokumen pada perangkat pengguna. Lakukan uji langsung terbatas setelah konfigurasi layanan.

### Checkpoint pemeriksaan README — 20 September 2026

Pada kode dasar [92a57fe](https://github.com/AnandaAzhari/ai-assistant/commit/92a57fe63782815455ce5c930c00fbc94689a5f6), `python -m pytest -q` di lingkungan Linux menghasilkan **574 passed, 1 failed**, serta **307 subtests passed**. Kegagalan berada pada `tests/test_document_engine.py::test_document_engine_builds_docx_without_ai`: assertion mencari `BAB I PENDAHULUAN` sebagai satu teks XML, sedangkan mesin memisahkan label bab dan judul dengan pergantian baris. Ketidaksesuaian tes ini masih perlu diselesaikan; pembaruan README tidak mengubah kode atau tes.
