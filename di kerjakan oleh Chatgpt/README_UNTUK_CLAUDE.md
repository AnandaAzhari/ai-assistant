# Serah terima prototipe pembayaran dan antrean kepada Claude

**Mulai dari `00_BACA_DULU_CLAUDE.md`.** Owner telah menyatakan hasil format
“sudah sesuai”. Seluruh 94 tes prototipe lulus pada tes ulang atas kode commit
`70771143c0ce8f6b9213a648f50c495e5559307b`; log, lingkungan, dan hash tersedia
di `bukti_uji/hasil_unit_test.json`. Persetujuan tersebut berlaku untuk tampilan
contoh, tidak membuktikan integrasi Nara/Telegram/pembayaran sungguhan.

Salinan pedoman lengkap ada di `referensi/`. Rencana berikutnya tersedia pada
`02_LANJUTAN_NARA_TELEGRAM.md`; file ini menjelaskan kontrak implementasinya.

## Keputusan dan batas pekerjaan owner

Owner meminta kode `.py` yang dapat dicoba dahulu dalam folder persis
`di kerjakan oleh Chatgpt`, sebelum diintegrasikan ke aplikasi sebenarnya.
Pada tahap prototipe ini semua perubahan dibatasi ke folder tersebut.
Harga masih usulan yang dapat diedit; instruksi mengerjakan demo tidak berarti
tarif ini sudah disahkan untuk pelanggan produksi.

Arahan lanjutan owner: **modul ini ditujukan untuk AI agent, dan owner cukup
mengecek DP/pelunasan melalui Telegram**. Demo terminal adalah alat pengujian;
produk akhirnya bukan aplikasi kasir terpisah yang wajib dibuka owner.

Jangan otomatis mengaktifkan kode ini pada runtime utama hanya karena foldernya
ada. Saat owner memberi perintah integrasi, perintah itu menjadi dasar untuk
mengubah bagian utama yang diperlukan. Periksa perubahan lokal owner/agen lain
dan versi repository terbaru sebelum mengedit; jangan menimpa pekerjaan mereka.

## Acuan repository saat dibuat

- Repository: `AnandaAzhari/ai-assistant`.
- Acuan awal harga/pembayaran: `f49aff17e764c9bc32e5be493c5038cf52dfe307`.
- Acuan penambahan antrean: `c1a96c25f08d2cfcf532db3023634c7951b5c37a`.
- Perbaikan format dimulai dari demo `be04efe2d165b9a2e7af198d20b9db8bc48c850d`.
- Main saat perbaikan format disiapkan: `2b58fd6b704dfc3d7f718f4be4cf59e84a3f5297`.
  Commit itu sudah menggabungkan payment gate utama. Semua perubahan dari pihak
  lain dipertahankan; pembaruan ini hanya menyentuh folder prototipe.
- `app/finance.py`: ledger keuangan lokal, belum rekonsiliasi bank atau gateway.
- `app/order_status.py`: status pesanan yang diisi admin.
- `app/customer_book.py`: catatan pelanggan/order yang berbeda dari ledger.
- `app/lead.py`: routing admin/pelanggan. Payment gate utama kini ada pada branch
  main terbaru; bandingkan `app/payment_gate.py` dan `app/pdf_watermark.py` sebelum
  menyatukan rancangan. Jangan membuat dua sumber kebenaran pembayaran.
- `whatsapp_main.py`: webhook khusus Meta; bukan endpoint pembayaran.
- `app/web_admin.py`: API admin; jangan membukanya tanpa autentikasi untuk gateway.
- `app/telegram.py`: `TelegramAdminAdapter`, `AdminIdentity`, pengiriman pesan,
  dan jurnal update/balasan yang perlu dipakai kembali saat integrasi.
- `app/admin_runtime.py`: `create_admin_lead()` menyusun layanan admin bersama.
- `app/document_agent.py`: `DocumentAgent.build_final()`, fase `draft_ready` /
  `final_ready`, serta properti `final_docx_path` dan `final_pdf_path`.

Periksa ulang file tersebut saat integrasi. Acuan di atas adalah checkpoint,
bukan klaim bahwa semua file akan selalu sama.

## Cara menjalankan dan bagian yang dapat dipakai

