# Rencana Nomor WhatsApp per Usaha (dicatat, belum diimplementasikan)

## Status
**Dicatat 19 September 2026 sebagai rencana/keputusan, BELUM ada kode yang dibuat untuk
ini.** Owner memilih "catat rencana dulu" (bukan langsung coding), karena status
pendaftaran nomor-nomor baru di WhatsApp Business Platform (Meta) belum dipastikan.
Dokumen ini murni supaya keputusannya tidak hilang, dan jadi acuan kalau nanti memang
dilanjutkan ke implementasi.

## Kondisi Sekarang
Hanya SATU nomor WhatsApp yang tersambung ke sistem: nomor Taqi Desk, dikelola
`whatsapp_main.py` + `app/whatsapp.py`, sudah lengkap sampai Fase 4 di
`docs/roadmap_customer_channel_v1.md` (Trust Layer, Approval Gate, kill switch, topic
restriction, price list/order status, attachment security, semua sudah jalan untuk
nomor ini). Nomor ini HANYA menangani Taqi Desk (Document Agent/Nara — pembuatan
makalah/KTI/skripsi), sesuai keputusan owner: **"Nara khusus pembuatan makalah saja"**.

## Keputusan (19 September 2026)
Owner punya total tiga jalur usaha yang sebelumnya sempat dipertimbangkan digabung jadi
satu nomor (lihat diskusi soal topic-restriction lintas-usaha), tapi diputuskan **tetap
dipisah per nomor** untuk sekarang:

| Usaha | Nomor WhatsApp | Otomatisasi | Catatan |
| --- | --- | --- | --- |
| Taqi Desk (makalah/print/fotocopy) | Nomor yang sudah tersambung sekarang | **Otomatis penuh** — satu-satunya yang otomatis untuk saat ini | Sudah jalan penuh (Fase 1-4), tidak berubah |
| Risol Mamqi | 081220283279 | **Manual** — dibalas langsung oleh istri owner, TIDAK disambungkan ke AI | Usaha terpisah dengan basis pelanggan sendiri |
| Photobooth (Pixiva.ID) + Install Windows/Servis Komputer | 081212490404 | **Manual** — dibalas langsung oleh owner, TIDAK disambungkan ke AI | Digabung SATU nomor karena keduanya dikerjakan owner sendiri |

**Catatan penting (ditegaskan owner):** untuk sekarang hanya Nara/Taqi Desk yang
otomatis. Nomor Risol Mamqi dan nomor Photobooth/Install Windows sengaja dibalas
manual dulu, bukan lewat AI Assistant. Ini menjawab pertanyaan yang sebelumnya masih
"belum diputuskan" di draf awal dokumen ini — sudah diputuskan owner: tetap manual.
Kalau nanti owner mau salah satu atau kedua nomor ini disambungkan ke AI juga (trust
layer, kill switch, dst, seperti Taqi Desk), itu permintaan baru yang perlu diminta
eksplisit — jangan diasumsikan otomatis menyusul hanya karena nomornya sudah dicatat
di sini.

Owner menyebut nomor-nomor ini masih bisa berubah ("nanti ini bisa diganti juga") — jangan
menganggapnya final/di-hardcode di kode kalau nanti diimplementasikan; sebaiknya tetap
lewat variabel `.env` seperti pola nomor Taqi Desk sekarang, bukan ditulis literal di
kode.

## Yang Masih Jadi Prasyarat Sebelum Bisa Dikerjakan
Prasyarat di bawah ini HANYA relevan kalau nanti owner memutuskan menyambungkan Risol
Mamqi dan/atau Photobooth/Install Windows ke AI juga (saat ini keduanya manual, jadi
belum perlu):
1. **Pendaftaran resmi WhatsApp Business Platform (Cloud API) di Meta Business Manager**
   untuk kedua nomor baru. Ini beda dari sekadar pakai WhatsApp/WhatsApp Business biasa di
   HP — perlu proses verifikasi bisnis di Meta dan menghasilkan `Phone Number ID` +
   access token tersendiri PER NOMOR (persis kebutuhan `WHATSAPP_PHONE_NUMBER_ID`/
   `WHATSAPP_API_TOKEN` yang sudah ada di `.env` untuk nomor Taqi Desk). Langkah ini
   dilakukan owner sendiri, tidak pernah lewat sesi ini (sesuai aturan credential di
   `policies/security_policy.md`).
