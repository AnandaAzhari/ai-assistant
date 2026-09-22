# Prototipe harga pembayaran dan antrean dokumen

**Status: DEMO TERPISAH. Format hasil telah disetujui owner; 94 tes prototipe lulus.
Tarif masih usulan untuk diuji oleh owner.**

Untuk serah terima, Claude mulai dari **`00_BACA_DULU_CLAUDE.md`**. Persetujuan
format, bukti tes, urutan integrasi, dan salinan pedoman sudah ada dalam folder ini.

Folder ini berisi kode Python yang dapat dijalankan, pengujian, dan panduan
integrasi untuk Claude. **Tujuannya adalah modul untuk AI agent, dengan Telegram
sebagai tempat owner mengecek DP dan pelunasan.** Kode aplikasi utama AI Assistant tidak diubah.
Tidak ada API key, koneksi Midtrans, transaksi uang, pesan pelanggan, atau
pembuatan/pengiriman makalah sungguhan dari demo ini.

## Mulai di Windows

Gunakan Python **3.11 atau lebih baru**, seperti proyek AI Assistant.
Demo antrean memakai **Microsoft Word desktop** untuk konversi PDF di Windows,
serta paket `pypdf` untuk membuat pratinjau. Jalankan `SIAPKAN_FORMAT.bat` sekali;
paket dipasang pada `.venv` di folder percobaan ini. Pemasangan memerlukan internet.
Demo pembayaran lama tetap memakai standard library.

1. Ambil pembaruan repository sesuai `CARA_GIT_PULL.md`.
2. Buka folder `di kerjakan oleh Chatgpt` pada `D:\ai-assistant-chatgpt-antrean`.
3. Klik dua kali **`SIAPKAN_FORMAT.bat`**. Setelah selesai, klik
   **`JALANKAN_CONTOH_ANTREAN.bat`** untuk membuat contoh baru dengan format proyek,
   PDF hasil konversi Word, serta pratinjau ber-watermark simulasi.
4. Klik dua kali **`JALANKAN_ANTREAN_DEMO.bat`** untuk mencoba langkahnya sendiri.
   Urutan menu: **1 → 3 → 4 → 5 → 6 → 7 → 8**. Lihat `PANDUAN_ANTREAN.md`.
5. `JALANKAN_TELEGRAM_DEMO.bat` tetap tersedia untuk format chat admin di terminal.
6. Klik dua kali `JALANKAN_TEST.bat` untuk menjalankan tes. Hasil akhir yang
   diharapkan: `OK` dan `TES LULUS.`

Alternatif terminal, dari dalam folder ini:

```powershell
.venv\Scripts\python.exe -B workflow_demo.py --sample
.venv\Scripts\python.exe -B workflow_demo.py
py -3 -B demo.py --sample
py -3 -B demo.py --telegram-demo
.venv\Scripts\python.exe -B -m unittest discover -s tests -p "test_*.py" -v
```

Menu interaktif lama dan baru memakai `runtime/demo.sqlite3` di folder ini.
Antrean serta file hasil dapat dibuka kembali setelah program ditutup.
`workflow_demo.py --sample` memakai subfolder baru di `runtime/samples/` pada
setiap peluncuran, sehingga tidak mengambil antrean interaktif. Contoh lama
`demo.py --sample` tetap memakai database memori.

Folder `runtime/` diabaikan Git. Modul tidak membaca `.env` atau database
produksi AI Assistant. Untuk demo kosong, tutup semua demo lalu ganti nama
**seluruh folder `runtime` milik prototipe ini**, misalnya `runtime-lama`.
Database dan folder hasil antrean harus disimpan bersama.

## Tahap kedua yang sudah tersedia

Pesanan dengan brief dan harga yang disetujui masuk antrean setelah DP cukup.
Pembayaran dan pengantrean dicatat dalam transaksi yang sama. Satu pekerja
mengambil satu pesanan; pekerjaan terputus perlu diperiksa sebelum diulang.
Pengulangan dibatasi maksimal dua percobaan.