Python 3.11+. Harga/pembayaran memakai standard library. Pekerja format dan tes
format memerlukan `pypdf` dari `requirements_format.txt`. Di Windows, jalankan
`SIAPKAN_FORMAT.bat` dan gunakan peluncur `.bat`; peluncur memilih `.venv` otomatis.
Konversi PDF memakai Microsoft Word desktop. Untuk Linux pengembangan, pasang
requirements pada environment uji dan gunakan LibreOffice seperti engine proyek.
Dari folder ini, dengan interpreter environment tersebut:

```bash
python -B -m unittest discover -s tests -p 'test_*.py' -v
python -B demo.py --sample
python -B demo.py --telegram-demo
python -B workflow_demo.py --sample
python -B workflow_demo.py
```

- `chatgpt_billing/pricing.py` menghasilkan `Quote` immutable dengan rincian dan
  syarat pembayaran. Input uang berupa integer rupiah; tidak ada float.
- `make_quote(QuoteRequest(...))` membaca konfigurasi default relatif terhadap
  file modul, bukan current working directory. Objek config bisa diberikan eksplisit.
- `Quote.review_reasons` menunjukkan kasus yang memerlukan pemeriksaan operator.
- `DemoStore` menyimpan snapshot penawaran agar perubahan config tidak mengubah
  pesanan yang telah dibuat. Metode menerima `actor` untuk audit demo; identitas
  tersebut belum merupakan autentikasi. Pada produksi actor harus berasal dari
  identitas terverifikasi, bukan teks bebas pelanggan.
- `simulate_payment` sengaja hanya menerima nama sumber berawalan `simulasi_`.
  Ini bukan adapter pembayaran nyata. Jangan membuat endpoint HTTP langsung
  yang meneruskan JSON pelanggan ke fungsi ini.
- `chatgpt_billing/telegram_admin.py` menyediakan `DemoTelegramAdmin.handle()`
  dengan pemeriksaan ID user, ID chat, dan chat pribadi. Perintah di luar modul
  mengembalikan `None` agar tetap ditangani router lama.
- `simulate_payment_update()` mengembalikan `PaymentUpdate` yang dihitung dalam
  transaksi SQLite. `ready_for_work` dan event audit hanya dibuat pada perubahan
  yang benar-benar melewati ambang DP. `AdminReply.ready_order_id` adalah sinyal
  untuk pengait Nara; hasil return itu sendiri bukan bukti eksekusi. Pada tahap
  kedua, brief yang sudah terdaftar di `demo_jobs` ikut diantrekan secara atomik
  di dalam transaksi pembayaran, termasuk bila pembayaran masuk melalui
  `DemoTelegramAdmin` yang memakai koneksi `DemoStore` lain pada database sama.

Contoh pemakaian internal:

```python
from chatgpt_billing.pricing import QuoteRequest, make_quote
from chatgpt_billing.payment_flow import DemoStore

quote = make_quote(QuoteRequest(pages=10))
store = DemoStore()  # :memory:
order = store.create_order(quote, approved_by="operator-demo")
store.accept_quote(order.order_id, actor="pelanggan-demo")
store.simulate_payment(order.order_id, "DEMO-DP-001", 18000)
assert store.get(order.order_id).can_start
store.close()
```

Folder luar mengandung spasi sesuai permintaan owner. Package di dalamnya bernama
`chatgpt_billing` agar valid untuk import Python. Demo mengatur konteks import dari
lokasi script; tidak menambahkan folder ini ke runtime produksi. Saat integrasi,
tetapkan lokasi package yang sesuai arsitektur terbaru dan ubah import secara eksplisit.

## Antrean dan file hasil tahap kedua

`WorkflowStore` memperluas database demo yang sama. Penanda database v1 tetap
berlaku; tabel `demo_jobs` dan identitas folder hasil ditambahkan tanpa mengubah
saldo atau penawaran lama. Folder artefak hanya boleh kosong atau mempunyai
penanda yang cocok dengan database. Simpan database dan folder artefak bersama.

