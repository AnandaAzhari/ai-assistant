# Google Sheets Sync Rules

## Tujuan
Menjadikan Google Sheets sebagai dashboard, reporting layer, dan tempat review yang mudah diakses tanpa menjadikannya database utama.

## Source of Truth
Database Finance Service/SQLite adalah source of truth utama.
Google Sheets adalah mirror/reporting layer.

Jika terjadi konflik, database utama menang kecuali owner secara eksplisit mengonfirmasi koreksi dari Google Sheets melalui proses import/reconciliation.

## Arah Sinkronisasi
### Default: One-way
Database -> Google Sheets.

Semua transaksi confirmed disinkronkan ke tab Transaksi dan metrik dashboard diperbarui.

### Manual Review Import
Perubahan manual di Google Sheets tidak langsung menimpa database.
Perubahan tersebut masuk status pending_import/review dan harus divalidasi sebelum diterapkan.

## Identitas Data
Setiap transaksi wajib memiliki transaction_id UUID yang stabil.
Jangan memakai nomor baris Google Sheets sebagai ID transaksi.

Setiap event sinkronisasi memiliki source_event_id/idempotency_key untuk mencegah duplikasi.

## Kolom Minimum Transaksi
- transaction_id
- tanggal
- waktu
- jenis
- usaha
- kategori
- deskripsi
- akun/metode pembayaran
- nominal
- status
- sumber
- order_id
- catatan
- dibuat_oleh
- created_at
- receipt_url/reference
- receipt_id
- extraction_confidence
- sync_status
- source_event_id
- last_synced_at

## Status Sinkronisasi
- pending
- synced
- retrying
- conflict
- failed

## Idempotency
Sebelum menambah baris baru, Sync Adapter harus mencari transaction_id/source_event_id yang sama.
Jika sudah ada, lakukan update pada record yang sama, bukan append duplikat.

## Retry
Jika Google Sheets tidak tersedia:
1. transaksi tetap dianggap berhasil jika sudah tersimpan di database utama,
2. simpan sync job sebagai pending,
3. retry dengan exponential backoff,
4. setelah batas retry tertentu, ubah menjadi failed dan kirim alert Telegram,
5. jangan membuat transaksi finansial duplikat akibat retry.

## Konflik
Contoh konflik:
- nominal Sheet berbeda dengan database,
- transaction_id sama tetapi usaha/kategori berbeda,
- baris dihapus manual,
- transaksi database sudah reversed tetapi Sheet masih active.

Aksi default: jangan overwrite diam-diam. Tandai conflict dan kirim ke owner untuk review jika perubahan berpengaruh ke laporan.

## Koreksi Transaksi
Tidak ada hard delete dari ledger.
Koreksi dilakukan dengan amendment/reversal sehingga riwayat tetap ada.
Google Sheets harus mencerminkan status terbaru tetapi tetap menyimpan transaction_id dan referensi koreksi.

## Dashboard
Dashboard membaca dari data yang sudah synced/confirmed.
Transaksi needs_review, rejected, atau failed tidak ikut angka final kecuali metrik khusus menampilkannya.

Metrik minimum:
- pemasukan hari/bulan
- pengeluaran hari/bulan
- arus kas bersih
- laba/rugi sederhana
- saldo per akun
- piutang
- utang
- pemasukan per usaha
- pengeluaran per kategori
- tren bulanan
- jumlah transaksi needs_review

## Receipt
Google Sheets hanya menyimpan link/reference struk dan metadata ekstraksi. File asli tidak ditanam sebagai data mentah di Sheet.

Jika receipt mengandung data sensitif, akses file mengikuti permission Drive dan retention policy.

## Keamanan
- Credential Google API tidak pernah ditulis di Sheet.
- Sheet tidak boleh berisi PIN, OTP, password, API key, atau secret.
- Hanya service account/OAuth yang terotorisasi yang boleh sinkron.
- Audit log menyimpan setiap sync/write penting.

## Frekuensi Sinkronisasi
V1:
- event-driven setelah transaksi confirmed,
- background retry untuk pending/failed,
- reconciliation harian untuk mendeteksi missing/conflict.

## Rekonsiliasi Harian
Setiap hari sistem membandingkan:
- jumlah transaksi,
- total pemasukan,
- total pengeluaran,
- daftar transaction_id,
- status sync.

Jika selisih ditemukan, kirim alert ke Telegram Admin.

## Versi
- v1.0
