# Hasil pengujian prototipe pembayaran dan antrean

Tanggal: 22 September 2026.

**Status serah terima: seluruh 94 tes prototipe lulus dan owner telah menerima
format Word/PDF contoh.** Tes ulang atas kode commit
`70771143c0ce8f6b9213a648f50c495e5559307b` menghasilkan 94 lulus, 0 gagal,
0 error, 0 skip. Waktu eksekusi, log, lingkungan, dan hash kode dicatat dalam
`bukti_uji/hasil_unit_test.json`. Pembaruan serah terima hanya menambah/memperbarui
dokumentasi serta bukti, tanpa mengubah kode Python.

- Lingkungan eksekusi: Linux, Python 3.12.14.
- Acuan saat perbaikan format disiapkan: demo `be04efe`; main `2b58fd6`.
- Engine `app/document_engine.py` dan kebijakan format sama pada kedua acuan.
- Lingkup kode: hanya folder `di kerjakan oleh Chatgpt`.
- Dependensi format: pypdf 6.10.0; konversi/QA Linux menggunakan LibreOffice dan Poppler.
- Eksekusi demo dan tes tanpa jaringan; pemasangan paket Windows memerlukan internet.

## Tes otomatis

```text
python -B -m unittest discover -s tests -p 'test_*.py' -v
Ran 94 tests
OK
```

**94 tes lulus, 0 gagal:** 48 tes harga/pembayaran, 32 tes antrean, dan 14 tes format.
Tes menggunakan database memori atau direktori sementara. Tidak ada token
Telegram, kunci Midtrans, akun pelanggan, atau database produksi yang dipakai.

| Kelompok | Perilaku yang diperiksa |
| --- | --- |
| Harga | Batas paket, halaman tambahan, minimum perapian, footnote, rush, DP dan pembulatan |
| Pembayaran | Harga harus disetujui, DP parsial/pending, pembayaran gagal, nominal salah, deduplikasi |
| Transaksi | Pembayaran dan pengantrean rollback bersama jika enqueue gagal |
| Konkurensi | Empat koneksi pembayaran bersamaan menghasilkan satu kredit dan satu enqueue; empat pengambil job hanya satu yang berhasil |
| Antrean | Brief wajib/terkunci, FIFO, adopsi pesanan lama yang sudah dibayar, restart |
| Pemulihan | Lease/heartbeat, pekerja lama ditolak, kegagalan terlambat diabaikan, maksimal dua percobaan |
| Dokumen | DOCX dengan footnote, PDF hilang/rusak, pratinjau identik, hasil dari pesanan lain, jalur symlink keluar |
| Persetujuan | Versi pratinjau harus cocok; pembayaran lunas saja tidak melepas final |
| Integritas | File hilang/berubah setelah review atau persetujuan menahan penyerahan |
| Penyerahan lokal | Pelunasan wajib, pelepasan berulang tidak membuat salinan baru, pemulihan setelah rename sebelum commit |
| Kompatibilitas | Pengendali pembayaran lama tetap mengantrekan; menu status lama tidak dapat melewati gerbang antrean |
| Adapter Nara | Fake prepared agent, draft belum siap, PDF hilang |
| Isolasi | Database/folder asing ditolak, contoh otomatis tidak mengubah database interaktif |
| Peluncuran | Script dari direktori lain dan path dengan spasi |
| Telegram | Owner/private chat saja, perintah lain tetap diteruskan, status pembayaran dipisahkan dari pekerjaan |

Tes symlink dapat dilewati pada Windows jika akun tidak mempunyai izin membuat
symlink. Pada pengujian Linux seluruh 94 tes dijalankan tanpa skip.
Tes format meliputi engine yang dimuat, A4/margin/TNR, heading/indentasi, section
numbering, footnote, bibliografi, namespace OOXML, watermark semua halaman,
konversi gagal, hash acuan, serta pembaruan dan kegagalan stabilisasi daftar isi.
Unit test menggunakan converter pengganti; konversi nyata diperiksa terpisah di bawah.

