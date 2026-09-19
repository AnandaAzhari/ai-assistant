# Provider AI & Harga — Dimas (Desktop Agent)

## Status kode saat ini

Dimas **tidak memakai AI sama sekali**, dan tidak ada rencana jangka pendek
untuk itu. `app/desktop.py` hanya berisi 89 baris kode deterministik: buat
folder pesanan, buka file dengan aplikasi bawaan Windows, dan mencatat
bukti/status. Dimas juga secara eksplisit ditandai di dokumennya sendiri
sebagai "belum dapat mengendalikan Windows" secara lebih luas.

Lihat `docs/PANDUAN_WINDOWS.md` untuk cara memakai Dimas sekarang (lewat
`jalankan.bat` / `main.py`).

## Kenapa belum butuh provider AI

Tugas Dimas saat ini (buat folder, buka file dengan aplikasi yang sesuai)
adalah operasi file-system sederhana yang tidak butuh pemahaman bahasa atau
penalaran — cocok tetap deterministik. Menambah AI di sini baru masuk akal
kalau cakupan Dimas diperluas nanti (misalnya memahami instruksi bahasa
bebas soal pengaturan file, atau mengendalikan aplikasi Windows lain).

## Rekomendasi

Tidak ada rekomendasi provider untuk saat ini — tidak perlu mengisi API key
apa pun untuk Dimas. Kalau ke depan cakupannya diperluas untuk memahami
instruksi bahasa bebas, model kecil/murah seperti DeepSeek V4.1 Flash
kemungkinan sudah cukup untuk klasifikasi perintah sederhana (folder mana,
file mana), tanpa perlu model yang lebih mahal.

## Harga

Tidak relevan untuk saat ini karena belum ada pemakaian AI.

## Variabel `.env` terkait

Tidak ada. Dimas tidak membaca variabel provider AI apa pun saat ini.