Pekerja `ProjectFormatWorker` memakai **`app/document_engine.py` milik proyek**
secara baca-saja, dengan direktori keluaran eksplisit di folder percobaan. Modul
bot, `.env`, database utama, dan provider AI tidak dijalankan. Checkout repository
harus lengkap; folder prototipe saja tidak cukup untuk contoh format ini.

Format mengikuti `policies/document_format_policy.md`,
`policies/document_type_structure_policy.md`, dan `skills/document_academic/`:

- A4, Times New Roman 12, spasi 1,5; margin kiri 4 cm dan sisi lain 3 cm.
- Sampul, kata pengantar, daftar isi, BAB I–III, serta daftar pustaka.
- Hierarki BAB → A. → 1. → a.; BAB baru pada halaman baru.
- Halaman awal Romawi, isi mulai angka 1; daftar isi sampai Heading 3.
- Footnote Word asli 10 pt, superscript; daftar pustaka dengan hanging indent.

PDF final dikonversi dari DOCX, kemudian disalin menjadi pratinjau dengan watermark
`PRATINJAU - SIMULASI` pada setiap halaman. Bila konversi atau daftar isi gagal,
pekerjaan ditahan. `ACUAN_FORMAT.json` di folder hasil internal merekam hash acuan.

**Isi tetap contoh pengujian, bukan makalah 10 halaman yang dikerjakan AI.**
Catatan kaki merujuk dokumen kebijakan repository, bukan sumber akademik rekaan.
Contoh bawaan menghasilkan 7 halaman pada pengujian Linux; periksa lagi hasil Word
di PC Anda. Pembuatan isi berdasarkan riset tetap tugas Nara saat integrasi.
`OfflineDemoWorker` lama hanya dipertahankan untuk unit test.

File yang sudah dihasilkan versi lama tidak diubah. Jalankan contoh otomatis
lagi untuk memperoleh pesanan dan file baru dengan format yang diperbaiki.

Sistem memeriksa struktur dasar dokumen dan mencatat hash file. Pelepasan file
final memerlukan persetujuan atas versi pratinjau yang sama dan pembayaran lunas.
File yang berubah setelah diperiksa akan ditahan. Pelepasan berarti menyalin
Word/PDF ke folder lokal; belum mengirimnya ke pelanggan.

Pada demo interaktif, menu 4 menjalankan satu pekerjaan. Antrean belum mempunyai
pekerja latar belakang. Adapter `PreparedNaraWorker` disediakan untuk Claude,
tetapi belum dihubungkan ke Nara, bot Telegram, atau pembayaran sungguhan.

Folder `private` adalah pemisahan lokasi internal aplikasi, bukan enkripsi atau
pembatasan akses terhadap pemilik PC. Watermark juga bukan pencegah penyalinan.

## Contoh tahap pertama yang tetap tersedia

Alur otomatis memakai makalah 10 halaman isi:

| Langkah | Hasil |
| --- | --- |
| Penawaran | Rp60.000 |
| Pelanggan menyetujui harga | Menunggu pembayaran awal |
| Dicoba mulai tanpa membayar | Ditolak |
| Notifikasi pembayaran `pending` | Pemasukan tetap Rp0 |
| Simulasi DP sukses | Rp18.000 tercatat |
| Notifikasi DP yang sama diulang | Tetap Rp18.000 |
| Mulai, catat pratinjau, setujui pratinjau | Menunggu pelunasan Rp42.000 |
| Dicoba menyerahkan final sebelum lunas | Ditolak |
| Simulasi pelunasan | Siap menyerahkan final |
| Catat penyerahan final | Selesai |

Dalam menu lama `JALANKAN_DEMO.bat`, urutan mudah: **1 → 3 → 4 → 5 → 6 → 8 → 4 → 9**.
Nomor 4 pertama untuk DP; nomor 4 kedua untuk sisa tagihan. Masukkan angka
tanpa titik: `18000`, bukan `18.000`. Menu 2 membuka pesanan demo lama.
Untuk mencoba notifikasi berulang, gunakan sumber, referensi, dan nominal yang sama.

