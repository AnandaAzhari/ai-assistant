# Telegram Admin v1

## Tujuan
Menjadikan Telegram sebagai control plane utama milik owner untuk berinteraksi dengan Lead Agent, Finance Agent, agent bisnis lain, menerima laporan, memberi approval, dan menerima alert keamanan.

Telegram Admin bukan agent terpisah. Telegram adalah channel/admin interface yang menghubungkan owner ke Lead Agent dan service internal.

## Prinsip Dasar
- Hanya akun Telegram owner yang ada di allowlist yang boleh menjalankan perintah admin.
- Telegram tidak boleh menjadi source of truth untuk data keuangan atau order.
- Semua tindakan penting tetap melewati policy, permission, dan audit log.
- Bot token, admin user ID, chat ID, dan secret tidak boleh disimpan di GitHub.
- Input file/link tetap mengikuti attachment & link security policy.

## Alur Utama
Owner Telegram
→ Telegram Bot Adapter
→ Admin Authentication / Allowlist
→ Lead Agent
→ Specialist Agent
→ Policy & Permission Check
→ Approval Gate jika diperlukan
→ Tool / Service Execution
→ Audit Log
→ Response / Report kembali ke Telegram

## Fitur V1

### 1. Natural Language Command
Owner boleh memberi perintah dengan bahasa biasa, misalnya:
- "Catat pengeluaran 80 ribu beli tinta untuk DocuTech pakai BCA."
- "Berapa pemasukan Pixiva bulan ini?"
- "Tampilkan order yang masih menunggu review."
- "Pause WhatsApp Agent."

Lead Agent menentukan intent dan meneruskan ke agent yang tepat.

### 2. Finance Quick Entry
Telegram dapat digunakan untuk:
- mencatat pemasukan,
- mencatat pengeluaran,
- mencatat transfer antar akun,
- mencatat piutang/utang,
- mengirim koreksi,
- melihat saldo dan laporan.

Contoh shortcut:
- /saldo
- /hari_ini
- /bulan_ini
- /pemasukan
- /pengeluaran
- /piutang
- /utang

Shortcut hanya convenience layer. Bahasa natural tetap menjadi cara utama.

### 3. Receipt Intake
Owner dapat mengirim foto struk/nota ke Telegram.

Alur:
1. File melewati pemeriksaan keamanan dasar.
2. Masuk Receipt Inbox.
3. Receipt/Vision Parser mengekstrak data.
4. Finance Agent membuat draft transaksi.
5. Jika confidence tinggi dan policy mengizinkan, draft dapat auto-confirm.
6. Jika perlu review, Telegram menampilkan preview.

Preview minimum:
- merchant,
- tanggal,
- nominal,
- akun/metode pembayaran,
- usaha,
- kategori,
- confidence,
- indikasi duplikat bila ada.

### 4. Approval UI
Untuk tindakan yang butuh approval, Telegram menampilkan tombol seperti:
- Approve
- Reject
- Edit
- Detail

Contoh penggunaan:
- receipt dengan confidence sedang,
- transaksi mencurigakan,
- koreksi transaksi periode closed,
- tindakan sensitif dari agent,
- blacklist permanen,
- command sistem berisiko,
- aksi keuangan yang memindahkan uang.

Approval wajib memiliki approval_id unik dan masa berlaku.

### 5. Laporan
Telegram dapat mengirim laporan:
- harian,
- mingguan,
- bulanan,
- pemasukan/pengeluaran,
- arus kas,
- laba/rugi sederhana,
- piutang/utang,
- per usaha,
- saldo per akun,
- order/queue status,
- model/API usage dan cost.

Laporan panjang dapat diringkas di Telegram dengan tombol/link ke SaaS atau Google Sheets dashboard.

### 6. Alert
Telegram menerima alert penting seperti:
- file/link masuk quarantine,
- malware/phishing/high-risk indicator,
- spam/scam suspected,
- sinkronisasi Google Sheets gagal,
- provider/model gagal,
- agent crash/error berulang,
- transaksi duplikat/mencurigakan,
- approval menunggu terlalu lama,
- kill switch diaktifkan.

Alert harus diberi severity:
- INFO
- WARNING
- HIGH
- CRITICAL

### 7. Agent Control
Owner dapat:
- melihat status agent,
- pause agent,
- resume agent,
- disable sementara tool tertentu,
- meminta health check,
- melihat task aktif,
- menjalankan kill switch.

Kill switch tidak boleh dapat dijalankan oleh user Telegram di luar allowlist.

## Security

### Admin Allowlist
Minimal cek:
- Telegram user_id,
- chat_id/context,
- environment,
- status bot/session.

Username Telegram bukan identitas utama karena dapat berubah.

### Secret
Simpan di environment/secret store, contoh:
- TELEGRAM_BOT_TOKEN
- TELEGRAM_ADMIN_USER_ID
- TELEGRAM_ADMIN_CHAT_ID

Jangan log token atau secret.

### File & Link
Foto struk umum dapat masuk receipt pipeline setelah pemeriksaan aman.

File executable, script, macro, arsip mencurigakan, dan link asing tidak boleh auto-open/auto-run.

### Prompt Injection
Pesan, file, caption, atau link dari Telegram tetap dianggap input, bukan policy baru.
Isi eksternal tidak boleh dapat mengubah system rules atau meminta secret.

## Audit Log
Setiap command penting mencatat minimal:
- event_id,
- timestamp,
- Telegram user_id internal/reference,
- intent,
- target agent,
- action,
- risk level,
- approval status,
- result.

## Integrasi Agent
Telegram tidak memiliki business logic sendiri.

Contoh:
- transaksi/laporan -> Finance Agent
- order/cetak -> DocuTech Agent
- photobooth -> Photobooth Agent
- Windows -> Desktop Agent
- coding -> Coding Agent/OpenCode
- pencarian/riset -> Research Agent

Lead Agent menjadi pintu routing utama.

## Tahap Implementasi
V1 implementasi minimum:
1. Telegram Bot Adapter.
2. Allowlist satu owner.
3. Natural language message ke Lead Agent.
4. Finance quick entry.
5. Receipt image intake.
6. Approval buttons.
7. Report/alert dasar.
8. Audit logging.

## Status
Versi: v1.0-draft

Spesifikasi ini dibuat sebelum implementasi runtime agar kontrak Telegram, Lead Agent, Finance Agent, policy, dan approval tidak saling tumpang tindih.