| API | Syarat dan hasil |
| --- | --- |
| `register_brief(order_id, Brief(...), actor=...)` | Hanya makalah sebelum pengerjaan; brief disimpan dan dikunci |
| `claim_next()` | Ambil satu job FIFO yang harga/brief disetujui dan DP cukup |
| `heartbeat(item)` | Perpanjang kepemilikan kerja yang masih aktif |
| `complete(item, ArtifactSet(...))` | Validasi file percobaan ini; simpan hash dan masuk review |
| `run_next(worker)` | Pembungkus sinkron claim, produce, complete; kegagalan menjadi blocked |
| `preview(order_id)` | Kembalikan path pratinjau setelah hash semua file dicek |
| `approve_result(..., preview_sha256=..., actor=...)` | Setujui versi pratinjau yang persis cocok |
| `release_result(order_id, actor=...)` | Salin final lokal setelah persetujuan, lunas, dan hash cocok |
| `recover_expired()` / `retry(...)` | Blokir job terputus; retry eksplisit maksimal dua percobaan |

Pembayaran dan pengantrean menggunakan satu transaksi SQLite `BEGIN IMMEDIATE`.
`reconcile()` menangani pesanan yang sudah dibayar sebelum brief didaftarkan.
Satu koneksi dipakai per thread/proses. Token percobaan dan lease bawaan 900 detik
mencegah hasil pekerja lama menimpa percobaan pengganti. Ini **bukan jaminan bahwa
panggilan AI eksternal hanya terjadi sekali**: proses yang terputus mungkin telah
memanggil provider. Simpan checkpoint Nara, identitas permintaan, dan biaya saat
membangun retry produksi. Jangan menjalankan loop AI tanpa batas.

`run_next()` cocok untuk fixture cepat. Integrasi Nara yang bisa berjalan lebih
dari 15 menit perlu memakai claim/heartbeat/complete dengan koneksi heartbeat
terpisah, atau scheduler yang memperpanjang lease selama pekerjaan hidup.
Demo belum mempunyai daemon, timer heartbeat, atau pengirim notifikasi otomatis.

`ProjectFormatWorker` adalah pekerja menu pengguna. Ia memuat langsung modul
`app/document_engine.py` melalui importlib, memakai `MakalahSpec` dan `DocumentSection`
asli, serta memberikan root build sementara di `runtime/format_builds`. Tidak ada
pemanggilan `from_env()`, startup bot, database utama, atau provider AI. Engine proyek
harus tetap modul tanpa startup saat di-import; periksa lagi bila engine berubah.

A4, margin, style, cover, section numbering, heading, serta field daftar isi
berasal dari engine yang sama. `project_format.py` menambahkan satu footnote native
untuk catatan uji internal serta format bibliografi kebijakan repository. Ini
bukan implementasi penuh CitationEngine: sitasi akademik pelanggan tetap wajib
melalui sumber terverifikasi dan alur sitasi Nara yang sebenarnya.

PDF dibuat oleh `DocumentEngine.convert_to_pdf()`. Di Windows Word COM memperbarui
field/daftar isi, menyimpan DOCX, lalu mengekspor PDF. `demo_toc.py` menolak hasil
Windows bila placeholder daftar isi belum terisi. Untuk pemeriksaan Linux, helper
mengisi cache field TOC khusus contoh ini berdasarkan posisi heading dalam PDF,
kemudian mengonversi ulang sampai nomor stabil, maksimal tiga kali. Helper tersebut
bukan pembuat TOC generik untuk semua makalah atau pengganti pembaruan field Word.

`pdf_preview.make_preview()` memakai pypdf untuk menyalin PDF final dan menambahkan
watermark pada setiap halaman. Isi dan ukuran halaman dipertahankan; file final
sumber tidak ditimpa. Watermark hanya penanda visual. Fungsi ini dapat diberikan
kepada `PreparedNaraWorker` saat integrasi dan tetap perlu diuji pada PDF Nara.
`ACUAN_FORMAT.json` mencatat hash engine, dua kebijakan, dan dua pedoman akademik.

`OfflineDemoWorker` lama dipertahankan sebagai fixture unit test pembayaran dan
antrean. Ia tidak dipakai peluncur pengguna dan tidak boleh dipakai untuk hasil
pelanggan. Tidak ada migrasi yang menulis ulang file atau saldo demo lama.

`artifacts.py` memeriksa lokasi file, ukuran, struktur XML/DOCX dasar, pasangan
referensi footnote, penanda PDF, dan hash SHA-256. Pemeriksaan PDF ini bukan
parser lengkap. Hash pratinjau yang berbeda dari final **tidak membuktikan adanya
watermark**. Isi, sumber, jumlah halaman, tata letak, dan watermark dari renderer
sebenarnya tetap harus diperiksa sebelum persetujuan.

