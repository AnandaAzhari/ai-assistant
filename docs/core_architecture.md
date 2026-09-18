# Core Architecture

## Tujuan
Membangun AI Assistant modular yang aman, mudah dikembangkan, tidak terikat satu model/provider, dan dapat digunakan untuk operasional usaha maupun personal assistant.

## Dua Jalur Utama

### A. Jalur Pelanggan
WhatsApp / channel pelanggan lain
→ Input Gateway
→ Security & Trust Layer
→ Lead Agent
→ Model Router
→ Agent Registry
→ Specialist Agent
→ Tool Gateway
→ Approval Gate bila diperlukan
→ Action / Response ke pelanggan
→ Audit Log + Memory + ML Feedback

### B. Jalur Owner / Admin
Telegram Admin / Web Admin / Desktop
→ Admin Authentication & Authorization
→ Lead Agent
→ Model Router
→ Agent Registry
→ Specialist Agent / Tool Gateway
→ Approval Gate bila diperlukan
→ Hasil / Laporan / Alert kembali ke owner
→ Audit Log + Memory + ML Feedback

Telegram diposisikan sebagai control plane utama milik owner untuk tahap awal, bukan sebagai channel pelanggan utama.

## Komponen Inti

### 1. Input Gateway
Menerima input dari channel seperti WhatsApp, Telegram Admin, Web UI, Desktop, dan channel lain di masa depan.

Input dibedakan berdasarkan asal:
- Customer channel: tidak tepercaya dan wajib melewati Security & Trust Layer.
- Owner/admin channel: wajib melewati authentication dan authorization.

### 2. Telegram Admin Control Plane
Telegram menjadi jalur cepat antara owner dan Lead Agent.

Fungsi utama:
- Mengirim perintah langsung ke Lead Agent.
- Menerima ringkasan order dan antrean.
- Menerima laporan harian/mingguan.
- Menerima security alert, spam/scam alert, dan file/link quarantine alert.
- Menerima approval request untuk tindakan sensitif.
- Menyetujui/menolak tindakan dengan command atau tombol.
- Melihat status agent, model, biaya API, dan kesehatan sistem.
- Menjalankan kill switch atau pause agent.
- Menerima notifikasi kegagalan tool/provider.

Telegram Admin tidak boleh memperlakukan semua akun Telegram sebagai admin. Hanya user/chat ID yang ada di allowlist yang boleh memberi perintah administratif.

Bot token, admin ID, dan secret lain hanya disimpan di environment/secret store dan tidak boleh masuk GitHub.

### 3. Security & Trust Layer
Bekerja sebelum Lead Agent memproses isi pesan pelanggan secara penuh.

Tugas utama:
- Trust/spam scoring.
- Deteksi pola scam/phishing.
- Pemeriksaan link dan attachment.
- Prompt-injection filtering.
- Pemisahan data pelanggan dan data internal.
- Rate limiting untuk pengirim mencurigakan.
- Quarantine untuk file/link berisiko.

Security layer tidak boleh menjalankan file, macro, script, executable, atau membuka link asing secara otomatis.

### 4. Lead Agent
Menerima input yang sudah melalui pemeriksaan yang sesuai dan menentukan intent serta agent yang paling tepat.

Lead Agent tidak harus mengerjakan semua tugas sendiri. Fokusnya adalah routing, koordinasi, monitoring, dan eskalasi.

Perintah dari Telegram Admin dapat memiliki prioritas lebih tinggi daripada tugas background, tetapi tetap tidak boleh melewati security policy dan approval policy.

### 5. Model Router
Memilih model AI berdasarkan jenis tugas, biaya, performa, privasi, dan ketersediaan provider.

Contoh strategi awal:
- DeepSeek V4.1 Flash: default murah/cepat.
- GPT/Gemini: fallback atau tugas tertentu.
- Model lokal: tugas ringan atau privacy-sensitive.

Model dapat diganti tanpa mengubah agent atau tools.

### 6. Agent Registry
Daftar semua agent aktif beserta kemampuan, izin, versi, tool yang boleh digunakan, dan batasannya.

