# Telegram Admin v1

## Implementasi yang tersedia — 18 September 2026

Bagian setelah panduan ini adalah rancangan target. Tidak semua fitur rancangan sudah tersedia.
Runtime saat ini menghubungkan chat pribadi owner ke layanan yang sama dengan Web Admin:

- Nara: pemahaman AI melalui provider DeepSeek dan file persona/skill yang sama, alur outline, persetujuan fokus, riset dan draft sesuai kemampuan Document Agent.
- Pencatatan keuangan dan perintah laporan yang tersedia di `/bantuan`. Router dan parser keuangan masih memakai implementasi yang ada; integrasi ini tidak mengubahnya menjadi AI penuh.
- Sesi dokumen disimpan di SQLite dan dipulihkan setelah program dinyalakan ulang. Sesi Telegram dibedakan berdasarkan bot, owner dan chat, serta terpisah dari sesi Web Admin. Buku keuangan tetap sama bila `DATABASE_PATH` sama.
- Balasan panjang dipecah tanpa dipotong. Balasan yang gagal dikirim dicoba kembali tanpa mengulangi tindakan yang sudah tercatat pada update yang sama.
- Hanya pesan dari owner dan chat pribadi yang dikonfigurasi yang diproses. Foto, suara dan lampiran diberi penjelasan bahwa pemrosesannya belum tersedia.
- **Menu perintah "/" bawaan Telegram (BARU, 19 September 2026):** setiap kali runtime dijalankan, daftar perintah didaftarkan otomatis ke Telegram lewat `setMyCommands` (`app/lead.py::TELEGRAM_COMMAND_MENU`, dipanggil dari `telegram_main.py`), termasuk `/help`. Ketuk "/" di kolom chat untuk melihat semua perintah beserta keterangan singkatnya, tanpa perlu hafal atau ketik `/bantuan` dulu. Ini murni kosmetik (autocomplete Telegram) — semua perintah tetap berfungsi normal walau pendaftaran ini gagal (mis. tidak ada internet saat startup); runtime tetap jalan, hanya menu "/"-nya yang belum terisi sampai runtime berikutnya dinyalakan.

Pengiriman file Word/PDF sebagai lampiran, pembacaan struk, tombol approval, laporan terjadwal dan alert otomatis **belum diimplementasikan** oleh adapter ini. Balasan hasil dokumen masih berupa teks/path lokal. Riset/draft tetap membutuhkan konfigurasi provider dan sumber yang memadai; koneksi Telegram saja tidak menjamin keduanya berhasil.

### Menggunakan bot yang sudah ada di Windows

1. Tutup runtime Telegram lama, lalu ambil kode terbaru dengan `git pull --ff-only` di folder project.
2. Pertahankan `.env` yang sudah ada, termasuk pengaturan DeepSeek. Pastikan `TELEGRAM_BOT_TOKEN` dan `TELEGRAM_ADMIN_USER_ID` terisi. `TELEGRAM_ADMIN_CHAT_ID` boleh kosong untuk chat pribadi; runtime memakai user ID. Simpan token hanya di komputer, jangan kirim melalui chat atau commit.
3. Jalankan `CEK_TELEGRAM.bat`. Pemeriksaan hanya memeriksa koneksi bot, webhook dan kelengkapan konfigurasi; tidak mengirim chat, menjalankan transaksi, atau menguji koneksi AI. Kecocokan akun owner diuji melalui `/status` setelah runtime aktif.
4. Jika ID admin belum diketahui, jalankan `TEMUKAN_TELEGRAM_ID.bat`. Kirim kode `/hubungkan ...` yang tampil ke chat pribadi bot dari akun sendiri, lalu salin kedua ID hasilnya ke `.env`. Tidak perlu membuat bot baru.
5. Jalankan `JALANKAN_TELEGRAM.bat`, buka chat bot, tekan Start bila diperlukan, lalu kirim `/status` dan `/bantuan`.
6. Untuk mencoba Nara, kirim `/makalah_baru`, lalu kebutuhan makalah seperti di Web Admin. Gunakan `/dokumen_status` untuk memeriksa sesi. Outline tetap memerlukan persetujuan sebelum dilanjutkan.

Komputer perlu menyala, internet tersedia, dan terminal runtime tetap terbuka. Tutup dengan Ctrl+C. Jangan menjalankan dua runtime untuk bot yang sama, termasuk dari komputer lain. Pengunci lokal mencegah dua runtime/penemuan ID dari folder project yang sama; bentrok polling di tempat lain dilaporkan saat Telegram menolaknya.

Jika bot masih menggunakan webhook, program menjelaskan bentroknya dan tidak menghapus webhook otomatis. Hanya bila memang ingin memindahkan bot tersebut ke polling komputer ini, jalankan `python telegram_main.py --remove-webhook --check`; opsi ini mempertahankan pesan tertunda.

### Pemulihan dan batas pengujian

Jurnal update menyimpan penanda tindakan sebelum menjalankan layanan. Setelah crash di tengah tindakan, hasil bisa belum pasti: bot meminta owner mengecek `/hari_ini` atau `/dokumen_status`, bukan menjalankan tindakan itu lagi secara otomatis. Timeout saat pengiriman dapat menghasilkan balasan duplikat; tidak ada klaim pengiriman tepat satu kali. Pesan baru yang diketik ulang oleh pengguna memiliki update ID baru dan dapat menjalankan tindakan baru.

Pengujian simulasi: `python -m unittest discover -s tests -p "test_telegram*.py"`. Mencakup pembatasan akun/chat, pemulihan offset, pesan berulang, kegagalan kirim, pemecahan teks/emoji, kerahasiaan error, integrasi ledger, persistensi sesi dan pemanggilan Nara. Hasil saat perubahan dibuat: 33 tes Telegram lulus. Suite keseluruhan menjalankan 209 tes dengan 4 kegagalan lama pada ekspektasi status Document Agent dan parsing judul "belum"; suite keseluruhan belum hijau. Koneksi bot nyata dan runtime Windows tetap perlu diuji di komputer owner.

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
- "Catat pengeluaran 80 ribu beli tinta untuk Taqi Desk pakai BCA."
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
