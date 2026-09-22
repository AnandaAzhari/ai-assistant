# Mengambil perbaikan format di PC Windows

Perubahan ada dalam folder `di kerjakan oleh Chatgpt`. Untuk demo format,
gunakan Python 3.11+, Microsoft Word desktop, dan paket pypdf yang dipasang
melalui `SIAPKAN_FORMAT.bat` pada environment terpisah dalam folder itu.

## Melanjutkan salinan yang sudah Anda pakai

Screenshot terakhir menunjukkan demo berhasil di:

```text
D:\ai-assistant-chatgpt-antrean\di kerjakan oleh Chatgpt
```

Tidak perlu membuat worktree baru atau pindah branch pada `D:\ai-assistant`.
Tutup menu demo dengan `0` bila masih berjalan. Di Git Bash, jalankan:

```bash
cd /d/ai-assistant-chatgpt-antrean
git status --short
```

Jika hasil status kosong, lanjutkan satu per satu:

```bash
git fetch origin
git merge --ff-only origin/main
cd "di kerjakan oleh Chatgpt"
explorer.exe .
```

`git merge --ff-only` memajukan salinan demo yang pada screenshot berada di
detached commit `be04efe`; tidak membuat merge baru dan tidak mengganti branch
pekerjaan utama. Jika ada perubahan lokal atau perintah gagal, berhenti dan
periksa pesannya. Jangan menggunakan force, reset hard, atau menghapus file.
Folder `runtime` dan `.venv` demo diabaikan Git dan tetap berada di komputer.

Di File Explorer yang terbuka:

1. Klik dua kali **SIAPKAN_FORMAT.bat**, tunggu hingga pemasangan selesai.
2. Klik dua kali **JALANKAN_CONTOH_ANTREAN.bat** untuk membuat contoh baru.
3. Buka lokasi hasil yang dicetak. Periksa `hasil.docx` dan `hasil.pdf` baru.
4. Untuk mencoba manual, buka **JALANKAN_ANTREAN_DEMO.bat**.
5. **JALANKAN_TEST.bat** menjalankan tes; hasil yang diharapkan `OK` dan `TES LULUS.`.

Pemasangan pertama memerlukan internet. Demo setelahnya tidak memanggil layanan
AI, pembayaran, atau Telegram. `SIAPKAN_FORMAT.bat` memasang paket hanya ke `.venv`
di folder ini. File hasil versi lama tetap tersimpan dan tidak diperbarui otomatis.

Alternatif menjalankan dari Git Bash setelah persiapan:

```bash
./.venv/Scripts/python.exe -B workflow_demo.py --sample
```

Alternatif PowerShell untuk pembaruan, setelah `git status --short` dipastikan kosong:

```powershell
cd D:\ai-assistant-chatgpt-antrean
git fetch origin
git merge --ff-only origin/main
cd "di kerjakan oleh Chatgpt"
.\SIAPKAN_FORMAT.bat
.\JALANKAN_CONTOH_ANTREAN.bat
```

## Bila salinan antrean belum ada

Bagian ini hanya untuk komputer lain yang belum mempunyai folder tersebut.
Dari repository yang sudah ada:

```bash
cd /d/ai-assistant
git fetch origin
git worktree add --detach /d/ai-assistant-chatgpt-antrean origin/main
cd "/d/ai-assistant-chatgpt-antrean/di kerjakan oleh Chatgpt"
explorer.exe .
```

Jangan menimpa direktori yang sudah ada. Ikuti langkah pemasangan dan contoh di atas.
Data demo lama tidak otomatis berpindah ke worktree baru; jangan mencampurkan
database atau folder hasil dua percobaan yang berbeda.

## Serah terima

Setelah tampilan sesuai, Claude dapat membaca `README_UNTUK_CLAUDE.md`, kode,
dan `HASIL_PENGUJIAN.md`. Penyambungan Nara/Telegram serta pembayaran sungguhan
masih merupakan tahap integrasi berikutnya, menggunakan aplikasi utama terbaru.