Lead Agent membaca registry untuk memilih agent, bukan mengandalkan hard-code.

### 7. Specialist Agents
Contoh agent:
- Desktop Agent
- WhatsApp Agent
- DocuTech Agent
- Photobooth Agent
- Research Agent
- Trading Agent
- Coding Agent / OpenCode
- Reporting Agent
- Social Media Agent (lihat `agents/social_media_agent.md` dan `docs/social_media_v1.md`)

Setiap agent mengikuti AGENT_TEMPLATE dan prinsip least privilege.

### 8. Tool Gateway
Satu pintu untuk menjalankan aksi nyata seperti membuka aplikasi, membaca file, menulis dokumen, mengakses browser, memanggil API, atau menjalankan command.

Agent tidak boleh mendapatkan akses langsung ke sistem tanpa melalui Tool Gateway.

Tool Gateway wajib memeriksa:
- permission
- risk level
- environment (DEV/PRODUCTION)
- approval requirement
- target resource
- source identity/channel

### 9. Approval Gate
Tindakan rutin dan berisiko rendah dapat berjalan otomatis.

Tindakan sensitif harus meminta approval user sesuai approval_policy.md.

Untuk tahap awal, Telegram Admin menjadi channel utama approval karena owner dapat menerima permintaan dan merespons dari HP/tablet.

### 10. Memory & Database
SQLite digunakan untuk tahap awal.

Jenis data:
- conversation state
- customer/order state
- agent task history
- trust/spam decisions
- approval history
- model usage/cost
- feedback berhasil/gagal
- report state
- admin command history

Memory tidak boleh menyimpan secret/API key secara plain text.

### 11. Audit Log
Setiap aksi agent yang menghasilkan efek nyata harus memiliki audit trail.

Minimal catat:
- timestamp
- actor/agent
- source channel
- authenticated identity bila admin
- action
- tool
- target
- approval status
- result
- risk level

### 12. Reporting & Alerting
Sistem dapat mengirim laporan otomatis ke Telegram Admin.

Contoh laporan:
- order baru dan status antrean
- pekerjaan selesai
- pelanggan perlu perhatian admin
- file/link dikarantina
- spam/scam terdeteksi
- error agent/tool/provider
- penggunaan token/API dan estimasi biaya
- ringkasan harian/mingguan

Laporan sensitif sebaiknya berupa ringkasan. Data pelanggan lengkap atau file sensitif tidak dikirim ke Telegram kecuali diperlukan dan diizinkan policy.

### 13. ML Feedback Layer
Data interaksi dikumpulkan untuk melatih classifier/router internal secara bertahap.

Contoh data:
input → intent → agent terpilih → trust score → action → success/failure → koreksi user.

ML tidak diberi hak mengeksekusi aksi langsung. Keputusan akhirnya tetap melewati policy dan Tool Gateway.

## Prinsip Keamanan
- Zero trust untuk input pelanggan.
- Admin channel wajib authentication + allowlist.
- Least privilege untuk setiap agent.
- No auto-execution untuk attachment atau link asing.
- Secrets hanya melalui environment/secret store.
- DEV terpisah dari PRODUCTION.
- Semua aksi penting tercatat.
- Kill switch harus tersedia.
- Model AI tidak boleh dianggap sebagai sumber otorisasi.
- Telegram adalah control plane, bukan secret store.

## Arsitektur Awal yang Direkomendasikan

OpenClaw 2 dapat digunakan sebagai runtime/orchestrator utama.
Telegram Bot digunakan sebagai owner/admin control plane.
OpenCode digunakan sebagai coding specialist, bukan sebagai control plane utama.
DeepSeek V4.1 Flash dapat menjadi default model murah.
Python ML Worker digunakan untuk classifier/router khusus di masa depan.
SQLite digunakan untuk memory/log awal.
GitHub menjadi source of truth untuk code, policy, dan konfigurasi non-secret.

## Status
Versi: v1.1-draft

Dokumen ini akan diperbarui ketika agent dan tool pertama mulai diimplementasikan.
