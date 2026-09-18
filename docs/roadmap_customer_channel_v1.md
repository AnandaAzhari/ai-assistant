# Roadmap: Customer Channel (WhatsApp) V1

## Tujuan
Urutan implementasi yang aman sebelum Lead Agent dibuka ke pelanggan asli lewat WhatsApp, mengikuti prinsip "Zero trust untuk input pelanggan" di `policies/security_policy.md`. Jalur Pelanggan sudah digambarkan di `docs/core_architecture.md`; dokumen ini memecahnya jadi fase implementasi konkret.

## Kenapa Urutan Ini
Security & Trust Layer dan Approval Gate saat ini baru berupa dokumen kebijakan (`policies/trust_spam_policy.md`, `policies/approval_policy.md`) — belum ada satu baris kode yang benar-benar menjalankannya. Menyambungkan WhatsApp sebelum dua lapisan ini ada di kode berarti pesan dari publik (termasuk spam/scam/percobaan prompt injection) langsung masuk ke Lead Agent tanpa penyaringan apa pun. Urutan di bawah memastikan pagar keamanan berdiri dulu sebelum pintunya dibuka ke publik.

## Fase 1: Security & Trust Layer (minimum)
Tujuan: setiap pesan pelanggan mendapat skor/keputusan sebelum diproses lebih lanjut.

Deliverables:
- Modul baru (misal `app/trust_layer.py`) yang mengubah aturan di `policies/trust_spam_policy.md` dan bagian "Aturan Trust & Spam" di `agents/lead_agent.md` jadi fungsi scoring bertahap: real customer / perlu verifikasi / kemungkinan spam — bukan keputusan tolak/terima biner.
- Pemeriksaan dasar: rate limiting per pengirim, deteksi pola link mencurigakan (mengikuti `policies/attachment_link_security.md`), penyimpanan skor + alasan ke database (bukan cuma diputuskan lalu dibuang).
- Test: `tests/test_trust_layer.py` dengan skenario pesan wajar, pesan mencurigakan, dan spam berulang.

Kriteria selesai: pesan simulasi pelanggan bisa diberi skor + keputusan (proses/minta verifikasi/tolak halus) sebelum menyentuh Lead Agent, dan hasilnya tercatat di audit log.

### Isolasi Data Antar Pelanggan (bagian dari Fase 1, wajib sebelum publik)
Lihat aturan lengkap di `policies/security_policy.md` bagian "Isolasi Antar Pelanggan". Ringkasan yang harus ada di kode Fase 1:

- Query database dari jalur pelanggan selalu difilter berdasarkan identitas pelanggan pengirim (`scope_id`/`order_id`/nomor WA miliknya sendiri) — tidak pernah query bebas/lintas pelanggan dari channel publik. Ini lapis utama; tanpa ini, AI secara fisik bisa "melihat" data pelanggan lain dan berisiko bocor kalau dibujuk lewat prompt injection.
- Pertanyaan yang mengarah ke data pihak lain (langsung maupun menyamar sebagai basa-basi) ditolak sopan dan dicatat sebagai sinyal ke trust/spam scoring, bukan cuma ditolak lalu dilupakan.
- Pengecekan tambahan sebelum balasan dikirim: pastikan isi balasan tidak menyebut nama/nomor/detail order milik pihak lain, sebagai jaring pengaman kedua.
- Query lintas pelanggan (rekap/laporan semua order) hanya boleh dari channel admin terautentikasi (Telegram Admin/Web Admin owner), tidak pernah dari channel pelanggan.

Kriteria selesai (tambahan untuk Fase 1): skenario uji "pelanggan A tanya data pelanggan B" dan "pelanggan menyamar minta rekap semua order" keduanya ditolak dan tercatat sebagai sinyal mencurigakan, bukan diproses.

## Fase 2: Approval Gate (minimum)
Tujuan: tindakan sensitif berhenti otomatis menunggu persetujuan owner, bukan cuma tertulis di kebijakan.

Deliverables:
- Modul baru (misal `app/approval_gate.py`) yang mengecek level akses di `policies/permissions.md` (Level 0-4) untuk tiap permintaan aksi, dan menerapkan aturan auto-send vs wajib-approval dari `policies/approval_policy.md`.
- State machine sederhana: `pending_approval` -> `approved`/`rejected`, dikirim ke Telegram Admin sebagai permintaan approval yang bisa dibalas lewat command/tombol.
- Test: `tests/test_approval_gate.py`.

Kriteria selesai: aksi Level 3-4 otomatis tertahan dan meminta approval owner lewat Telegram sebelum dieksekusi; aksi Level 0-2 tetap berjalan otomatis.

## Fase 3: Input Gateway Pelanggan + Lead Agent Versi Pelanggan
Tujuan: Lead Agent punya jalur khusus pesan pelanggan yang wajib melalui Fase 1 dan 2 lebih dulu.

Deliverables:
- Tambah method baru di `app/lead.py`, misal `handle_customer_message()`, terpisah dari `handle_admin_message()` yang sudah ada — wajib memanggil Trust Layer dan Approval Gate sebelum memproses isi pesan.
- Kembangkan `app/interaction_policy.py` dari sekadar helper istilah menjadi gateway sungguhan yang memutuskan asal channel dan rute pesan.
- Sambungkan model AI (lihat pemetaan di `docs/core_architecture.md` bagian Model Router) ke Lead Agent untuk memahami intent pesan bebas pelanggan — saat ini router admin masih murni keyword/regex.

Kriteria selesai: pesan pelanggan simulasi bisa diproses end-to-end (trust check -> intent -> agent yang tepat -> approval bila perlu -> balasan), semuanya tercatat di audit log.

## Fase 4: WhatsApp Adapter
Tujuan: channel WhatsApp benar-benar tersambung, sesudah tiga fase di atas siap.

Deliverables:
- Pilih provider WhatsApp Business API (API resmi Meta Cloud API, atau provider pihak ketiga) — perlu riset terpisah soal syarat verifikasi bisnis dan biaya, di luar cakupan dokumen ini.
- Modul baru `app/whatsapp.py` mengikuti pola `app/telegram.py` yang sudah berjalan (terima pesan masuk, kirim balasan), token diisi di `.env` lokal (`WHATSAPP_PROVIDER`, `WHATSAPP_API_TOKEN` sudah punya slotnya).
- Semua pesan WhatsApp wajib masuk lewat Fase 1-3 dulu, tidak pernah langsung ke agent.
- Rollout bertahap: mulai dari nomor uji terbatas (owner + beberapa orang terpercaya) dulu, baru nomor bisnis utama ke seluruh pelanggan setelah stabil.

## Ukuran Relatif Tiap Fase
Perkiraan kasar berdasarkan cakupan kerja, bukan estimasi waktu pasti (kecepatan tergantung waktu yang bisa dialokasikan):

| Fase | Ukuran | Ketergantungan |
| --- | --- | --- |
| 1. Security & Trust Layer | Sedang | Tidak ada, bisa mulai sekarang |
| 2. Approval Gate | Sedang | Tidak ada, bisa paralel dengan Fase 1 |
| 3. Input Gateway + Lead Agent Pelanggan | Sedang-Besar | Fase 1 dan 2 selesai |
| 4. WhatsApp Adapter | Kecil-Sedang (di luar riset provider) | Fase 1-3 selesai |

## Yang Tidak Perlu Menunggu Roadmap Ini
Finance Agent, Document Agent (Nara), Desktop Agent, Web Admin, dan Telegram Admin tetap aman dilanjutkan sekarang karena semuanya jalur owner-only, bukan publik.

## Status
- v0.1-draft
