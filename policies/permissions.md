# Permissions Policy

## Prinsip
Setiap agent hanya mendapat izin minimum yang dibutuhkan (least privilege). Tidak ada agent yang otomatis mendapat akses penuh ke komputer, data pelanggan, akun, atau channel komunikasi.

## Level Izin

### Level 0 — Read Only
Contoh: membaca status sistem, membaca knowledge base, membaca file yang sudah diizinkan.
Approval: tidak diperlukan.

### Level 1 — Low-Risk Action
Contoh: membuka aplikasi, membuka folder, mencari file, membuat draft lokal.
Approval: tidak diperlukan selama target ada dalam allowlist.

### Level 2 — Controlled Write
Contoh: membuat atau mengedit dokumen kerja, menyimpan output ke folder kerja agent, memulai/melanjutkan sesi pembuatan dokumen pelanggan (makalah/KTI/skripsi lewat Document Agent, action_type `buat_dokumen_pelanggan` — lihat `app/lead.py`).
Approval: tidak diperlukan untuk area kerja yang diizinkan; semua aksi harus dicatat.

### Level 3 — External Action
Contoh: mengirim pesan, mengunggah file, menjalankan command tertentu, mengubah status order.
Approval: dapat berjalan otomatis bila aksi termasuk workflow bisnis rutin dan sudah diizinkan oleh policy; aksi sensitif wajib approval.

### Level 4 — High Risk
Contoh: menghapus data permanen, menjalankan administrator command, instal software, transaksi keuangan, trading execution, perubahan security setting.
Approval: wajib dari admin.

## Batas Akses
- Agent hanya boleh mengakses folder, tool, account, dan channel yang ditetapkan.
- Agent tidak boleh membaca secret dari `.env` kecuali melalui service yang memang membutuhkannya.
- Agent tidak boleh membagikan secret, token, credential, atau data pelanggan ke agent lain tanpa kebutuhan yang sah.
- Aksi di luar capability agent harus dikembalikan ke Lead Agent untuk routing ulang.

## Audit
Semua aksi Level 2-4 harus dicatat dengan minimal: waktu, agent, user/session, tool, target, hasil, dan status approval bila ada.