Menu lama hanya mencatat tahap serta referensi contoh. Gunakan demo antrean
untuk membuat file sebenarnya. Pesanan yang sudah dikelola antrean tidak dapat
melewati pemeriksaan hasil melalui menu tahap pertama.

## Telegram sebagai panel admin AI agent

Owner meminta cukup mengecek DP/pelunasan dari Telegram. Pengendali pesannya
sudah dibuat di `chatgpt_billing/telegram_admin.py` dan diuji tanpa koneksi bot.
`JALANKAN_TELEGRAM_DEMO.bat` membuka simulasi percakapan di terminal; **perintah
berikut belum aktif di bot Telegram utama** sampai Claude mengintegrasikannya.

| Perintah prototipe | Fungsi |
| --- | --- |
| `/dp` | Daftar pesanan yang menunggu pembayaran awal |
| `/dp ID_PESANAN` | Status DP satu pesanan |
| `/pembayaran ID_PESANAN` | Total, pembayaran tercatat, dan sisa tagihan |
| `/dp_konfirmasi ID_PESANAN NOMINAL REFERENSI` | Konfirmasi manual QRIS setelah owner mengecek uang masuk |
| `/lunas_konfirmasi ID_PESANAN NOMINAL REFERENSI` | Catat pembayaran berikutnya; tidak memaksakan status lunas jika nominal kurang |
| `/bantuan_pembayaran` | Petunjuk perintah |

Gunakan ID yang ditampilkan demo. Nominal ditulis `18000`, bukan `18.000`.
Referensi adalah identitas transaksi, misalnya `QR-001`; pengulangan transaksi
yang sama tidak menambah pemasukan lagi. Dalam penggunaan nyata, periksa
**aplikasi merchant**, bukan hanya screenshot dari pelanggan.

Untuk mencontohkan jalur otomatis, tersedia perintah **khusus demo**
`/simulasi_midtrans ID_PESANAN NOMINAL REFERENSI STATUS`. Status pending/expire/deny
tidak membuat DP terbayar; settlement menghitung penerimaan satu kali.
Saat syarat pembayaran awal terpenuhi, pengendali menghasilkan sinyal pesanan siap
diteruskan ke Nara. Jika brief sudah didaftarkan melalui demo antrean pada
database yang sama, pesanan juga masuk antrean persisten. Pengendali belum
mengeksekusi Nara atau mengirim apa pun.

Setelah integrasi nyata:

- **QRIS statis:** owner memeriksa uang masuk lalu mengonfirmasi melalui Telegram.
- **Midtrans:** adapter terverifikasi memperbarui pembayaran, lalu Telegram memberi
  notifikasi; owner tidak harus mengonfirmasi setiap DP secara manual.
- Pembukaan pekerjaan berbayar tetap berasal dari status pembayaran tersimpan.
  AI tidak menebak apakah pelanggan sudah membayar.

Pengendali hanya menerima ID owner dan chat pribadi yang dikonfigurasi. Pesan
dari orang lain atau grup diabaikan. Perintah seperti `/saldo` dikembalikan ke
router lama agar tidak mengambil alih fitur yang sudah ada.

## Harga usulan dan aturan hitung

Edit `config_harga.json` untuk mencoba harga lain. Perubahan berlaku untuk
penawaran baru; harga dan syarat pembayaran pesanan lama tetap sesuai snapshot
penawaran saat dibuat. Jangan mengubah `status` menjadi produksi: kode demo
memang menolak konfigurasi selain `USULAN_UNTUK_UJI`.

### Penyusunan makalah

| Paket | Batas halaman isi | Harga |
| --- | ---: | ---: |
| Ringkas | 5 | Rp35.000 |
| Standar | 10 | Rp60.000 |
| Lengkap | 15 | Rp90.000 |
| Halaman tambahan di atas kapasitas paket yang dipilih | Per halaman | Rp6.000 |

