# Serah-terima prototipe harga dan pembayaran kepada Claude

## Keputusan dan batas pekerjaan owner

Owner meminta kode `.py` yang dapat dicoba dahulu dalam folder persis
`di kerjakan oleh Chatgpt`, sebelum diintegrasikan ke aplikasi sebenarnya.
Pada tahap prototipe ini semua perubahan dibatasi ke folder tersebut.
Harga masih usulan yang dapat diedit; instruksi mengerjakan demo tidak berarti
tarif ini sudah disahkan untuk pelanggan produksi.

Arahan lanjutan owner: **modul ini ditujukan untuk AI agent, dan owner cukup
mengecek DP/pelunasan melalui Telegram**. Demo terminal adalah alat pengujian;
produk akhirnya bukan aplikasi kasir terpisah yang wajib dibuka owner.

Jangan otomatis mengaktifkan kode ini pada runtime utama hanya karena foldernya
ada. Saat owner memberi perintah integrasi, perintah itu menjadi dasar untuk
mengubah bagian utama yang diperlukan. Periksa perubahan lokal owner/agen lain
dan versi repository terbaru sebelum mengedit; jangan menimpa pekerjaan mereka.

## Acuan repository saat dibuat

- Repository: `AnandaAzhari/ai-assistant`.
- Acuan main: `f49aff17e764c9bc32e5be493c5038cf52dfe307`.
- `app/finance.py`: ledger keuangan lokal, belum rekonsiliasi bank atau gateway.
- `app/order_status.py`: status pesanan yang diisi admin.
- `app/customer_book.py`: catatan pelanggan/order yang berbeda dari ledger.
- `app/lead.py`: routing admin/pelanggan; belum alur tagihan pembayaran.
- `whatsapp_main.py`: webhook khusus Meta; bukan endpoint pembayaran.
- `app/web_admin.py`: API admin; jangan membukanya tanpa autentikasi untuk gateway.
- `app/telegram.py`: `TelegramAdminAdapter`, `AdminIdentity`, pengiriman pesan,
  dan jurnal update/balasan yang perlu dipakai kembali saat integrasi.
- `app/admin_runtime.py`: `create_admin_lead()` menyusun layanan admin bersama.

Periksa ulang file tersebut saat integrasi. Acuan di atas adalah checkpoint,
bukan klaim bahwa semua file akan selalu sama.

## Cara menjalankan dan bagian yang dapat dipakai

Python 3.11+, standard library saja. Dari folder ini:

```bash
python -B -m unittest discover -s tests -p 'test_*.py' -v
python -B demo.py --sample
python -B demo.py --telegram-demo
```

- `chatgpt_billing/pricing.py` menghasilkan `Quote` immutable dengan rincian dan
  syarat pembayaran. Input uang berupa integer rupiah; tidak ada float.
- `make_quote(QuoteRequest(...))` membaca konfigurasi default relatif terhadap
  file modul, bukan current working directory. Objek config bisa diberikan eksplisit.
- `Quote.review_reasons` menunjukkan kasus yang memerlukan pemeriksaan operator.
- `DemoStore` menyimpan snapshot penawaran agar perubahan config tidak mengubah
  pesanan yang telah dibuat. Metode menerima `actor` untuk audit demo; identitas
  tersebut belum merupakan autentikasi. Pada produksi actor harus berasal dari
  identitas terverifikasi, bukan teks bebas pelanggan.
- `simulate_payment` sengaja hanya menerima nama sumber berawalan `simulasi_`.
  Ini bukan adapter pembayaran nyata. Jangan membuat endpoint HTTP langsung
  yang meneruskan JSON pelanggan ke fungsi ini.
- `chatgpt_billing/telegram_admin.py` menyediakan `DemoTelegramAdmin.handle()`
  dengan pemeriksaan ID user, ID chat, dan chat pribadi. Perintah di luar modul
  mengembalikan `None` agar tetap ditangani router lama.
- `simulate_payment_update()` mengembalikan `PaymentUpdate` yang dihitung dalam
  transaksi SQLite. `ready_for_work` dan event audit hanya dibuat pada perubahan
  yang benar-benar melewati ambang DP. `AdminReply.ready_order_id` adalah sinyal
  untuk pengait Nara; belum merupakan antrean pekerjaan atau bukti eksekusi.

Contoh pemakaian internal:

```python
from chatgpt_billing.pricing import QuoteRequest, make_quote
from chatgpt_billing.payment_flow import DemoStore

quote = make_quote(QuoteRequest(pages=10))
store = DemoStore()  # :memory:
order = store.create_order(quote, approved_by="operator-demo")
store.accept_quote(order.order_id, actor="pelanggan-demo")
store.simulate_payment(order.order_id, "DEMO-DP-001", 18000)
assert store.get(order.order_id).can_start
store.close()
```

