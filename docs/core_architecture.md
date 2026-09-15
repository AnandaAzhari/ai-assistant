# Core Architecture

## Tujuan
Membangun AI Assistant modular yang aman, mudah dikembangkan, tidak terikat satu model/provider, dan dapat digunakan untuk operasional usaha maupun personal assistant.

## Alur Utama

User / Customer Channel
→ Input Gateway
→ Security & Trust Layer
→ Lead Agent
→ Model Router
→ Agent Registry
→ Specialist Agent
→ Tool Gateway
→ Approval Gate
→ Action / Response
→ Audit Log + Memory + ML Feedback

## Komponen Inti

### 1. Input Gateway
Menerima input dari channel seperti Web UI, WhatsApp, Telegram, Desktop, dan channel lain di masa depan.

Semua input eksternal dianggap tidak tepercaya sampai melewati pemeriksaan keamanan.

### 2. Security & Trust Layer
Bekerja sebelum Lead Agent memproses isi pesan secara penuh.

Tugas utama:
- Trust/spam scoring.
- Deteksi pola scam/phishing.
- Pemeriksaan link dan attachment.
- Prompt-injection filtering.
- Pemisahan data pelanggan dan data internal.
- Rate limiting untuk pengirim mencurigakan.
- Quarantine untuk file/link berisiko.

Security layer tidak boleh menjalankan file, macro, script, executable, atau membuka link asing secara otomatis.

### 3. Lead Agent
Menerima input yang sudah melalui pemeriksaan awal dan menentukan intent serta agent yang paling tepat.

Lead Agent tidak harus mengerjakan semua tugas sendiri. Fokusnya adalah routing, koordinasi, monitoring, dan eskalasi.

### 4. Model Router
Memilih model AI berdasarkan jenis tugas, biaya, performa, dan ketersediaan provider.

Contoh strategi awal:
- DeepSeek V4.1 Flash: default murah/cepat.
- GPT/Gemini: fallback atau tugas tertentu.
- Model lokal: tugas ringan atau privacy-sensitive.

Model dapat diganti tanpa mengubah agent atau tools.

### 5. Agent Registry
Daftar semua agent aktif beserta kemampuan, izin, versi, tool yang boleh digunakan, dan batasannya.

Lead Agent membaca registry untuk memilih agent, bukan mengandalkan hard-code.

### 6. Specialist Agents
Contoh agent:
- Desktop Agent
- WhatsApp Agent
- DocuTech Agent
- Photobooth Agent
- Research Agent
- Trading Agent
- Coding Agent / OpenCode

Setiap agent mengikuti AGENT_TEMPLATE dan prinsip least privilege.

### 7. Tool Gateway
Satu pintu untuk menjalankan aksi nyata seperti membuka aplikasi, membaca file, menulis dokumen, mengakses browser, memanggil API, atau menjalankan command.

Agent tidak boleh mendapatkan akses langsung ke sistem tanpa melalui Tool Gateway.

Tool Gateway wajib memeriksa:
- permission
- risk level
- environment (DEV/PRODUCTION)
- approval requirement
- target resource

### 8. Approval Gate
Tindakan rutin dan berisiko rendah dapat berjalan otomatis.

Tindakan sensitif harus meminta approval user sesuai approval_policy.md.

### 9. Memory & Database
SQLite digunakan untuk tahap awal.

Jenis data:
- conversation state
- customer/order state
- agent task history
- trust/spam decisions
- approval history
- model usage/cost
- feedback berhasil/gagal

Memory tidak boleh menyimpan secret/API key secara plain text.

### 10. Audit Log
Setiap aksi agent yang menghasilkan efek nyata harus memiliki audit trail.

Minimal catat:
- timestamp
- actor/agent
- source channel
- action
- tool
- target
- approval status
- result
- risk level

### 11. ML Feedback Layer
Data interaksi dikumpulkan untuk melatih classifier/router internal secara bertahap.

Contoh data:
input → intent → agent terpilih → trust score → action → success/failure → koreksi user.

ML tidak diberi hak mengeksekusi aksi langsung. Keputusan akhirnya tetap melewati policy dan Tool Gateway.

## Prinsip Keamanan
- Zero trust untuk input pelanggan.
- Least privilege untuk setiap agent.
- No auto-execution untuk attachment atau link asing.
- Secrets hanya melalui environment/secret store.
- DEV terpisah dari PRODUCTION.
- Semua aksi penting tercatat.
- Kill switch harus tersedia.
- Model AI tidak boleh dianggap sebagai sumber otorisasi.

## Arsitektur Awal yang Direkomendasikan

OpenClaw 2 dapat digunakan sebagai runtime/orchestrator utama.
OpenCode digunakan sebagai coding specialist, bukan sebagai control plane utama.
DeepSeek V4.1 Flash dapat menjadi default model murah.
Python ML Worker digunakan untuk classifier/router khusus di masa depan.
SQLite digunakan untuk memory/log awal.
GitHub menjadi source of truth untuk code, policy, dan konfigurasi non-secret.

## Status
Versi: v1.0-draft

Dokumen ini akan diperbarui ketika agent dan tool pertama mulai diimplementasikan.
