# TaqiDesk Integration Notes

## Status
Hasil pembacaan struktur internal `AnandaAzhari/taqi-desk` untuk integrasi AI Assistant. Dokumen ini belum mengubah kode TaqiDesk.

## Temuan Utama

### Database
- Desktop dan web memakai kelas `desktop.storage.Store` yang sama.
- Database utama berada di `riwayat.sqlite3` di folder data TaqiDesk.
- SQLite memakai foreign keys dan transaksi eksplisit untuk operasi penting.
- Jangan membuat AI Assistant menulis langsung ke file SQLite. Gunakan adapter/API yang memanggil method `Store` agar validasi, migration, idempotency, dan audit operasional tidak dilewati.

### Pesanan
Tabel/operasi penting sudah tersedia:
- `orders`
- `order_requests` untuk idempotency pembuatan order
- `work_events` untuk riwayat pengerjaan
- `attachments`
- `print_links`
- `print_events`

`OrderOperations` sudah menyediakan operasi seperti:
- baca detail order,
- daftar order untuk hub,
- update status dengan revision check,
- attachment,
- link batch cetak,
- konfirmasi cetak.

Revision pada order berguna untuk mencegah dua proses menimpa perubahan yang sama secara diam-diam.

### Pembayaran
Pembayaran disimpan terpisah pada tabel `payments`.

Fitur yang sudah ada:
- pembayaran bertahap,
- token unik/idempotency,
- metode pembayaran,
- koreksi/void dengan alasan,
- perhitungan sisa tagihan,
- perlindungan pembayaran nontunai melebihi sisa tagihan.

Finance Agent sebaiknya membaca event pembayaran dari TaqiDesk dan membuat event pemasukan dengan `source_ref` stabil. Jangan menghitung pemasukan hanya dari flag `paid`.

### Laporan
`desktop.business.period_report()` sudah membedakan:
- nilai pesanan berdasarkan tanggal order,
- penerimaan kas berdasarkan tanggal pembayaran,
- pembayaran void,
- metode pembayaran,
- sisa tagihan.

Ini dapat menjadi sumber awal untuk ringkasan DocuTech, tetapi Finance Agent tetap mempunyai ledger keuangan sendiri untuk menyatukan semua usaha dan pengeluaran.

### Web Server
Web lokal memakai:
- Flask,
- Waitress,
- password hash,
- session cookie,
- CSRF,
- host validation untuk localhost/LAN,
- rate limiting login sederhana.

Endpoint browser sudah tersedia untuk order, pembayaran, attachment, laporan, dan backup.

## Keputusan Integrasi
API browser yang ada tidak digunakan langsung oleh AI Assistant karena autentikasinya dirancang untuk sesi manusia + CSRF.

V1 yang disarankan:

AI Assistant
→ `TaqiDeskAdapter`
→ localhost-only Agent API di TaqiDesk
→ `Store` / `OrderOperations`
→ `riwayat.sqlite3`

## Agent API yang Disarankan
Tahap pertama read-mostly:
- `GET /internal/agent/v1/health`
- `GET /internal/agent/v1/orders`
- `GET /internal/agent/v1/orders/<id>`
- `GET /internal/agent/v1/report?start=...&end=...`

Tahap berikutnya setelah policy/approval:
- create order dengan idempotency key,
- update status dengan revision,
- attachment aman,
- payment event hanya melalui policy yang jelas.

## Security Boundary
- Default bind `127.0.0.1`, bukan internet.
- Secret agent API disimpan di environment lokal, bukan GitHub.
- Gunakan header auth khusus dan constant-time comparison.
- Jangan reuse password web owner sebagai API key.
- Semua write memakai idempotency key.
- Operasi sensitif tetap melalui Approval Policy.
- AI Assistant tidak boleh menjalankan SQL bebas.

## Hubungan dengan Finance Agent
Contoh event:

TaqiDesk payment confirmed
→ TaqiDeskAdapter
→ Finance Agent
→ cek `source_event_id`
→ ledger pemasukan
→ Google Sheets sync
→ laporan Telegram

Transfer, pengeluaran operasional, dan transaksi personal tetap berasal dari Finance Agent, bukan database TaqiDesk.

## Rekomendasi Urutan
1. Selesaikan Telegram Admin minimum dan uji allowlist.
2. Aktifkan Finance runtime minimum.
3. Buat TaqiDesk Agent API read-only.
4. Hubungkan `TaqiDeskAdapter` dari AI Assistant.
5. Sinkronkan payment event ke Finance Agent secara idempotent.
6. Baru tambahkan write actions TaqiDesk yang memerlukan approval.