Folder luar mengandung spasi sesuai permintaan owner. Package di dalamnya bernama
`chatgpt_billing` agar valid untuk import Python. Demo mengatur konteks import dari
lokasi script; tidak menambahkan folder ini ke runtime produksi. Saat integrasi,
tetapkan lokasi package yang sesuai arsitektur terbaru dan ubah import secara eksplisit.

## Perilaku yang sudah diuji

1. Paket, halaman tambahan, minimum jasa rapikan, dan tambahan footnote.
2. Perapian dasar makalah sudah termasuk; bundle footnote tidak dihitung ganda.
3. Harga di bawah/sama dengan ambang memakai pembayaran penuh; selebihnya DP.
4. Persetujuan harga dan DP cukup harus mendahului pengerjaan.
5. Status pending/deny/expire tidak menambah saldo pembayaran.
6. Notifikasi sukses berulang, termasuk dari dua koneksi, hanya dikreditkan sekali.
7. Referensi yang sama dengan nominal/order berbeda ditolak.
8. Pratinjau disetujui dan pembayaran lunas sebelum final.
9. Revisi pelanggan mengurangi jatah; koreksi kesalahan penyedia tidak.
10. Snapshot, riwayat, dan deduplikasi tetap tersimpan setelah restart.
11. Pembayaran berlebih atau setelah pembatalan memerlukan pemeriksaan manual.
12. Database tanpa penanda demo ditolak; tidak mengubah database contoh produksi.
13. Owner dapat cek DP, konfirmasi manual, dan cek sisa tagihan dari pengendali Telegram.
14. Pengguna lain/grup ditolak; perintah lama seperti `/saldo` tidak diambil alih.
15. Konfirmasi owner bersamaan atas transaksi yang sama hanya menghasilkan satu
    sinyal kesiapan kerja. Konfirmasi lunas dengan nominal kurang tidak memaksa lunas.

Lihat `HASIL_PENGUJIAN.md`. Tes baru tidak membuktikan koneksi layanan eksternal
atau integrasi dengan seluruh aplikasi utama.

## Rencana integrasi bertahap setelah diperintahkan owner

### 1. Tetapkan penawaran dan pengait ke alur Nara

- Konfirmasi tarif final, aturan pemilihan paket, lingkup, deadline, revisi, dan
  penanganan pembatalan/refund. Paket otomatis menggunakan kapasitas, bukan biaya termurah.
- Harga dihitung oleh kode dari konfigurasi server. AI hanya mengumpulkan data;
  jangan mempercayai total harga yang dikirim pelanggan atau dikarang model.
- Simpan order/invoice yang nyata dan hubungkan ke identitas pelanggan, usaha,
  sesi Nara, serta persetujuan penawaran.
- Letakkan gerbang pembayaran setelah brief dan penawaran disetujui, sebelum
  riset/draft berbayar. Konsultasi singkat dan estimasi dapat mendahului DP.
- Tambahkan pengait ke alur final yang benar-benar mengirim file; status demo
  `delivered` tidak boleh dianggap bukti bahwa pesan/file telah terkirim.

### 1b. Sambungkan admin Telegram yang sudah ada

- Owner memakai bot admin yang sama. Jangan membuat polling kedua dengan token
  yang sama, karena bisa mengganggu runtime `telegram_main.py` yang sedang berjalan.
- Gunakan identitas owner dari konfigurasi/runtime asli (`AdminIdentity`);
  jangan menyalin ID `1` atau `42` dari demo/tes ke produksi.
- Pertahankan pemeriksaan private chat dan allowlist di `TelegramAdminAdapter`.
  Hubungkan handler pembayaran pada routing admin, bukan routing WhatsApp pelanggan.
  Jangan mengambil `user_id`/`chat_id` dari teks pesan.
- Alur QRIS statis: owner melihat transaksi masuk di aplikasi merchant, lalu
  `/dp_konfirmasi` atau `/lunas_konfirmasi` mencatatnya melalui Telegram dengan audit.
- Alur Midtrans: notifikasi provider terverifikasi memperbarui invoice, kemudian
  kirim ringkasan DP/pelunasan ke Telegram owner; tidak perlu menunggu konfirmasi
  manual tambahan untuk setiap pembayaran Midtrans yang sudah sah.
- `payment_notice()` hanya memformat pesan. Gunakan pengirim dan pemecah pesan
  Telegram yang sudah ada serta outbox/retry persisten. Jangan mengirim ke chat
  yang ditentukan pelanggan.