2. Sampai prasyarat di atas jelas, belum ditentukan apakah menjalankan **proses
   `whatsapp_main.py` terpisah per nomor** (tiap proses baca `.env`/`DATABASE_PATH`
   sendiri, paling sederhana meniru pola yang sudah ada) atau **satu proses yang
   membedakan nomor lewat `phone_number_id` di payload webhook** lalu merutekan ke
   konteks usaha yang berbeda (lebih rumit, belum perlu dipilih sekarang).

## Yang Belum Ada Sama Sekali untuk Photobooth & Install Windows
Berbeda dari Taqi Desk yang sudah punya Document Agent (Nara) dengan alur
percakapan lengkap, Photobooth dan Install Windows belum punya agent/alur khusus.
Karena nomor 081212490404 untuk sekarang dibalas MANUAL oleh owner (bukan AI), ini
sebetulnya bukan blocker apa pun saat ini. Baru relevan kalau suatu saat owner
memutuskan menyambungkan nomor ini ke AI juga: secara default AI akan
mengklasifikasikan kebutuhan itu sebagai `minta_detail_order` (sudah ada di
`app/customer_intent.py`) — pelanggan diminta menceritakan kebutuhan, lalu diteruskan
ke Interaction Log untuk owner balas manual. Ini cukup wajar untuk booking yang
relatif sederhana, tapi BUKAN otomatisasi penuh seperti Nara. Kalau nanti owner mau
alur yang lebih pintar (harga otomatis dari `app/price_list.py`, booking terjadwal,
dst), itu jadi pekerjaan implementasi terpisah, menyusul setelah nomornya benar-benar
aktif DAN owner memutuskan mau otomatis.

## Risol Mamqi — sudah diputuskan: manual, bukan AI
Sejauh ini Risol Mamqi baru muncul sebagai kategori usaha di Finance Agent (Laras) —
lihat `BUSINESSES` di `app/finance.py` dan `brand_profiles/risol_mamqi.md` untuk Content
Studio (Kirana). Nomor WhatsApp Risol Mamqi (081220283279) TIDAK disambungkan ke sistem
AI (tidak ada trust layer/kill switch/dsb seperti Taqi Desk) — tetap dibalas manual oleh
istri owner. Ini sudah final untuk sekarang, bukan lagi pertanyaan terbuka.

## Referensi
- `docs/roadmap_customer_channel_v1.md` — Fase 1-4 yang sudah selesai untuk nomor Taqi
  Desk; jadi cetak biru kalau nomor lain nanti benar-benar disambungkan ke AI.
- `policies/security_policy.md` — aturan credential (nomor/token WhatsApp baru tetap
  tidak pernah diminta/dibaca lewat sesi ini).
- `app/finance.py` (`BUSINESSES`) — empat usaha yang sudah tercatat di sisi keuangan,
  terpisah dari keputusan channel WhatsApp di dokumen ini.

## Riwayat Perubahan
- 19 September 2026: dokumen dibuat, nomor Risol Mamqi dan Photobooth/Install Windows
  dicatat, status "belum diputuskan" untuk keduanya.
- 19 September 2026 (lanjutan, hari yang sama): owner menegaskan Risol Mamqi dan
  Photobooth/Install Windows dibalas MANUAL saja untuk sekarang (bukan AI); dan nama
  usaha "Taqi DocuTech" diganti jadi **"Taqi Desk"** di seluruh sistem (lihat
  `brand_profiles/taqi_desk.md`, `app/finance.py`). Nama lama tetap dikenali sebagai
  alias input di Finance Agent supaya kebiasaan lama tidak gagal tercatat.