Halaman isi tidak mencakup cover, kata pengantar, daftar isi, dan daftar pustaka.
Format standar, BAB/subbab, nomor halaman, sitasi dasar/daftar pustaka dari sumber
yang digunakan, dan satu putaran revisi kecil termasuk paket.
Topik umum dengan sumber tersedia menjadi dasar penawaran; topik sulit atau
pedoman khusus perlu dinilai owner, bukan dipaksakan ke harga otomatis.

Pilihan **otomatis** memilih paket terkecil yang kapasitasnya mencukupi.
Lebih dari 15 halaman memakai paket Lengkap ditambah halaman tambahan.
Pilihan paket eksplisit mempertahankan paket yang telah disepakati dan menambahkan
kelebihan halaman. Contoh: Ringkas yang diperluas menjadi 8 halaman =
Rp35.000 + 3 × Rp6.000 = Rp53.000. Otomatis untuk pesanan baru 8 halaman memilih
Standar Rp60.000. Ini keputusan harga **sementara**, bukan optimasi tarif termurah;
owner perlu meninjau apakah sistem paket ini ingin dipertahankan sebelum produksi.

### Merapikan dokumen pelanggan

| Tingkat | Tarif per halaman | Minimum total |
| --- | ---: | ---: |
| Dasar: font, spasi, margin, paragraf | Rp2.000 | Rp15.000 |
| Struktur: dasar + BAB/subbab, penomoran, daftar isi | Rp3.500 | Rp25.000 |
| Khusus: mengikuti pedoman | Mulai Rp5.000 | Rp40.000 |

Ketiga tingkat adalah alternatif, tidak ditumpuk. Jumlah halaman di sini adalah
halaman dokumen pelanggan yang disepakati untuk dirapikan. Tarif khusus memerlukan
pemeriksaan operator. Paket makalah tidak ditambah tarif rapikan dasar lagi.
Format khusus untuk makalah baru belum dihitung otomatis; buat penawaran manual.

### Tambahan

| Tambahan | Tarif awal |
| --- | ---: |
| Bundle footnote makalah, hingga 10 catatan dari sumber lengkap | Rp15.000 |
| Footnote ke-11 dan seterusnya dalam bundle | Rp1.000/catatan |
| Rapikan footnote dokumen pelanggan dari data sumber lengkap | Rp1.000/catatan, minimum Rp10.000 |
| Mencari/memeriksa data sumber kutipan yang belum lengkap | Mulai Rp5.000/sumber |
| Putaran revisi kecil tambahan | Mulai Rp10.000/putaran |
| Cepat, kurang dari 24 jam | Tambahan 30% dari subtotal seluruh jasa |

Bundle dan tarif per-footnote untuk dokumen pelanggan tidak dipakai bersamaan.
Penelitian sumber yang sudah termasuk paket makalah tidak ditagihkan ulang sebagai
verifikasi tambahan. Tambahan verifikasi adalah pekerjaan di luar lingkup paket
yang diperiksa dan disepakati sebelumnya. Tidak boleh mengarang sumber yang tidak ditemukan.

Layanan cepat, tarif khusus, tambahan verifikasi, dan tambahan revisi meminta
konfirmasi pemeriksaan operator sebelum pesanan demo dapat dibuat. Harga mulai
bukan jaminan harga final untuk semua kasus. Cetak, jilid, ongkir, refund, biaya
provider pembayaran, dan pajak **belum dihitung**.

## Pembayaran dan revisi

- Total sampai Rp35.000: bayar penuh sebelum pengerjaan.
- Total di atas Rp35.000: DP 30%, dibulatkan ke atas ke rupiah utuh.
- Kriteria memakai **total setelah tambahan**, bukan harga paket dasar.
- Pelanggan harus menyetujui penawaran sebelum menerima simulasi pembayaran.
- Pembayaran boleh bertahap, tetapi pengerjaan baru dibuka setelah ambang awal tercapai.
- Pratinjau harus disetujui dan total harus lunas sebelum penyerahan final.
- Satu putaran revisi kecil termasuk. Putaran tambahan bisa dimasukkan ke penawaran awal.
- Kesalahan dari penyedia dapat dikoreksi tanpa mengurangi jatah revisi.
- Perubahan topik/lingkup dan revisi tambahan setelah jatah habis membutuhkan
  penawaran baru; kode ini tidak diam-diam mengubah tagihan yang sudah disetujui.
