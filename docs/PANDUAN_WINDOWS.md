# Panduan Windows — AI Assistant v0.1

Target pertama: ketik perintah, buat folder pesanan, buka file contoh, dan lihat laporan.
Program bekerja lokal, belum menggunakan provider AI atau WhatsApp.

## 1. Siapkan Python

Buka PowerShell, ketik:

```powershell
py -3 --version
```

Gunakan Python 3.11 atau lebih baru. Jika perintah `py` tidak dikenal, coba
`python --version`. Jika Python belum terpasang, buka situs resmi
[Python untuk Windows](https://www.python.org/downloads/windows/) dan pasang
rilis stabil Python 3. Setelah pemasangan, tutup dan buka kembali terminal.
Tidak ada paket tambahan, `pip install`, atau API key yang diperlukan.

## 2. Unduh program

1. Buka repo [ai-assistant](https://github.com/AnandaAzhari/ai-assistant) dengan akun GitHub kamu.
2. Klik **Code → Download ZIP**.
3. Ekstrak ZIP ke folder komputer. Jangan menjalankan dari dalam ZIP.
4. Buka folder hasil ekstrak yang berisi `main.py` dan `jalankan.bat`.

Jika sudah menggunakan Git pada repo ini, ambil perubahan terbaru dengan `git pull`
di folder repo milikmu. Simpan perubahan lokalmu terlebih dahulu.

## 3. Siapkan file contoh

1. Di File Explorer, buat folder kerja, misalnya `Dokumen\Uji Asisten`.
2. Buka Notepad, tulis `Ini dokumen uji pertama.`, lalu simpan sebagai `contoh.txt`
   di folder kerja tersebut. Pastikan nama dan ekstensi terlihat di File Explorer.
3. Salin alamat lengkap folder kerja dari bilah alamat File Explorer.

Gunakan lokasi yang benar-benar ada di komputermu. `D:\Pesanan` di contoh perintah
bukan lokasi wajib; komputer tanpa drive D bisa memakai folder Dokumen.
Simpan file pelanggan di folder kerja terpisah dari repo agar tidak ikut commit.

## 4. Jalankan

Klik dua kali `jalankan.bat`, kemudian tempel alamat folder kerja ketika diminta.

Alternatif: buka PowerShell di folder program, lalu ketik:

```powershell
py -3 main.py
```

Jika hanya perintah `python` yang tersedia, gunakan `python main.py`.
Program menampilkan alamat folder kerja yang dipakai dan daftar perintah.

## 5. Uji pesanan pertama

Masukkan jawaban berikut, satu per satu sesuai pertanyaan program:

| Pertanyaan | Jawaban contoh |
| --- | --- |
| `Perintah >` | `pesanan` |
| `Nama folder pesanan:` | `Uji-001` |
| `Nama/path file (di dalam folder kerja):` | `contoh.txt` |

Hasil yang diharapkan:

- Folder `Uji-001` muncul di dalam folder kerja.
- Windows diminta membuka `contoh.txt` dengan aplikasi yang sesuai.
- File contoh tetap di lokasi asal; tidak disalin ke folder pesanan.
- Program menampilkan bukti folder tersedia dan status `menunggu verifikasi`.
- Periksa jendela dokumen. Jika file yang benar terlihat, kembali ke terminal
  dan ketik `y`. Program mencatat bahwa verifikasi berasal dari pengguna.
- Jika belum terlihat, ketik `n`; jika belum tahu, tekan Enter. Program tidak
  akan mengklaim pembukaan file sudah berhasil.
- Ketik `keluar` setelah selesai.

Nama/path file boleh mengandung spasi. Path relatif dihitung dari folder kerja.
Path lengkap hasil **Copy as path** boleh ditempel beserta tanda kutip ganda.
Dokumen harus berada di dalam folder kerja atau subfoldernya.

## 6. Jika ada kendala

| Gejala | Tindakan |
| --- | --- |
| Python tidak ditemukan atau muncul Microsoft Store | Selesaikan pemasangan Python, buka ulang terminal, lalu periksa versi. |
| `main.py` tidak ditemukan | Buka terminal di folder hasil ekstrak yang berisi `main.py`. |
| Folder kerja tidak dapat digunakan | Periksa alamat dan pastikan folder sudah dibuat serta bisa diakses. |
| Nama folder tidak valid | Gunakan nama sederhana seperti `Uji-001`, tanpa slash, titik dua, atau nama khusus seperti `CON`. |
| Nama sudah dipakai sebuah file | Pilih nama folder lain; file lama tidak ditimpa. |
| File tidak ditemukan | Periksa ekstensi dan path persis; jangan menebak dari nama yang mirip. |
| File di luar folder kerja | Gunakan file contoh di dalam folder kerja atau jalankan ulang dengan folder kerja yang sesuai. |
| Aplikasi tidak membuka file | Coba buka file melalui File Explorer untuk memeriksa aplikasi bawaan; laporkan `n` di terminal. |
| Status sebagian selesai | Baca langkah yang sudah selesai. Folder yang telah dibuat tetap ada. |

Tidak ada penghapusan, penimpaan file, pemasangan aplikasi, pengiriman data,
atau eksekusi perintah terminal bebas dalam versi ini.

## 7. Batas pengujian

Pengujian unit dapat berjalan di Windows maupun Linux:

```powershell
py -3 -m unittest discover -s tests -v
```

Pengujian otomatis memeriksa alur dan penanganan kesalahan memakai pembuka file
pengganti. Integrasi aplikasi desktop Windows harus diperiksa dengan langkah 5.
Setelah uji pertama berhasil, tahap berikutnya adalah menambahkan pemahaman
bahasa dengan AI ke router yang sudah bekerja.
