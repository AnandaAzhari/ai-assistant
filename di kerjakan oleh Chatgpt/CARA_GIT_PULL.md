# Mengambil pembaruan di PC Windows

Semua kode tahap kedua tetap berada dalam folder GitHub `di kerjakan oleh Chatgpt`.
Demo memakai Python 3.11+ tanpa paket tambahan.

## Untuk kondisi komputer owner saat ini

Screenshot menunjukkan pekerjaan utama berada pada branch
`fitur-watermark-payment-gate` dengan perubahan lokal, sedangkan salinan demo
`D:\ai-assistant-chatgpt` berada pada detached commit `c1a96c2`. Folder demo di
salinan tersebut terlihat bernama `di_kerjakan_oleh_chatgpt`.

**Tidak perlu pindah ke main atau melakukan pull pada branch pekerjaan utama.**
Ambil pembaruan melalui worktree baru agar folder yang sudah diganti namanya,
data demo lama, dan pekerjaan Claude tetap tersimpan.

Jika demo lama masih berjalan, ketik `0` untuk menutup demo itu. Bot utama tidak
perlu dihentikan hanya untuk menjalankan contoh offline ini. Pada Git Bash,
jalankan perintah berikut satu per satu:

```bash
cd /d/ai-assistant
git fetch origin
git worktree add --detach /d/ai-assistant-chatgpt-antrean origin/main
cd "/d/ai-assistant-chatgpt-antrean/di kerjakan oleh Chatgpt"
py -3 -B workflow_demo.py --sample
```

Lanjutkan ke perintah berikutnya hanya jika perintah sebelumnya berhasil.
`git fetch` memperbarui referensi remote; `git worktree add` membuat salinan
checkout baru tanpa mengganti branch atau file kerja `D:\ai-assistant`.
Nama folder di GitHub masih memakai spasi, jadi gunakan tanda petik seperti contoh.

Alternatif PowerShell:

```powershell
cd D:\ai-assistant
git fetch origin
git worktree add --detach D:\ai-assistant-chatgpt-antrean origin/main
cd "D:\ai-assistant-chatgpt-antrean\di kerjakan oleh Chatgpt"
py -3 -B workflow_demo.py --sample
```

Jika `py` tidak dikenali tetapi Python AI Assistant tersedia sebagai `python`,
gunakan `python -B workflow_demo.py --sample`. Peluncur `.bat` juga mencoba kedua
nama interpreter itu dan memeriksa versinya.

Jika folder `ai-assistant-chatgpt-antrean` sudah ada, periksa isinya; jangan
menghapus atau menimpanya untuk memaksa perintah berhasil. Gunakan lokasi baru
yang belum ada atau kirim pesan error untuk diperiksa.

Data pesanan demo lama tidak otomatis berpindah ke worktree baru. Mulailah dengan
pesanan contoh baru pada tahap ini; pembayaran dan file lama tetap ada di lokasi
lama. Jika suatu saat memindahkan data demo, tutup seluruh proses demo dan salin
seluruh folder `runtime` sebagai satu kesatuan, bukan database atau file terpisah.
Jangan mencampurnya dengan runtime demo baru yang sudah berisi data.

## Menjalankan tahap kedua

Di File Explorer, buka:

```text
D:\ai-assistant-chatgpt-antrean\di kerjakan oleh Chatgpt
```

1. `JALANKAN_CONTOH_ANTREAN.bat`: contoh otomatis sampai Word dan PDF tersedia.
2. `JALANKAN_ANTREAN_DEMO.bat`: menu interaktif; ikuti `PANDUAN_ANTREAN.md`.
3. `JALANKAN_TEST.bat`: pemeriksaan otomatis; hasil akhir `OK` dan `TES LULUS.`.

Jendela `.bat` menunggu tombol agar pesan hasil/error terbaca. Peluncur lama
`JALANKAN_CONTOH.bat`, `JALANKAN_DEMO.bat`, dan `JALANKAN_TELEGRAM_DEMO.bat`
tetap tersedia untuk pengujian pembayaran tahap pertama. Semua ini demo offline;
perintah pembayaran belum diaktifkan pada bot Telegram utama.

## Jika kelak memperbarui checkout main yang bersih

Bagian ini hanya berlaku jika `git branch --show-current` menunjukkan `main`
dan `git status --short` kosong, bukan kondisi branch kerja owner pada screenshot.

```bash
git status --short
git branch --show-current
git pull --ff-only origin main
```

Jika ada perubahan lokal, riwayat bercabang, konflik, atau pesan file akan
ditimpa, periksa dahulu. Jangan menggunakan `reset --hard`, `clean -fd`, atau
force pull. Login GitHub dilakukan melalui mekanisme Git di komputer; token
atau password tidak perlu dikirim di chat.

Setelah demo cocok, minta Claude membaca `README_UNTUK_CLAUDE.md`, kode, dan
`HASIL_PENGUJIAN.md`, lalu mengintegrasikan berdasarkan versi aplikasi terbaru.
