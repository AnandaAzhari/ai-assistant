# AI Assistant

Kerangka asisten lokal untuk Windows, versi program v0.1. Perintah terminal
diteruskan oleh Lead Agent ke Desktop Agent untuk membuat folder pesanan dan
membuka dokumen melalui aplikasi bawaan Windows.

Mulai dari **[Panduan Windows](docs/PANDUAN_WINDOWS.md)**.

## Menjalankan

Gunakan Python 3.11 atau lebih baru. Tidak perlu paket tambahan atau API key.
Ekstrak repo, lalu klik dua kali `jalankan.bat`, atau buka terminal di folder repo:

```powershell
py -3 main.py
```

Masukkan folder kerja yang sudah ada. Ketik `bantuan` untuk daftar perintah.
Untuk menentukan folder langsung:

```powershell
py -3 main.py --workspace "D:\Pesanan"
```

## Kemampuan versi ini

- `folder`: membuat folder baru dan memeriksa keberadaannya.
- `buka`: meminta Windows membuka file yang ditentukan.
- `pesanan`: membuat folder, lalu membuka file, dengan laporan hasil parsial jika gagal.
- File yang didukung: PDF, TXT, DOCX, XLSX, PPTX, PNG, JPG/JPEG.
- File harus berada di dalam folder kerja; gunakan path tepat, bukan pencocokan nama mirip.
- Folder yang sudah ada dipertahankan. File pelanggan tidak dipindah atau disalin otomatis.
- Tampilan dokumen dikonfirmasi oleh pengguna. Respons dari Windows sendiri belum
  membuktikan bahwa aplikasi menampilkan dokumen dengan benar.

Ini masih router perintah tetap. Pemahaman bahasa bebas, provider AI, WhatsApp,
pembukaan browser, perintah Windows bebas, dan pengaturan sistem belum diimplementasikan.
Panduan `agents/*.md` menjelaskan peran dan cakupan pengembangan; program belum
memuat panduan tersebut sebagai prompt AI.

## Struktur

| Lokasi | Isi |
| --- | --- |
| `agents/` | Panduan peran agen yang telah disepakati |
| `app/lead.py` | Pemilihan tugas Desktop Agent |
| `app/desktop.py` | Pembuatan folder dan permintaan membuka file |
| `main.py` | Terminal dan laporan hasil |
| `jalankan.bat` | Peluncur Windows |
| `docs/PANDUAN_WINDOWS.md` | Pemasangan dan uji manual |
| `tests/` | Pengujian alur, kegagalan, dan batas tindakan |

## Pengujian

```powershell
py -3 -m unittest discover -s tests -v
```

Tes memakai folder sementara dan pengganti pemanggilan pembuka file. Tes tidak
membuka aplikasi sungguhan; uji tampilan Windows tetap dilakukan mengikuti panduan.