- Pisahkan status pekerjaan dari pembayaran. Setelah DP cukup, lanjutkan pekerjaan
  Nara tepat satu kali melalui pekerjaan persisten yang tahan restart; hasil return
  Python saja bisa hilang jika proses crash sesudah transaksi tersimpan.
- Hilangkan/nonaktifkan `/simulasi_midtrans` dari runtime produksi. Jalur pelanggan
  tidak boleh dapat memanggil metode simulator untuk membuka gerbang pengerjaan.

### 2. Adapter Midtrans sandbox

- Bangun adapter tersendiri untuk membuat tagihan dengan ID dan nominal yang
  terikat pada invoice tersimpan. Tagihan DP dan pelunasan memiliki ID masing-masing.
- Gunakan environment sandbox dan kunci di server. Jangan meminta kunci di chat
  atau menyimpannya dalam Git. Tidak ada kunci yang dibutuhkan oleh demo ini.
- Buat endpoint HTTPS publik khusus pembayaran. Keberadaan webhook WhatsApp
  tidak otomatis membuatnya kompatibel dengan notifikasi Midtrans.
- Verifikasi notifikasi sesuai dokumentasi resmi dan cocokkan order ID, nominal,
  akun merchant/environment, currency, serta status terhadap invoice tersimpan.
- Gunakan Get Transaction Status untuk rekonsiliasi/kasus meragukan dan notifikasi
  terlambat. Screenshot, ucapan pelanggan, redirect browser, atau teks AI tidak
  cukup untuk menandai invoice terbayar.
- Tentukan aturan status tiap metode pembayaran; simulasi ini hanya memodelkan
  pending/settlement/expire/deny untuk pembahasan QRIS. Jangan menganggapnya
  implementasi lengkap semua metode Midtrans.

Dokumentasi yang perlu diperiksa ulang ketika membangun adapter:

- https://docs.midtrans.com/reference/qris
- https://docs.midtrans.com/docs/https-notification-webhooks

### 3. Persistensi, pengiriman, dan ledger

- Jangan mengarahkan `DemoStore` ke `data/assistant.db`. Gunakan migrasi produksi
  yang ditinjau dan diuji dengan salinan database.
- Simpan notifikasi mentah yang diperlukan secara aman ke inbox persisten sebelum
  menganggapnya ditangani; gunakan deduplikasi provider/merchant/transaction ID.
- Pastikan pembaruan pembayaran, invoice, dan event untuk ledger atomik atau
  memakai outbox/retry yang aman. Retry setelah crash tidak boleh menggandakan pemasukan.
- Catat DP dan pelunasan satu kali sesuai penerimaan. Memasukkan nilai order penuh
  ke Customer Book tidak otomatis menjadi pemasukan.
- Bedakan nilai bruto pesanan, biaya gateway, dana yang belum cair, dan pencairan
  ke bank. Saldo pembayaran demo bukan saldo rekening atau laporan akuntansi.
- Notifikasi terlambat, salah nominal, kelebihan bayar, refund, dan pembatalan
  memerlukan pencatatan/rekonsiliasi. Demo hanya menolak kasus tersebut; sistem
  nyata harus menyimpan kejadian agar uang tidak hilang dari pelacakan.
- Pakai antrean pengiriman persisten untuk pesan dan file. Jangan menandai terkirim
  hanya karena pembayaran berhasil; tangani kegagalan pengiriman dan pengulangan.

### 4. Pratinjau, revisi, dan pengujian integrasi

- Bangun PDF pratinjau yang benar-benar terlindungi sesuai keputusan produk.
  Referensi `DEMO-pratinjau-watermark.pdf` hanyalah teks contoh.
- Gerbang final harus melindungi semua jalur: WhatsApp, tautan unduh, dan alat
  admin yang relevan. Pertahankan isolasi data pelanggan.
- Terapkan batas waktu revisi bila disepakati; belum ada timer di prototipe.
- Tambahkan tes dengan adapter palsu untuk kegagalan provider, retry, restart,
  notifikasi paralel, nominal salah, dan pengiriman file gagal. Lalu uji sandbox
  Midtrans end-to-end sebelum mempertimbangkan transaksi nyata.
- Jalankan pengujian integrasi dan regresi aplikasi utama pada commit terbaru.
  Jangan menyatakan aplikasi siap produksi hanya berdasarkan tes prototipe ini.

## Batas yang masih terbuka

Belum ada adapter Midtrans live/sandbox, API/layar pelanggan, autentikasi baru,
penghubung TaqiDesk, posting ledger Laras, real PDF watermark, pengiriman file,
refund, batas revisi berbasis waktu, cetak/jilid, fee provider, atau pajak.
Tidak ada penggunaan internet oleh kode demo maupun tesnya.
