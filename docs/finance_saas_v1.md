# Finance SaaS v1

## Working Name
Taqi FinanceDesk (working title; dapat diganti nanti)

## Tujuan
Membuat aplikasi SaaS keuangan harian dan bulanan yang terhubung ke Finance Agent, Telegram Admin, database utama, Google Sheets dashboard, dan Receipt Intake dari foto struk.

## Keputusan Skema (19 September 2026)
Owner memilih memperkaya Telegram Admin + Google Sheets yang sudah ada, BUKAN membangun
aplikasi web dashboard terpisah (butuh hosting/login sendiri, effort jauh lebih besar,
dan tidak sejalan dengan "Batas V1" di bawah yang memang menyasar sistem internal owner,
bukan produk dijual ke luar). Jadi modul "1. Dashboard" di bawah ini dipenuhi lewat
kombinasi command Telegram (laporan on-demand) + Google Sheets (dashboard visual, lihat
`docs/google_sheets_sync.md`), bukan lewat aplikasi web baru. Bagian ini tetap disimpan
sebagai referensi kalau suatu saat memang ingin dibangun sebagai aplikasi terpisah
(lihat "Roadmap Setelah V1" poin 7, multi-tenant SaaS).

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
Tampilkan (status per command Telegram, 19 September 2026 — lihat "Keputusan Skema"
di atas soal kenapa ini command, bukan aplikasi web):
- [x] saldo total dan per akun — `/saldo`, `/akun`.
- [x] pemasukan/pengeluaran hari ini, minggu ini, bulan ini, per usaha — `/hari_ini
  [usaha]`, `/minggu_ini [usaha]`, `/bulan_ini [usaha]` (`app/finance.py`
  `today_summary`/`week_summary`/`month_summary`, semua terima filter `business`
  opsional).
- [x] arus kas bersih (per periode, sudah ada sejak awal) DAN arus kas per akun
  (saldo awal/masuk/keluar/saldo akhir, baru) — `/arus_kas [akun]`
  (`app/finance.py::cash_flow`).
- [x] laba/rugi sederhana dengan rincian pengeluaran per kategori — `/laba_rugi
  [usaha]` (`app/finance.py::profit_loss`). Catatan: ini pendapatan dikurangi
  seluruh pengeluaran tercatat, BUKAN laporan akuntansi formal dengan pemisahan
  HPP/beban operasional — di luar cakupan V1 (lihat "Batas V1").
- [x] pengeluaran per kategori — bagian dari `/laba_rugi`
  (`app/finance.py::category_breakdown`, method umum yang bisa dipakai laporan lain).
- [ ] piutang/utang — belum ada (lihat gap di bawah).
- [ ] tren 12 bulan — belum ada.
- [ ] transaksi needs_review — Finance Agent sudah punya konsep `needs_review` untuk
  transaksi yang gagal validasi, tapi belum ada command untuk melihat daftarnya
  (saat ini transaksi yang gagal validasi memang tidak pernah tersimpan sama sekali,
  bukan tersimpan dengan status menunggu — lihat `app/finance.py::handle`).

Test untuk semua yang sudah `[x]` di atas: `tests/test_finance_reports.py`.

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
- Taqi Desk,
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
Contoh (yang sudah `[x]` di atas):
- "Catat keluar 80 ribu beli tinta, Taqi Desk, BCA"
- /saldo, /akun, /kategori
- /hari_ini, /minggu_ini, /bulan_ini (opsional filter usaha)
- /laba_rugi, /arus_kas (opsional filter usaha/akun)
- [x] **Pertanyaan bebas via AI (BARU, 19 September 2026)** — owner tidak wajib
  hafal command, bisa tanya bebas mis. "pemasukan bulan lalu Risol Mamqi berapa?",
  "untung bulan ini berapa?", "saldo BCA sekarang berapa?". Diklasifikasikan AI
  (`app/finance_query.py::FinanceQueryInterpreter`, provider DeepSeek), lalu
  dijawab `FinanceService._answer_free_form_query` memakai method laporan yang
  SAMA dengan command tetap di atas — angka tidak pernah dikarang AI. Kalau AI
  gagal/tidak yakin, otomatis jatuh ke jalur command/pencatatan lama. Detail
  provider: `docs/providers/laras.md`.
- /piutang, /utang — belum ada implementasi, masih placeholder
- kirim foto struk — belum ada (lihat Receipt AI Flow)
- approve/reject receipt draft — belum ada
- menerima alert sync/security/anomali — belum ada

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
- v1.1 (19 September 2026) — Modul 1 (Dashboard, lewat command Telegram) sebagian besar
  selesai: laporan mingguan, laba/rugi, arus kas per akun, dan filter per usaha. Sisa
  gap: piutang/utang, tren 12 bulan, dan seluruh Receipt Inbox (Modul 3) belum ada
  kodenya. Lihat status `[x]`/`[ ]` di tiap modul di atas untuk detail per item.
- v1.2 (19 September 2026, lanjutan hari yang sama) — Modul 7 (Telegram Admin)
  bertambah **pertanyaan keuangan bebas via AI**: owner tidak lagi wajib memakai
  command tetap untuk bertanya laporan, bisa mengobrol bebas dan Laras menjawab
  dari data asli (`app/finance_query.py`). Milestone: pertama kalinya Laras
  terhubung ke provider AI di produksi (lihat `docs/providers/laras.md`).
  Pencatatan transaksi baru dan seluruh command tetap tetap 100% deterministik,
  tidak berubah.