File dibuat dahulu dalam `runtime/workflow/private/`. Folder `private` tidak
menyediakan enkripsi atau pembatasan akses OS; jalur pelanggan saat integrasi
tidak boleh mengeksposnya. Pelepasan memakai salinan sementara, verifikasi hash,
dan rename folder ke `released/`. Jika proses berhenti sesudah rename tetapi
sebelum commit, percobaan pelepasan berikutnya memvalidasi dan memakai salinan
yang sama. Kerusakan salinan akan ditolak.

Status order `delivered` pada demo berarti **file tersedia lokal**; event-nya
`local_final_released`. Produksi harus membedakan siap kirim, sedang dikirim, dan
terkirim melalui outbox serta bukti pengiriman. Jangan menggunakan status demo
sebagai bukti pelanggan menerima file.

Pesanan yang sudah mempunyai brief antrean diblokir dari transisi manual demo
lama, termasuk pembatalan dan revisi. Pembayaran tetap bisa dicatat melalui
pengendali demo Telegram. Revisi hasil berversi, jasa perapian file pelanggan,
dan pembatalan job belum diimplementasikan pada antrean.

## Menyambungkan pekerja Nara

`PreparedNaraWorker(factory, preview_builder)` adalah adapter yang bisa dipanggil,
tetapi kedua dependensinya wajib dipasang oleh integrasi. Ia tidak membuat
runtime admin, membaca `.env`, atau memuat Nara sendiri.

1. Sesudah `claim_next()`, siapkan satu instance Nara per order dan workspace
   keluaran di `item.output_dir`. Pertahankan isolasi sumber, pelanggan, serta
   database. Gunakan database uji; jangan menunjuk demo ke `assistant.db`.
2. Jalankan tahap brief, persetujuan kerangka, riset, dan draft milik Nara.
   Pekerjaan berbayar harus dimulai setelah claim yang lolos pembayaran.
   Jika menunggu persetujuan manusia lama, pisahkan checkpoint dan fase tugas;
   jangan menahan lease tanpa batas.
3. `factory(item)` mengembalikan Nara yang sudah `draft_ready` / `final_ready`.
   Adapter memanggil `build_final()` dan mensyaratkan `status == 'final_ready'`.
   Kedua file DOCX dan PDF harus benar-benar ada di direktori percobaan itu.
   Nara dapat melaporkan final siap walau konversi PDF gagal; adapter akan menolak
   hasil tersebut sampai PDF tersedia.
4. `preview_builder(final_pdf, output_path)` harus membuat pratinjau ber-watermark
   dari **PDF Nara yang asli**, mempertahankan isi dan tata letaknya. Jangan
   mengganti makalah Nara dengan PDF fixture `OfflineDemoWorker`.
5. Kembalikan hasil ke `complete()` untuk pemeriksaan, tampilkan pratinjau kepada
   pihak berwenang, catat persetujuan versi, lalu lepaskan final setelah lunas.

Kontrak adapter diuji dengan Nara palsu, termasuk draft belum siap dan keluaran
PDF hilang. Pembatasan direktori diperiksa pada jalur validasi file. Model/provider
Nara sungguhan belum dijalankan. Gunakan hasil tes ini sebagai dasar integrasi,
bukan klaim alur AI makalah end-to-end telah selesai.

## Perilaku yang sudah diuji