## Percobaan file dan pemeriksaan visual

`python -B workflow_demo.py --sample` dijalankan dan berhasil: sebelum DP tidak
ada job yang bisa diambil; DP Rp18.000 membuka antrean; final ditolak sebelum
persetujuan dan sebelum pelunasan; setelah tambahan Rp42.000 file dilepas lokal.

Contoh baru dibuat dengan `ProjectFormatWorker`: DOCX berasal dari engine proyek,
PDF final merupakan hasil konversi DOCX, dan pratinjau merupakan salinan PDF itu
ber-watermark. Ketiganya menghasilkan **7 halaman**: sampul, kata pengantar,
daftar isi, BAB I, BAB II, BAB III, dan daftar pustaka.

Seluruh 7 halaman DOCX dirender dengan renderer dokumen/LibreOffice dan diperiksa
secara visual. Seluruh halaman PDF final serta pratinjau dirender dengan Poppler
dan diperiksa. Tidak ditemukan teks terpotong atau elemen bertumpuk. Footnote
berada di bawah halaman BAB I, bibliografi memakai hanging indent, sampul tanpa
nomor, halaman awal i/ii, dan isi bernomor 1–4. Daftar isi sesuai posisi heading.
Watermark terlihat pada seluruh halaman pratinjau; final tetap bersih.

Teks PDF final sama dengan teks pratinjau setelah penanda watermark dihapus,
dan geometri setiap halaman cocok. File hasil yang sudah dilepas tidak diubah.
Pengguna Windows memakai Microsoft Word desktop; LibreOffice dan Poppler dipakai
untuk pemeriksaan Linux ini dan tidak perlu dipasang pada PC owner yang memiliki Word.

## Bukti dari komputer owner

Screenshot tahap pertama menunjukkan demo chat terminal berhasil mencatat
DP Rp18.000 dan pelunasan Rp42.000, dengan total Rp60.000 dan sisa Rp0.
Screenshot berikutnya membuktikan demo antrean `be04efe` selesai di PC owner dan
Word/PDF berhasil dibuka. Owner kemudian melaporkan format Calibri/nomor desimal
tidak sesuai aturan proyek. Laporan itu menjadi dasar perbaikan ini.
Setelah perbaikan format dikirim, owner mengonfirmasi: **“hasilnya sudah sesuai”**.
Konfirmasi tersebut dicatat sebagai penerimaan tampilan hasil Word/PDF pada
percobaan owner. Tidak ada log Windows baru atau rincian versi Microsoft Word
yang dilampirkan bersama konfirmasi itu. ChatGPT tidak menjalankan Word COM di
Windows; bukti owner dan pengujian Linux di atas harus tetap dibedakan.

## Batas verifikasi

- Nara/model AI asli belum dijalankan. Adapter diuji memakai objek palsu.
- Dokumen singkat merupakan fixture, bukan hasil riset atau makalah 10 halaman.
- Tidak ada transaksi Midtrans sandbox/live, polling Telegram, atau pengiriman
  dokumen sungguhan. File `BUKTI_PENYERAHAN.json` hanya mencatat penyalinan lokal.
- Pemeriksa file memvalidasi struktur dasar dan hash, bukan isi akademik, jumlah
  halaman, tata letak semua kemungkinan brief, atau efektivitas watermark Nara.
- Revisi file berversi, antrean perapian, dan scheduler latar belakang belum dibuat.
- Peluncur `.bat` disiapkan dengan CRLF dan path berpetik. Installer `.venv` serta
  konversi melalui Word COM belum dijalankan di lingkungan Windows oleh ChatGPT.
- Suite seluruh aplikasi utama tidak dijalankan; kode aplikasi utama tidak diubah.
- Tarif tetap usulan untuk pengujian.

Panduan pengguna ada di `PANDUAN_ANTREAN.md`; kontrak integrasi dan pekerjaan
yang masih diperlukan ada di `README_UNTUK_CLAUDE.md`.
