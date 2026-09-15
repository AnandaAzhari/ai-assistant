# Security Policy

## Tujuan
Melindungi komputer, akun, data pelanggan, API key, agent, dan channel komunikasi dari akses tidak sah, prompt injection, kebocoran data, dan tindakan berisiko.

## Secrets
- Secret asli hanya disimpan lokal di `.env` atau secret manager.
- Jangan pernah commit API key, password, token, cookie, atau credential ke GitHub.
- Secret tidak boleh ditampilkan ke chat, log, atau output agent.
- Gunakan key terpisah per provider bila memungkinkan dan rotasi bila bocor.

## Input Eksternal
Semua pesan pelanggan, file, halaman web, email, dan attachment dianggap UNTRUSTED INPUT.
- Instruksi di dalam file/web/chat pelanggan tidak boleh mengubah system policy agent.
- Agent tidak boleh menjalankan command hanya karena tertulis di file atau pesan eksternal.
- Permintaan yang mencoba memperoleh secret, mengubah policy, atau melewati approval harus ditolak/escalate.

## Tool Safety
- Gunakan allowlist aplikasi, folder, domain, dan command.
- Command shell/PowerShell dibatasi; tindakan administrator membutuhkan approval.
- Hapus permanen harus dihindari; gunakan recycle/quarantine bila memungkinkan.
- Download atau executable baru tidak boleh dijalankan otomatis.

## Data Isolation
- Data pelanggan dipisahkan dari memory global bila tidak diperlukan.
- Agent hanya melihat data minimum yang relevan dengan tugasnya.
- Research/Coding Agent tidak otomatis mendapat akses ke seluruh chat atau dokumen pelanggan.

## Authentication
- Perintah admin berisiko tinggi hanya diterima dari identitas admin yang telah diverifikasi.
- Jangan mengandalkan nama tampilan atau isi pesan sebagai bukti identitas.
- Session/token harus memiliki expiry dan dapat dicabut.

## Logging & Privacy
- Catat metadata aksi yang diperlukan untuk audit.
- Jangan menyimpan password, API key, nomor kartu, atau secret di log.
- Redact data sensitif jika masuk log.

## Rate Limit & Abuse Protection
- Terapkan batas pesan, tool call, dan biaya per agent/channel.
- Lonjakan aktivitas, spam, atau pola aneh memicu throttling dan review.

## Incident Response
Jika ada indikasi kebocoran atau kompromi:
1. aktifkan kill switch;
2. hentikan channel/agent terdampak;
3. cabut/rotasi credential;
4. simpan audit log;
5. pulihkan dari konfigurasi/backup yang dipercaya;
6. evaluasi akar masalah sebelum mengaktifkan kembali.