1. Paket, halaman tambahan, minimum jasa rapikan, dan tambahan footnote.
2. Perapian dasar makalah sudah termasuk; bundle footnote tidak dihitung ganda.
3. Harga di bawah/sama dengan ambang memakai pembayaran penuh; selebihnya DP.
4. Persetujuan harga dan DP cukup harus mendahului pengerjaan.
5. Status pending/deny/expire tidak menambah saldo pembayaran.
6. Notifikasi sukses berulang, termasuk dari dua koneksi, hanya dikreditkan sekali.
7. Referensi yang sama dengan nominal/order berbeda ditolak.
8. Pratinjau disetujui dan pembayaran lunas sebelum final.
9. Revisi pelanggan mengurangi jatah; koreksi kesalahan penyedia tidak.
10. Snapshot, riwayat, dan deduplikasi tetap tersimpan setelah restart.
11. Pembayaran berlebih atau setelah pembatalan memerlukan pemeriksaan manual.
12. Database tanpa penanda demo ditolak; tidak mengubah database contoh produksi.
13. Owner dapat cek DP, konfirmasi manual, dan cek sisa tagihan dari pengendali Telegram.
14. Pengguna lain/grup ditolak; perintah lama seperti `/saldo` tidak diambil alih.
15. Konfirmasi owner bersamaan atas transaksi yang sama hanya menghasilkan satu
    sinyal kesiapan kerja. Konfirmasi lunas dengan nominal kurang tidak memaksa lunas.

Lihat `HASIL_PENGUJIAN.md`. Tes baru tidak membuktikan koneksi layanan eksternal
atau integrasi dengan seluruh aplikasi utama.

## Rencana integrasi bertahap setelah diperintahkan owner

### 1. Tetapkan penawaran dan pengait ke alur Nara

- Konfirmasi tarif final, aturan pemilihan paket, lingkup, deadline, revisi, dan
  penanganan pembatalan/refund. Paket otomatis menggunakan kapasitas, bukan biaya termurah.
- Harga dihitung oleh kode dari konfigurasi server. AI hanya mengumpulkan data;
  jangan mempercayai total harga yang dikirim pelanggan atau dikarang model.
- Simpan order/invoice yang nyata dan hubungkan ke identitas pelanggan, usaha,
  sesi Nara, serta persetujuan penawaran.
- Letakkan gerbang pembayaran setelah brief dan penawaran disetujui, sebelum
  riset/draft berbayar. Konsultasi singkat dan estimasi dapat mendahului DP.
- Tambahkan pengait ke alur final yang benar-benar mengirim file; status demo
  `delivered` tidak boleh dianggap bukti bahwa pesan/file telah terkirim.

### 1b. Sambungkan admin Telegram yang sudah ada

- Owner memakai bot admin yang sama. Jangan membuat polling kedua dengan token
  yang sama, karena bisa mengganggu runtime `telegram_main.py` yang sedang berjalan.
- Gunakan identitas owner dari konfigurasi/runtime asli (`AdminIdentity`);
  jangan menyalin ID `1` atau `42` dari demo/tes ke produksi.
- Pertahankan pemeriksaan private chat dan allowlist di `TelegramAdminAdapter`.
  Hubungkan handler pembayaran pada routing admin, bukan routing WhatsApp pelanggan.
  Jangan mengambil `user_id`/`chat_id` dari teks pesan.
- Alur QRIS statis: owner melihat transaksi masuk di aplikasi merchant, lalu
  `/dp_konfirmasi` atau `/lunas_konfirmasi` mencatatnya melalui Telegram dengan audit.
- Alur Midtrans: notifikasi provider terverifikasi memperbarui invoice, kemudian
  kirim ringkasan DP/pelunasan ke Telegram owner; tidak perlu menunggu konfirmasi
  manual tambahan untuk setiap pembayaran Midtrans yang sudah sah.
- `payment_notice()` hanya memformat pesan. Gunakan pengirim dan pemecah pesan
  Telegram yang sudah ada serta outbox/retry persisten. Jangan mengirim ke chat
  yang ditentukan pelanggan.
- Pisahkan status pekerjaan dari pembayaran. Setelah DP cukup, lanjutkan pekerjaan
  Nara tepat satu kali melalui pekerjaan persisten yang tahan restart; hasil return
  Python saja bisa hilang jika proses crash sesudah transaksi tersimpan.
- Hilangkan/nonaktifkan `/simulasi_midtrans` dari runtime produksi. Jalur pelanggan
  tidak boleh dapat memanggil metode simulator untuk membuka gerbang pengerjaan.

### 2. Adapter Midtrans sandbox

- Bangun adapter tersendiri untuk membuat tagihan dengan ID dan nominal yang
  terikat pada invoice tersimpan. Tagihan DP dan pelunasan memiliki ID masing-masing.
- Gunakan environment sandbox dan kunci di server. Jangan meminta kunci di chat
  atau menyimpannya dalam Git. Tidak ada kunci yang dibutuhkan oleh demo ini.
