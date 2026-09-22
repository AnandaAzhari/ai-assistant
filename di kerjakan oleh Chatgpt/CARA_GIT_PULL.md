# Mengambil pembaruan di PC Windows

Pembaruan ini menambahkan folder `di kerjakan oleh Chatgpt` pada branch `main`.
Tidak ada paket Python tambahan yang harus dipasang untuk demo.

## 1. Buka terminal di folder proyek

Jika memakai PowerShell dan proyek berada di `D:\ai-assistant`:

```powershell
cd D:\ai-assistant
git status --short
git branch --show-current
```

Jika memakai Git Bash:

```bash
cd /d/ai-assistant
git status --short
git branch --show-current
```

Sesuaikan lokasi bila folder proyek berbeda. Pada Command Prompt gunakan
`cd /d D:\ai-assistant`. Perintah Git berikutnya sama di ketiga terminal.

## 2. Periksa sebelum mengambil perubahan

- Jika `git status --short` tidak menampilkan baris, tidak ada perubahan lokal
  yang dilaporkan Git. Branch yang diharapkan adalah `main`.
- Jika muncul daftar perubahan, selesaikan/simpan pekerjaan tersebut bersama
  Claude terlebih dahulu. Tidak perlu menghapus file atau membuang perubahan.
- Jika branch berbeda, periksa pekerjaan di branch tersebut sebelum pindah ke
  `main`. Jangan otomatis mencampurkan main ke branch pekerjaan lain.
- Jika muncul `not a git repository`, terminal belum berada di folder repository
  atau folder berasal dari ZIP, bukan clone Git.

## 3. Ambil pembaruan

Setelah status dan branch sesuai:

```bash
git pull --ff-only origin main
```

Opsi `--ff-only` mencegah Git membuat merge otomatis bila riwayat bercabang.
Jika ada pesan konflik, `would be overwritten`, atau `Not possible to fast-forward`,
berhenti dan kirim pesan lengkapnya untuk diperiksa. **Jangan gunakan `reset --hard`,
`clean -fd`, atau force pull untuk memaksa pembaruan ini.**

Jika diminta login GitHub, lakukan melalui mekanisme login Git di komputer;
jangan menaruh token/password di chat atau repository.

## 4. Coba hasilnya

Buka folder `di kerjakan oleh Chatgpt` di File Explorer, kemudian klik:

1. `JALANKAN_CONTOH.bat` — alur otomatis dari harga hingga final.
2. `JALANKAN_DEMO.bat` — menu untuk membuat pesanan contoh sendiri.
3. `JALANKAN_TELEGRAM_DEMO.bat` — mencoba format chat cek DP di terminal.
4. `JALANKAN_TEST.bat` — pemeriksaan otomatis; akhir yang diharapkan `TES LULUS.`.

Demo Telegram ini tidak terhubung ke bot sungguhan. Perintah baru di bot utama
baru tersedia setelah integrasi yang Anda perintahkan berikutnya.

Atau, dari root repository, PowerShell/Git Bash:

```bash
py -3 -B "di kerjakan oleh Chatgpt/demo.py" --sample
```

Jendela `.bat` sengaja menunggu tombol ditekan agar pesan hasil/error bisa dibaca.
Jika Python tidak ditemukan, gunakan instalasi Python 3.11+ yang menjalankan
AI Assistant. Bila diperlukan, kirim screenshot pesan tersebut.

## 5. Setelah demo cocok

Minta Claude membaca `README_UNTUK_CLAUDE.md` dari folder ini, membaca kode serta
hasil pengujiannya, lalu menyusun perubahan integrasi berdasarkan kode terbaru.
Pemindahan file saja belum menyambungkan Midtrans, Nara, atau Laras.
