# Mulai di sini — serah terima untuk Claude

## Status yang telah disepakati

Owner meminta seluruh hasil kerja ChatGPT, kode, bukti pengujian, dan bahan baca
Claude tetap berada dalam folder **`di kerjakan oleh Chatgpt`**. Perubahan paket
serah terima ini tidak mengaktifkan integrasi pada aplikasi utama.

**Seluruh 94 tes otomatis prototipe lulus: 0 gagal, 0 error, 0 skip.**
Word, PDF final, dan pratinjau contoh telah diperiksa secara visual pada pengujian
ChatGPT. Setelah mencoba perbaikan, owner menyatakan: **“hasilnya sudah sesuai”**.
Format tersebut menjadi acuan yang sudah disetujui untuk kelanjutan pekerjaan.

Pernyataan lulus berlaku untuk prototipe dan skenario yang tercatat dalam
`HASIL_PENGUJIAN.md`. Integrasi Nara dengan model asli, Telegram sungguhan,
Midtrans, dan pengiriman pelanggan belum diuji oleh paket ini. Jangan menyebut
seluruh aplikasi utama atau alur produksi sudah lulus berdasarkan 94 tes ini.

## Urutan membaca

| Urutan | File/lokasi | Tujuan |
| --- | --- | --- |
| 1 | `01_FORMAT_DAN_PERSETUJUAN_OWNER.md` | Format yang disetujui serta batas persetujuan |
| 2 | `HASIL_PENGUJIAN.md` | Skenario, hasil visual, dan batas verifikasi |
| 3 | `bukti_uji/hasil_unit_test.json` | Hasil tes ulang, log asli yang dinormalisasi, lingkungan, dan hash kode |
| 4 | `README_UNTUK_CLAUDE.md` | Kontrak API, arsitektur antrean, dan rincian adapter Nara |
| 5 | `02_LANJUTAN_NARA_TELEGRAM.md` | Urutan pekerjaan integrasi berikutnya |
| 6 | `referensi/README.md`, lalu empat pedoman di folder itu | Salinan aturan format/sitasi yang digunakan |
| 7 | `chatgpt_billing/`, `tests/`, `workflow_demo.py`, `demo.py` | Implementasi dan pengujian yang tersedia |
| 8 | `README.md`, `config_harga.json` | Lingkup jasa dan usulan harga; persetujuan format bukan pengesahan tarif |
| 9 | `CARA_GIT_PULL.md`, `PANDUAN_ANTREAN.md` | Langkah Windows dan reproduksi demo |

## Peta kode

| File | Peran |
| --- | --- |
| `chatgpt_billing/pricing.py` | Penawaran dan aturan nominal pembayaran |
| `chatgpt_billing/payment_flow.py` | Status pembayaran, deduplikasi, snapshot penawaran, audit demo |
| `chatgpt_billing/workflow.py` | Antrean persisten, claim/heartbeat, pemeriksaan, persetujuan, pelepasan lokal |
| `chatgpt_billing/artifacts.py` | Validasi dasar DOCX/PDF dan hash file |
| `chatgpt_billing/project_format.py` | Contoh yang memakai DocumentEngine asli dengan lokasi keluaran terpisah |
| `chatgpt_billing/demo_toc.py` | Pembaruan cache daftar isi khusus contoh untuk pemeriksaan Linux |
| `chatgpt_billing/pdf_preview.py` | Watermark pada salinan PDF hasil konversi DOCX |
| `chatgpt_billing/workers.py` | PreparedNaraWorker untuk draft siap; OfflineDemoWorker hanya fixture tes |
| `chatgpt_billing/telegram_admin.py` | Handler admin pembayaran yang belum disambungkan ke transport Telegram |
| `tests/test_chatgpt_billing.py` | 48 tes harga, pembayaran, dan handler admin |
| `tests/test_workflow.py` | 32 tes antrean dan kontrak adapter |
| `tests/test_project_format.py` | 14 tes format dan pratinjau |

## Cara memulai pekerjaan lanjutan

1. Periksa branch, perubahan lokal, dan versi repository. Pertahankan pekerjaan
   owner/agen lain. Pada main sudah ada payment gate; baca implementasi terbarunya
   sebelum menyatukan alur agar pembayaran tidak dicatat dua kali.
2. Cocokkan kode dengan commit pengujian dan hash dalam `bukti_uji/hasil_unit_test.json`.
3. Gunakan format yang disetujui. Instruksi khusus pelanggan tetap dapat mengganti
   bagian format yang memang diminta; jangan mengubah default atas selera model.
4. Lanjutkan persiapan/adaptor dalam folder ini sesuai arahan owner. Folder ini
   tidak otomatis memberi perintah untuk menyalakan integrasi pada runtime utama.
   Bila owner kemudian memerintahkan integrasi, kerjakan berdasarkan perintah itu.
5. Reproduksi tes dan demo sebelum menyatakan perubahan berikutnya selesai.
   Gunakan environment dan data uji tersendiri.

Kode pengujian acuan: `70771143c0ce8f6b9213a648f50c495e5559307b`.
Source dan pedoman aplikasi utama tetap berada pada lokasi aslinya; salinan
pedoman dalam folder ini adalah bahan baca, bukan pengganti modul runtime.
