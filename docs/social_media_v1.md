# Social Media Content V1

## Working Name
Taqi ContentDesk (working title; dapat diganti nanti, mengikuti pola Taqi FinanceDesk).

## Tujuan
Membuat sistem konten media sosial yang terhubung ke Social Media Agent, Telegram Admin, Web Admin, dan beberapa usaha sekaligus, sehingga owner cukup memberi brief singkat dan sistem membantu dari ide sampai laporan performa.

## Usaha Tercakup V1
- Taqi DocuTech
- Pixiva.ID
- Risol Mamqi

Computer Service dan akun personal tidak masuk cakupan V1 kecuali owner memintanya. Struktur data dibuat agar usaha baru mudah ditambahkan tanpa mengubah arsitektur inti, mengikuti pola multi-business pada Finance SaaS.

## Sasaran V1
- Owner bisa minta ide konten lewat Telegram/Web Admin dan menerima beberapa draft dalam hitungan menit.
- Draft mencakup caption/naskah dan, bila diperlukan, visual pendukung.
- Owner bisa approve, edit, atau tolak draft sebelum tayang.
- Konten terjadwal otomatis ke platform yang sudah terhubung, tanpa owner mengetik ulang di tiap aplikasi.
- Owner menerima laporan performa konten dan rekap kalender mingguan/bulanan.
- Konten dan brand voice terpisah rapi per usaha.

## Platform V1
Prioritas awal:
- Instagram (feed, story, reels).
- TikTok (video pendek).
- WhatsApp Status/Broadcast (promosi ke kontak/pelanggan langsung).

Platform lain (Facebook, Threads, YouTube Shorts, dan seterusnya) ditambahkan lewat Platform Adapter baru tanpa mengubah Content Engine inti, mengikuti pola Google Sheets Sync Adapter dan Provider abstraction yang sudah dipakai untuk model AI.

## Modul Utama

### 1. Content Calendar
Tampilkan:
- jadwal konten per usaha dan per platform,
- status tiap slot: idea, draft, needs_review, approved, scheduled, published, failed, retracted,
- filter per usaha, platform, tanggal, dan status.

### 2. Content Studio (Ide & Naskah)
- Owner mengirim brief singkat (tema, tujuan, platform, usaha).
- Social Media Agent membuat beberapa alternatif caption/naskah/hook sesuai brand profile usaha.
- Owner memilih, mengedit, atau meminta versi lain.

### 3. Visual Studio
- Pembuatan gambar/poster/thumbnail dari brief atau template brand melalui Image Generation Provider.
- Opsi memakai foto/video yang diunggah owner sebagai bahan dasar, bukan hanya generate dari nol.
- Semua visual melewati Attachment Security Policy sebelum dipakai bila berasal dari file upload eksternal.

### 4. Scheduling & Publishing
- Penjadwalan per platform dengan waktu tayang yang dapat diatur owner atau disarankan sistem berdasarkan histori performa.
- Publishing melalui Platform Publishing Adapter resmi masing-masing platform.
- Retry otomatis untuk kegagalan publish sementara (rate limit, gangguan API), dengan alert ke Telegram bila gagal permanen.

### 5. Analytics & Reporting
- Metrik dasar: reach, impression, like, comment, share, save, view, click (sesuai yang disediakan tiap platform).
- Rekap performa per konten, per usaha, per platform, dan tren mingguan/bulanan.
- Insight sederhana: jenis konten/topik yang secara historis performanya lebih baik per usaha.

### 6. Brand Profile Manager
- Penyimpanan brand profile per usaha: tone of voice, palet warna/identitas visual, target audiens, larangan tema/kata, contoh caption favorit.
- Wajib diisi sebelum Social Media Agent membuat konten auto-publish untuk usaha tersebut.

### 7. Telegram Admin
Telegram berfungsi sebagai quick-brief dan control plane, konsisten dengan pola Finance Agent.
Contoh:
- "/konten_baru Risol Mamqi Instagram promo weekend"
- "/jadwal_konten" - lihat kalender minggu ini
- "/approve_konten <id>" / "/tolak_konten <id>"
- "/performa_konten <usaha>"
- menerima alert kegagalan publish atau sinkronisasi.

