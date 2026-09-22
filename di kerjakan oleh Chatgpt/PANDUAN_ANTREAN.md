# Mencoba antrean sampai file final

Tahap pertama telah menguji DP Rp18.000 dan pelunasan Rp42.000 untuk contoh
tagihan Rp60.000. Tahap kedua menguji apa yang terjadi setelah pembayaran:
pekerjaan masuk antrean, hasil diperiksa, pratinjau disetujui, lalu file final
dilepas. Semua pembayaran tetap simulasi dan dokumennya contoh singkat tanpa AI.

## Percobaan otomatis

Buka `JALANKAN_CONTOH_ANTREAN.bat`. Tidak perlu memasukkan perintah Telegram.
Program membuat pesanan baru dan seharusnya menampilkan:

```text
LULUS: pekerja ditahan sebelum DP.
LULUS: file final ditahan sebelum persetujuan.
LULUS: file final ditahan sebelum lunas.
ALUR SELESAI. File contoh tersedia di: ...
```

Salin lokasi folder hasil dari terminal ke alamat File Explorer. Di sana ada
`hasil.docx`, `hasil.pdf`, dan `BUKTI_PENYERAHAN.json`. Lokasi `pratinjau.pdf`
juga tercetak di terminal. Word memiliki footnote asli. PDF pratinjau memiliki
watermark `PRATINJAU - SIMULASI`; PDF final tidak memiliki watermark tersebut.

Contoh otomatis membuat database baru di `runtime/samples/` setiap kali
dijalankan. Persetujuan pratinjau juga disimulasikan oleh program. Untuk mencoba
pemeriksaan dan persetujuan sendiri, gunakan menu interaktif berikut.

## Percobaan dengan menu

Tutup contoh otomatis, lalu buka `JALANKAN_ANTREAN_DEMO.bat`.

| Menu | Tindakan | Hasil yang diharapkan |
| --- | --- | --- |
| 1 | Buat pesanan; judul boleh dikosongkan untuk memakai contoh | Tagihan Rp60.000, menunggu DP |
| 4 sebelum DP | Coba proses antrean | Belum ada pekerjaan yang siap |
| 3 | Simulasikan DP | Rp18.000 tercatat; masuk antrean |
| 4 | Kerjakan satu pesanan paling awal dalam antrean | Word, PDF, dan pratinjau dibuat |
| 5 | Buka pratinjau | Pembaca PDF Windows membuka PDF simulasi |
| 6 | Setujui versi pratinjau | Persetujuan tersimpan |
| 8 sebelum lunas | Coba lepas file final | Ditolak karena sisa Rp42.000 |
| 7 | Simulasikan pelunasan | Total tercatat Rp60.000, sisa Rp0 |
| 8 | Lepas file final | Folder hasil terbuka di File Explorer |
| 9 | Periksa status | Pembayaran lunas; file final tersedia lokal |
| 0 | Keluar | Data dan file tetap tersimpan |

Menu 4 mengambil pesanan siap paling awal, bukan selalu pesanan yang sedang
dipilih. ID yang diproses ditampilkan dan menjadi pesanan aktif. File hasil ada
di `runtime/workflow/released/ID_PESANAN/TOKEN_PERCOBAAN/`.

Setelah program dibuka kembali, menu 2 memilih pesanan tersimpan. Jika belum
menyetujui hasil, buka lagi pratinjaunya lewat menu 5 sebelum menu 6.

## Melanjutkan pesanan dari demo Telegram lama

Ini bisa dilakukan jika demo lama dan baru memakai **folder `runtime` yang sama**.
Pilih menu 2, salin ID yang ditampilkan, lalu menu 10 untuk menambahkan brief.
Pesanan yang sudah lunas tidak perlu dibayar lagi; lanjutkan menu 4, 5, 6, dan 8.
Hanya pesanan yang belum mulai dikerjakan yang dapat diberi brief antrean.

Jika pembaruan diambil melalui worktree baru, data lama masih ada di worktree
lama dan tidak otomatis ikut. Mulailah dari pesanan baru untuk percobaan ini.
Jangan menunjuk demo ke database bot utama.

## Jika proses terputus atau muncul error

Antrean dan pembayaran tersimpan di SQLite. Pekerjaan yang berhenti di tengah
pembuatan file tidak diulang diam-diam. Setelah batas kepemilikan kerja 15 menit
habis, menu 11 menandainya untuk pemeriksaan. Menu 12 mengantrekannya lagi,
lalu menu 4 menjalankan percobaan berikutnya. Maksimal dua percobaan per pesanan.
Hasil dari pekerja lama tidak dapat menyelesaikan percobaan pengganti.

Jika file berubah setelah diperiksa, jangan mengganti hash atau memaksa status
selesai. Simpan pesan error untuk diperiksa. Demo belum menyediakan perbaikan
versi hasil atau revisi dokumen setelah pratinjau dibuat.

Jika pembaca PDF tidak terbuka, buka lokasi yang dicetak melalui File Explorer.
Jika Python tidak ditemukan, gunakan Python 3.11+ yang menjalankan AI Assistant.
Peluncur Windows tidak memerlukan paket Python tambahan.

## Batas tahap ini

- Judul brief dicantumkan dalam file contoh, tetapi isi dokumen tidak dihasilkan
  dari riset atau model AI. Harga 10 halaman hanya contoh tagihan.
- Tidak ada bot Telegram kedua, pembacaan token, atau pemanggilan Nara/Midtrans.
  Menjalankan dua peluncur antrean ini tidak memulai bot utama.
- File final tersedia di komputer. Status selesai bukan bukti terkirim ke pelanggan.
- Pemeriksaan struktur dan hash belum menilai kebenaran sumber, konsistensi
  penomoran akademik, mutu isi, atau tata letak makalah sebenarnya.
- Perapian file pelanggan dan revisi versi hasil belum masuk antrean tahap ini.

Claude dapat membaca `README_UNTUK_CLAUDE.md` untuk menyambungkan modul ini ke
runtime AI agent setelah owner memerintahkan integrasinya.
