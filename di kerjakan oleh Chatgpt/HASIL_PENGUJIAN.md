# Hasil pengujian prototipe pembayaran dan antrean

Tanggal: 22 September 2026.

- Lingkungan eksekusi: Linux, Python 3.12.14.
- Acuan tahap kedua: `c1a96c25f08d2cfcf532db3023634c7951b5c37a`.
- Lingkup kode: hanya folder `di kerjakan oleh Chatgpt`.
- Dependensi demo dan tes: Python standard library, tanpa jaringan.

## Tes otomatis

```text
python -B -m unittest discover -s tests -p 'test_*.py' -v
Ran 80 tests
OK
```

**80 tes lulus, 0 gagal:** 48 tes harga/pembayaran lama dan 32 tes antrean baru.
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
symlink. Pada pengujian Linux seluruh 80 tes dijalankan tanpa skip.

## Percobaan file dan pemeriksaan visual

`python -B workflow_demo.py --sample` dijalankan dan berhasil: sebelum DP tidak
ada job yang bisa diambil; DP Rp18.000 membuka antrean; final ditolak sebelum
persetujuan dan sebelum pelunasan; setelah tambahan Rp42.000 file dilepas lokal.

DOCX hasil contoh dirender dengan LibreOffice melalui renderer dokumen, kemudian
seluruh halaman gambar diperiksa. PDF final dan pratinjau dirender dengan Poppler
dan diperiksa. Contoh bawaan menghasilkan masing-masing satu halaman. Teks dapat
dibaca, BAB/subbab tampil, footnote Word berada di bagian bawah, watermark terlihat
pada PDF pratinjau, dan final tidak mempunyai watermark pratinjau.

Renderer dipakai untuk pemeriksaan pengembangan saja; pengguna tidak perlu
memasang LibreOffice/Poppler untuk menjalankan pekerja contoh offline.
Pembuatan PDF oleh Nara nanti tetap mengikuti kebutuhan renderer aplikasi utama.

## Bukti dari komputer owner

Screenshot tahap pertama menunjukkan demo chat terminal berhasil mencatat
DP Rp18.000 dan pelunasan Rp42.000, dengan total Rp60.000 dan sisa Rp0.
Itu membuktikan percobaan pembayaran lama berjalan di PC owner. Peluncur
antrean tahap kedua belum dijalankan di Windows owner pada saat laporan ini dibuat.

## Batas verifikasi

- Nara/model AI asli belum dijalankan. Adapter diuji memakai objek palsu.
- Dokumen singkat merupakan fixture, bukan hasil riset atau makalah 10 halaman.
- Tidak ada transaksi Midtrans sandbox/live, polling Telegram, atau pengiriman
  dokumen sungguhan. File `BUKTI_PENYERAHAN.json` hanya mencatat penyalinan lokal.
- Pemeriksa file memvalidasi struktur dasar dan hash, bukan isi akademik, jumlah
  halaman, tata letak semua kemungkinan brief, atau efektivitas watermark Nara.
- Revisi file berversi, antrean perapian, dan scheduler latar belakang belum dibuat.
- Peluncur `.bat` disiapkan dengan CRLF dan path berpetik; eksekusi tahap kedua
  pada Windows perlu dicoba pengguna.
- Suite seluruh aplikasi utama tidak dijalankan; kode aplikasi utama tidak diubah.
- Tarif tetap usulan untuk pengujian.

Panduan pengguna ada di `PANDUAN_ANTREAN.md`; kontrak integrasi dan pekerjaan
yang masih diperlukan ada di `README_UNTUK_CLAUDE.md`.