## Content AI Flow
Brief owner (Telegram/Web Admin)
→ Content Studio (draft caption/naskah)
→ Visual Studio (draft visual bila diperlukan)
→ Preview ke owner
→ Approval Gate sesuai Approval Policy
→ Content Calendar (scheduled)
→ Platform Publishing Adapter
→ Publish
→ Insight Collector
→ Analytics & Reporting
→ Laporan Telegram

## Data Model Minimum

### ContentItem
- content_id
- business_id
- platform
- type: feed/story/reel/short_video/broadcast/status
- caption/script
- status
- scheduled_at
- published_at
- media_refs
- source: manual/ai_draft/ai_auto
- created_by
- created_at
- updated_at

### MediaAsset
- asset_id
- content_id
- type: image/video
- file_reference
- source: uploaded/ai_generated
- security_check_status
- created_at

### PublishEvent
- event_id
- content_id
- platform
- platform_post_id
- status: pending/success/failed/retracted
- error_reason optional
- attempted_at
- confirmed_at

### PerformanceMetric
- metric_id
- content_id
- platform
- reach
- impressions
- likes
- comments
- shares
- saves
- views
- clicks
- collected_at

### BrandProfile
- business_id
- tone_of_voice
- visual_identity_reference
- target_audience
- forbidden_topics
- example_captions
- updated_at

## Hak Akses
V1 minimal:
- OWNER: akses penuh + approval publikasi.
- AGENT: akses sesuai permission (draft, jadwal, baca metrik; publish hanya sesuai Approval Policy).
- VIEWER/STAFF: opsional tahap berikutnya, misalnya admin konten yang hanya boleh membuat draft.

## Keamanan
- Token/API key tiap platform hanya di environment/secret store, tidak pernah di database konten, log, atau Google Sheets.
- Publikasi ke channel publik mengikuti Approval Policy dan Permissions Policy (Level 3 - External Action).
- Media dari owner tetap melalui Attachment & Link Security Policy sebelum diproses, terutama bila diunggah dari channel yang menerima file eksternal.
- Least privilege: Social Media Agent hanya mendapat akses ke akun/platform yang sudah dikonfigurasi, tidak ke seluruh akun sosial media owner.
- Audit trail untuk setiap draft, approval, publish, retract, dan kegagalan.
- DEV terpisah dari PRODUCTION agar percobaan konten tidak sengaja tayang ke akun asli.

## Tech Direction
Rekomendasi awal, konsisten dengan arah Finance SaaS:
- Frontend: perluasan Web Admin/PWA yang sudah ada, bukan aplikasi terpisah.
- Core/Content Engine: mengikuti bahasa/runtime yang sama dengan Lead Agent saat ini (Python), agar mudah disambung ke router yang sama.
- Database konten: SQLite untuk prototype awal, sejalan dengan Finance Service.
- Image/Video generation: melalui Provider abstraction seperti `app/providers/`, agar model/vendor dapat diganti tanpa mengubah Content Engine.
- Platform Publishing/Insights: Platform Adapter per platform (Instagram, TikTok, WhatsApp Business API), mengikuti pola `GoogleSheetsSync` sebagai Sync Adapter.
- Reporting mirror: opsional sinkron ke Google Sheets untuk rekap konten, mengikuti aturan di `docs/google_sheets_sync.md` (database tetap source of truth).

## Batas V1
Belum perlu:
- auto-publish tanpa approval untuk semua jenis konten,
- iklan berbayar/ads management,
- multi-akun per platform untuk satu usaha,
- integrasi influencer/creator eksternal,
- multi-tenant untuk usaha di luar milik owner.

V1 fokus menjadi asisten konten internal owner yang stabil untuk tiga usaha awal terlebih dahulu.

## Roadmap Setelah V1
1. Rekomendasi jadwal tayang otomatis berdasarkan histori performa.
2. A/B testing caption/visual sederhana.
3. Auto-repurpose satu konten ke beberapa platform sekaligus.
4. Perluasan platform (Facebook, Threads, YouTube Shorts).
5. Integrasi ads/promosi berbayar dengan approval ketat.
6. Multi-staff role untuk tim konten.
7. Multi-tenant bila ingin ditawarkan ke usaha lain.

## Versi
- v0.2-draft. Modul 2 (Content Studio "Ide & Naskah") sudah diimplementasikan sebagai `app/content_studio.py`, dipanggil lewat `/konten_baru` di Telegram Admin — lihat `agents/social_media_agent.md` untuk detail status implementasi per modul.
