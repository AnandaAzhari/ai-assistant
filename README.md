# AI Assistant

Kerangka asisten lokal untuk Windows. Proyek ini memisahkan AI Assistant Core dari aplikasi bisnis seperti TaqiDesk.

## Web Admin / PWA v0.1

Web Admin minimum sekarang tersedia untuk menguji jalur:

`Browser -> Web Admin -> Lead Agent`

Fitur awal:
- chat ke Lead Agent,
- slash command seperti `/status`, `/saldo`, `/hari_ini`, `/bulan_ini`, dan `/antrean`,
- status komponen sistem,
- voice input Bahasa Indonesia melalui speech recognition browser bila didukung,
- opsi membacakan jawaban melalui text-to-speech browser,
- manifest + service worker dasar agar fondasi PWA sudah tersedia.

Jalankan di Windows dengan klik dua kali:

```text
JALANKAN_WEB_ADMIN.bat
```

Lalu buka:

```text
http://localhost:8081
```

Tahap v0.1 sengaja hanya localhost. Akses tablet/HP melalui LAN + HTTPS akan ditambahkan setelah alur lokal stabil. Ini penting karena microphone dan instalasi PWA penuh pada browser mobile umumnya memerlukan secure context/HTTPS.

Voice v0.1 memakai kemampuan speech recognition browser. Implementasi ini belum berarti STT berjalan lokal/offline; dukungan dan pemrosesan audio bergantung pada browser/platform. Rencana berikutnya dapat menambahkan STT lokal/provider abstraction agar lebih konsisten.

## Telegram Admin

Telegram Adapter minimum juga tersedia tetapi bersifat opsional. Token dan ID admin hanya dibaca dari `.env` lokal dan tidak boleh masuk GitHub.

## Terminal Windows lama

Perintah terminal Desktop Agent tetap tersedia. Mulai dari **[Panduan Windows](docs/PANDUAN_WINDOWS.md)**.

Gunakan Python 3.11 atau lebih baru. Untuk terminal lama:

```powershell
py -3 main.py
```

Perintah:
- `folder`: membuat folder baru dan memeriksa keberadaannya.
- `buka`: meminta Windows membuka file yang ditentukan.
- `pesanan`: membuat folder, lalu membuka file.

## Arsitektur arah pengembangan

```text
Web/PWA ----\
Telegram ----> Lead Agent -> Specialist Agent -> Tools/Services
Discord  ----/                    |
                                  +-> Finance Service
                                  +-> TaqiDesk Adapter
                                  +-> Desktop Agent
```

Web/PWA adalah control plane utama yang direncanakan. Telegram/Discord menjadi adapter tambahan, bukan pusat business logic.

## Struktur penting

| Lokasi | Isi |
| --- | --- |
| `agents/` | Panduan peran agent |
| `app/lead.py` | Lead Agent/router minimum |
| `app/desktop.py` | Desktop Agent |
| `app/telegram.py` | Telegram Admin adapter |
| `app/web_admin.py` | HTTP server Web Admin minimum |
| `web_admin/` | UI, slash command, voice, dan PWA assets |
| `JALANKAN_WEB_ADMIN.bat` | Peluncur Web Admin Windows |
| `docs/` | Arsitektur, Finance, Telegram, dan catatan integrasi TaqiDesk |
| `tests/` | Pengujian alur dan batas tindakan |

## Pengujian

```powershell
py -3 -m unittest discover -s tests -v
```

Tes tidak membuktikan perilaku microphone atau UI browser secara penuh; keduanya tetap perlu diuji manual pada perangkat nyata.
