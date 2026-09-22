# Pekerjaan lanjutan: Nara dan Telegram

Dokumen ini adalah rencana integrasi untuk Claude. Tahap di bawah belum dinyatakan
selesai hanya karena prototipe dan format contoh telah lulus pengujian.

## Alur yang dituju

Brief dan harga disetujui → pembayaran awal terverifikasi → antrean Nara →
riset/draft serta pemeriksaan sumber → Word/PDF dengan format yang disetujui →
pratinjau versi hasil → persetujuan → pelunasan → penyerahan file final.

Owner memantau DP dan pelunasan melalui bot admin Telegram yang sudah ada.
Pekerjaan rutin tidak mengharuskan owner membuka menu terminal demo.

## Urutan integrasi

| Tahap | Pekerjaan Claude | Hasil yang perlu dibuktikan |
| --- | --- | --- |
| 1. Cocokkan aplikasi terbaru | Baca payment gate, ledger, Nara, dan routing Telegram asli; tentukan pemetaan order/invoice/sesi Nara | Satu sumber status pembayaran; tidak ada kredit atau pekerjaan ganda |
| 2. Hubungkan antrean ke Nara | Siapkan instance/workspace per order, checkpoint, batas retry, dan heartbeat untuk pekerjaan lama | Nara mulai setelah syarat pembayaran terpenuhi dan dapat pulih setelah restart |
| 3. Pertahankan format | Gunakan DocumentEngine, CitationEngine, Source Registry, dan preferensi pelanggan asli | Format yang disetujui tetap berlaku; sumber nyata diverifikasi; Word/PDF sesuai |
| 4. Hubungkan pratinjau | Gunakan PDF hasil Word sebagai sumber watermark dan ikat persetujuan ke hash versi | File berubah ditahan; persetujuan lama tidak berlaku pada versi baru |
| 5. Hubungkan Telegram admin | Pasang handler melalui router/bot yang sudah ada dengan identitas owner terverifikasi | Owner dapat memeriksa pembayaran; pesan orang lain/grup tidak mengonfirmasi pembayaran |
| 6. Hubungkan penyerahan | Gunakan antrean pengiriman persisten, deduplikasi, bukti kirim, dan penanganan gagal | File dikirim setelah persetujuan dan lunas; status terkirim hanya sesudah berhasil |

Kontrak rinci `claim_next`, `heartbeat`, `complete`, `approve_result`, serta
`release_result` tersedia dalam `README_UNTUK_CLAUDE.md`. `PreparedNaraWorker`
hanya menerima Nara dengan draft siap dan kedua file final tersedia. Pengumpulan
brief, persetujuan kerangka, riset, dan pembuatan draft belum dilakukan adapter itu.

## Pemetaan ke aplikasi utama

Path berikut relatif terhadap root repository. Baca versi terbarunya saat integrasi;
file Python utama sengaja tidak digandakan ke folder prototipe.

| Area | File yang perlu diperiksa |
| --- | --- |
| Nara dan pembuatan dokumen | `app/document_agent.py`, `app/document_engine.py`, `app/citation_engine.py` |
| Aturan dokumen | `policies/document_format_policy.md`, `policies/document_type_structure_policy.md`, `skills/document_academic/` |
| Pembayaran/preview yang sudah ada | `app/payment_gate.py`, `app/pdf_watermark.py`, `app/approval_gate.py` |
| Routing/admin | `app/lead.py`, `app/admin_runtime.py`, `app/telegram.py`, `telegram_main.py` |
| Kanal pelanggan | `whatsapp_main.py` |
| Keuangan/order | `app/finance.py`, `app/order_status.py`, `app/customer_book.py` |

## Ketentuan saat menyambungkan

- `simulate_payment` dan `/simulasi_midtrans` hanya untuk demo. Status uang nyata
  berasal dari verifikasi merchant/konfirmasi owner yang sah atau adapter provider
  terverifikasi. AI tidak menentukan bahwa pembayaran sudah masuk.
- Gunakan bot Telegram yang sudah berjalan melalui satu jalur polling/webhook.
  Menjalankan polling kedua dengan token sama dapat mengganggu bot utama.
- `delivered` pada prototipe hanya berarti file disalin lokal. Pemetaan produksi
  harus membedakan file siap kirim, pengiriman berlangsung, dan benar-benar terkirim.
- Seluruh test prototipe menggunakan data terpisah. Jangan arahkan DemoStore ke
  database produksi. Integrasi membutuhkan pemetaan/migrasi yang sesuai aplikasi.
- Pemilihan Claude/OpenAI sebagai provider lead baru sebatas saran dalam diskusi;
  belum ada keputusan aktivasi. Gunakan konfigurasi dan adapter yang benar-benar
  tersedia, serta anggaran yang ditetapkan owner saat melakukan uji API berbayar.
- Tidak perlu menguji ulang uang sungguhan untuk membuktikan unit test. Lakukan
  tes adapter dengan pengganti terkontrol, kemudian uji integrasi terbatas sesuai
  lingkungan dan layanan yang memang hendak diaktifkan owner.

## Kriteria sebelum menyatakan integrasi selesai

Tes berikut perlu dicatat sebagai hasil integrasi baru, terpisah dari 94 tes demo:

1. Alur Nara asli dapat menghasilkan Word/PDF dari brief dan sumber terverifikasi.
2. DP belum cukup, harga belum disetujui, atau brief belum lengkap menahan pengerjaan.
3. Pembayaran berulang/restart tidak menggandakan pencatatan atau enqueue.
4. Preview yang belum disetujui atau sisa tagihan positif menahan pengiriman final.
5. Hash/versi berubah memerlukan review baru.
6. Pengiriman Telegram/kanal pelanggan yang gagal dapat diulang tanpa klaim terkirim palsu.
7. Regresi aplikasi utama lulus dan format Word/PDF tetap sesuai acuan owner.

Laporan berikutnya harus menyebut commit, lingkungan, skenario yang benar-benar
dijalankan, hasil, dan bagian yang belum dicoba.
