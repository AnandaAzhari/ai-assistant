# Finance SaaS v1

## Working Name
Taqi FinanceDesk (working title; dapat diganti nanti)

## Tujuan
Membuat aplikasi SaaS keuangan harian dan bulanan yang terhubung ke Finance Agent, Telegram Admin, database utama, Google Sheets dashboard, dan Receipt Intake dari foto struk.

## Sasaran V1
- Mudah dipakai dari HP, tablet, dan desktop.
- Catat pemasukan/pengeluaran dalam beberapa detik.
- Upload/foto struk lalu AI membuat draft transaksi.
- Pisahkan keuangan per usaha dan personal.
- Dashboard harian, bulanan, dan per usaha.
- Sinkron ke Google Sheets tanpa menjadikan Sheet sebagai database utama.
- Terhubung ke Lead Agent dan Telegram Admin.

## Modul Utama
### 1. Dashboard
Tampilkan:
- saldo total dan per akun,
- pemasukan hari ini/bulan ini,
- pengeluaran hari ini/bulan ini,
- arus kas bersih,
- laba/rugi sederhana,
- piutang/utang,
- tren 12 bulan,
- pemasukan per usaha,
- pengeluaran per kategori,
- transaksi needs_review.

### 2. Transaksi
- tambah/edit melalui amendment,
- filter tanggal, usaha, kategori, akun, status,
- pencarian,
- attachment/reference struk,
- audit history.

### 3. Receipt Inbox
Sumber foto:
- kamera/upload SaaS,
- Telegram Admin,
- sumber terotorisasi lain.

Status:
- uploaded,
- extracting,
- needs_review,
- confirmed,
- rejected,
- duplicate_suspected.

Preview hasil AI sebelum transaksi final untuk confidence sedang/rendah.

### 4. Akun & Saldo
Contoh: Cash, BCA, BNI, SeaBank, Bank Jago, QRIS, e-wallet.

V1 menghitung saldo dari ledger + saldo awal.
Tidak melakukan koneksi bank otomatis dulu.

### 5. Usaha
Multi-business ledger:
- Taqi DocuTech,
- Pixiva.ID,
- Computer Service,
- Risol Mamqi,
- Personal.

### 6. Laporan
- harian,
- mingguan,
- bulanan,
- arus kas,
- laba/rugi sederhana,
- piutang,
- utang,
- per usaha,
- per kategori,
- export/share.

### 7. Telegram Admin
Telegram berfungsi sebagai quick-entry dan control plane.
Contoh:
- "Catat keluar 80 ribu beli tinta, DocuTech, BCA"
- kirim foto struk,
- /saldo,
- /hari_ini,
- /bulan_ini,
- /piutang,
- approve/reject receipt draft,
- menerima alert sync/security/anomali.

### 8. Google Sheets
Google Sheets menjadi dashboard/reporting mirror sesuai docs/google_sheets_sync.md.

## Receipt AI Flow
Foto Struk
→ File Security Check
→ Receipt Inbox
→ Vision Extraction
→ Normalization
→ Duplicate Check
→ Confidence Score
→ Draft Transaction
→ Auto-confirm atau Owner Review
→ Finance Ledger
→ Google Sheets Sync
→ Dashboard/Telegram Report

## Data Model Minimum
### Transaction
- transaction_id
- date/time
- type: income/expense/transfer/receivable/payable/adjustment
- business_id
- category_id
- account_id
- amount
- description
- source
- order_id optional
- status
- receipt_id optional
- created_by
- created_at
- updated_at

### Receipt
- receipt_id
- file_reference
- source_channel
- merchant
- receipt_number optional
- transaction_date
- extracted_total
- extraction_confidence
- duplicate_score
- status
- raw_extraction_json secured
- created_at

### Audit Event
- event_id
- actor
- action
- entity_type
- entity_id
- before/after reference
- timestamp

## Hak Akses
V1 minimal:
- OWNER: akses penuh + approval.
- AGENT: akses sesuai permission.
- VIEWER/STAFF: opsional tahap berikutnya.

## Keamanan
- .env/secret store untuk credential.
- Owner authentication.
- Telegram admin allowlist.
- Attachment quarantine/security policy.
- Least privilege.
- No hard delete ledger.
- Audit trail.
- Rate limit.
- Backup database.
- DEV dan PRODUCTION terpisah.

## Tech Direction
Rekomendasi awal:
- Frontend SaaS: web responsive/PWA.
- Core/API: TypeScript/Node.js.
- Finance database: SQLite untuk local prototype, kemudian PostgreSQL saat SaaS multi-device/production.
- ML/vision worker: Python atau model vision provider melalui adapter.
- Agent runtime/orchestration: modular; OpenClaw dapat dipakai tanpa membuat finance data bergantung pada OpenClaw.
- Google Sheets melalui Sync Adapter.

## Batas V1
Belum perlu:
- transfer uang otomatis,
- koneksi bank live,
- pajak/akuntansi formal penuh,
- payroll,
- inventory accounting kompleks,
- multi-tenant publik untuk pelanggan luar.

V1 fokus menjadi sistem keuangan internal owner yang stabil terlebih dahulu.

## Roadmap Setelah V1
1. Rekonsiliasi mutasi bank/e-wallet.
2. Budget dan target pengeluaran.
3. Recurring transactions.
4. Forecast cashflow.
5. Deteksi anomali/fraud internal.
6. Multi-user/staff roles.
7. Multi-tenant SaaS jika ingin dijual ke usaha lain.

## Versi
- v1.0-draft