- Batas waktu revisi tiga hari **belum ditegakkan otomatis**. Ini masih aturan yang
  perlu dikonfirmasi owner dan diimplementasikan saat integrasi.

Aturan revisi di atas diuji pada alur tahap pertama. Antrean file tahap kedua
belum mendukung putaran revisi atau jasa merapikan file pelanggan. Jangan memakai
menu revisi lama untuk mengubah hasil yang telah dikunci oleh antrean.

Pembatalan demo hanya tersedia untuk pesanan yang belum menerima pembayaran dan
belum dikerjakan. Pembayaran terlambat setelah pembatalan atau pembayaran berlebih
ditolak oleh demo dan membutuhkan pemeriksaan operator. Integrasi nyata harus
menyimpan kejadian tersebut untuk rekonsiliasi; tidak boleh menghilangkan bukti uang masuk.

## Isi folder

| Lokasi | Fungsi |
| --- | --- |
| `chatgpt_billing/pricing.py` | Validasi input/config dan kalkulasi penawaran |
| `chatgpt_billing/payment_flow.py` | Tahapan pesanan, database demo, simulasi pembayaran, jejak tindakan |
| `chatgpt_billing/telegram_admin.py` | Cek DP/pelunasan dan konfirmasi owner, tanpa koneksi bot |
| `chatgpt_billing/workflow.py` | Antrean SQLite, pemulihan pekerjaan, persetujuan versi, pelepasan file |
| `chatgpt_billing/artifacts.py` | Pemeriksaan struktur dasar, isolasi lokasi, hash dokumen |
| `chatgpt_billing/workers.py` | Fixture unit test dan adapter Nara yang belum diaktifkan |
| `chatgpt_billing/project_format.py` | Pekerja contoh dengan DocumentEngine asli |
| `chatgpt_billing/pdf_preview.py`, `chatgpt_billing/demo_toc.py` | Watermark PDF dan cache daftar isi contoh |
| `tests/test_project_format.py` | Pengujian format, konversi gagal, TOC, serta pratinjau |
| `00_BACA_DULU_CLAUDE.md` | Titik masuk serah terima dan urutan membaca |
| `01_FORMAT_DAN_PERSETUJUAN_OWNER.md` | Acuan format yang telah diterima owner |
| `02_LANJUTAN_NARA_TELEGRAM.md` | Pekerjaan integrasi berikutnya |
| `bukti_uji/`, `referensi/` | Bukti tes ulang dan salinan pedoman format |
| `workflow_demo.py` | Menu antrean dan contoh otomatis sampai file lokal |
| `demo.py` | Contoh otomatis dan menu terminal |
| `config_harga.json` | Tarif serta aturan pembayaran usulan |
| `tests/test_chatgpt_billing.py` | Pengujian perilaku harga/pembayaran |
| `tests/test_workflow.py` | Pengujian antrean, pemulihan, file, dan adapter |
| `JALANKAN_*.bat` | Peluncur Windows |
| `CARA_GIT_PULL.md` | Cara mengambil pembaruan dan menjalankan demo |
| `PANDUAN_ANTREAN.md` | Langkah percobaan tahap kedua di komputer owner |
| `README_UNTUK_CLAUDE.md` | Batas implementasi dan peta integrasi |
| `HASIL_PENGUJIAN.md` | Bukti pengujian serta batas verifikasi |

Pekerja format hanya memuat `app/document_engine.py` asli dengan root keluaran
terpisah. Tidak ada pemanggilan bot atau perubahan pada peluncur utama.
Penggunaan aplikasi utama setelah `git pull` tetap mengikuti kode utamanya.