- Buat endpoint HTTPS publik khusus pembayaran. Keberadaan webhook WhatsApp
  tidak otomatis membuatnya kompatibel dengan notifikasi Midtrans.
- Verifikasi notifikasi sesuai dokumentasi resmi dan cocokkan order ID, nominal,
  akun merchant/environment, currency, serta status terhadap invoice tersimpan.
- Gunakan Get Transaction Status untuk rekonsiliasi/kasus meragukan dan notifikasi
  terlambat. Screenshot, ucapan pelanggan, redirect browser, atau teks AI tidak
  cukup untuk menandai invoice terbayar.
- Tentukan aturan status tiap metode pembayaran; simulasi ini hanya memodelkan
  pending/settlement/expire/deny untuk pembahasan QRIS. Jangan menganggapnya
  implementasi lengkap semua metode Midtrans.

Dokumentasi yang perlu diperiksa ulang ketika membangun adapter:

- https://docs.midtrans.com/reference/qris
- https://docs.midtrans.com/docs/https-notification-webhooks

### 3. Persistensi, pengiriman, dan ledger

- Jangan mengarahkan `DemoStore` ke `data/assistant.db`. Gunakan migrasi produksi
  yang ditinjau dan diuji dengan salinan database.
- Simpan notifikasi mentah yang diperlukan secara aman ke inbox persisten sebelum
  menganggapnya ditangani; gunakan deduplikasi provider/merchant/transaction ID.
- Pastikan pembaruan pembayaran, invoice, dan event untuk ledger atomik atau
  memakai outbox/retry yang aman. Retry setelah crash tidak boleh menggandakan pemasukan.
- Catat DP dan pelunasan satu kali sesuai penerimaan. Memasukkan nilai order penuh
  ke Customer Book tidak otomatis menjadi pemasukan.
- Bedakan nilai bruto pesanan, biaya gateway, dana yang belum cair, dan pencairan
  ke bank. Saldo pembayaran demo bukan saldo rekening atau laporan akuntansi.
- Notifikasi terlambat, salah nominal, kelebihan bayar, refund, dan pembatalan
  memerlukan pencatatan/rekonsiliasi. Demo hanya menolak kasus tersebut; sistem
  nyata harus menyimpan kejadian agar uang tidak hilang dari pelacakan.
- Pakai antrean pengiriman persisten untuk pesan dan file. Jangan menandai terkirim
  hanya karena pembayaran berhasil; tangani kegagalan pengiriman dan pengulangan.

### 4. Pratinjau, revisi, dan pengujian integrasi

- Pembuat pratinjau `pdf_preview.make_preview()` sudah memberi watermark pada
  PDF hasil konversi DOCX. Uji lagi pada keluaran Nara; jangan menganggap watermark
  mencegah penyalinan isi atau menghubungkannya diam-diam ke runtime utama.
- Gerbang final harus melindungi semua jalur: WhatsApp, tautan unduh, dan alat
  admin yang relevan. Pertahankan isolasi data pelanggan.
- Terapkan batas waktu revisi bila disepakati; belum ada timer di prototipe.
- Tambahkan tes dengan adapter palsu untuk kegagalan provider, retry, restart,
  notifikasi paralel, nominal salah, dan pengiriman file gagal. Lalu uji sandbox
  Midtrans end-to-end sebelum mempertimbangkan transaksi nyata.
- Jalankan pengujian integrasi dan regresi aplikasi utama pada commit terbaru.
  Jangan menyatakan aplikasi siap produksi hanya berdasarkan tes prototipe ini.

## Batas yang masih terbuka

Belum ada adapter Midtrans live/sandbox, API/layar pelanggan, autentikasi baru,
penghubung TaqiDesk, posting ledger Laras, integrasi watermark keluaran Nara,
pengiriman file, revisi berversi pada antrean, refund, batas revisi berbasis waktu,
cetak/jilid, fee provider, atau pajak.
Tidak ada penggunaan internet oleh kode demo maupun tesnya setelah dependensi
tersedia. `SIAPKAN_FORMAT.bat` membutuhkan internet untuk pemasangan paket.
Hasil verifikasi: 94 tes lulus dan 7 halaman contoh diperiksa; lihat laporan
untuk batas pengujian Microsoft Word COM di Windows.
