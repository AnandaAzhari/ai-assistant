# Roadmap: Customer Channel (WhatsApp) V1

## Tujuan
Urutan implementasi yang aman sebelum Lead Agent dibuka ke pelanggan asli lewat WhatsApp, mengikuti prinsip "Zero trust untuk input pelanggan" di `policies/security_policy.md`. Jalur Pelanggan sudah digambarkan di `docs/core_architecture.md`; dokumen ini memecahnya jadi fase implementasi konkret.

## Kenapa Urutan Ini
Security & Trust Layer dan Approval Gate saat ini baru berupa dokumen kebijakan (`policies/trust_spam_policy.md`, `policies/approval_policy.md`) — belum ada satu baris kode yang benar-benar menjalankannya. Menyambungkan WhatsApp sebelum dua lapisan ini ada di kode berarti pesan dari publik (termasuk spam/scam/percobaan prompt injection) langsung masuk ke Lead Agent tanpa penyaringan apa pun. Urutan di bawah memastikan pagar keamanan berdiri dulu sebelum pintunya dibuka ke publik.

## Temuan dari Riset Eksternal (2026)
Dicek ke sumber industri terkini soal praktik AI agent produksi, dibandingkan dengan desain yang sudah ada di repo ini.

### Yang sudah benar arahnya
- **Pola orkestrasi Lead Agent + Specialist Agents** ("orchestrator-worker") sudah sesuai rekomendasi industri untuk sistem berskala kecil-menengah — riset Princeton NLP menemukan satu agent tunggal justru menyamai/mengalahkan sistem multi-agent pada 64% tugas yang diuji, dan 40% pilot multi-agent gagal dalam 6 bulan pertama produksi karena kompleksitas berlebihan. Jangan tergoda menambah jumlah agent lebih dari yang benar-benar dibutuhkan.
- **Brand Profile per usaha dan skema transaksi Finance Agent yang terstruktur** sudah sejalan dengan temuan Gartner bahwa banyak proyek AI enterprise gagal karena data tidak "siap dipakai AI" (tidak terstruktur/tidak bersih). Ini justru pekerjaan rumah yang sudah kamu selesaikan lebih dulu.
- **Prinsip Approval Gate (manusia tetap mengambil keputusan akhir untuk aksi sensitif)** sejalan dengan temuan bahwa tim gabungan manusia+agent mengungguli agent yang sepenuhnya otonom pada 68,7% kasus. Jangan buru-buru menghilangkan approval manusia meski nanti sistemnya sudah terasa "pintar".

### Yang masih jadi celah nyata (belum ada di dokumen manapun sebelumnya)
1. ~~**Guardrails runtime belum konkret sebagai kategori.**~~ **Selesai (19 September
   2026):** catatan riset asli di bawah ini ditulis SEBELUM Fase 3/4 (lihat checklist di
   bawah) menutup sebagian besar gap ini untuk jalur pelanggan, dan sebelum
   `app/topic_guard.py` menyatukan keduanya jadi guardrail lintas-agent yang eksplisit —
   lihat `policies/security_policy.md` bagian "Hallucination Prevention & Topic
   Restriction (Lintas Agent)" untuk kebijakan lengkap yang sekarang berlaku, dan bagian
   "Guardrail Tambahan yang Perlu Masuk Fase 1" di bawah untuk status implementasi
   per-agent. Sisa yang masih terbuka: router admin (`handle_admin_message`) masih murni
   keyword tanpa AI (lihat Fase 3 di bawah), dan belum ada guardrail serupa untuk Laras
   (belum ada trafik AI produksi) atau Dimas (belum ada AI sama sekali).

   Catatan riset asli (untuk konteks historis): Security & Trust Layer di Fase 1 sudah menyasar sebagian (spam/scam, isolasi data), tapi riset industri membagi guardrails jadi 6 kategori: prompt injection detection, data/PII protection, **hallucination prevention**, topic restriction, policy enforcement, dan audit trail. Dua yang belum tersentuh sama sekali di dokumenmu: **hallucination prevention** (mencegah AI mengarang info di luar Document Agent — `document_agent.md` sudah larang "mengarang referensi" tapi itu baru untuk Nara, belum jadi aturan lintas semua agent) dan **topic restriction** (agent tetap dalam batas topik usahanya, tidak menjawab di luar konteks yang seharusnya).
2. **Belum ada Evaluasi & Observability untuk output AI-nya sendiri.** `tests/` yang ada sekarang menguji logika Python yang deterministik (parsing, kategori, dsb) — bagus, tapi begitu model AI beneran tersambung ke Lead Agent/Nara/Social Media Agent, kamu butuh cara terpisah untuk tahu **apakah jawaban AI-nya sendiri bagus atau tidak**, bukan cuma "apakah kodenya jalan tanpa error". Lihat Fase 5 di bawah.

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

### Guardrail Tambahan yang Perlu Masuk Fase 1

- [x] **Hallucination prevention (lintas agent, bukan cuma Nara).** Diimplementasikan
  (19 September 2026) via `app/topic_guard.py::is_verbatim_quote()` (kutipan-bukti,
  dipakai `app/customer_intent.py`/Taqi dan `app/document_intake.py`/Nara),
  `app/document_draft.py::_validate()` (sitasi Nara hanya boleh dari Source Registry
  terdaftar), `LeadAgent._augment_reply_with_real_data()` (harga/status pelanggan
  SELALU dari data asli atau jujur "belum bisa dipastikan", tidak pernah ditebak), dan
  `app/content_studio.py` (Kirana, guard harga karangan di draf caption). Detail
  kebijakan lengkap di `policies/security_policy.md`. Test:
  `tests/test_topic_guard.py`, `tests/test_customer_intent.py`,
  `tests/test_document_agent.py` (`DocumentAgentTopicRestrictionTests`),
  `tests/test_content_studio.py`.
- [x] **Topic restriction.** Diimplementasikan dua tempat dengan SATU daftar kata kunci
  bersama (`app/topic_guard.py::is_off_topic()`, tidak ada dua salinan yang bisa
  berbeda): (1) Taqi di kontak pertama pelanggan (`action_type` `di_luar_topik`,
  `app/lead.py`/`app/customer_intent.py`, selesai lebih dulu — lihat checklist Fase 4 di
  bawah), dan (2) **baru (19 September 2026)** Nara DI TENGAH sesi dokumen yang sudah
  berjalan (`app/document_agent.py`, backstop deterministik yang berjalan SEBELUM
  memanggil AI intake untuk pesan yang jelas di luar topik — menutup gap di
  `eval/scenarios/nara.md` Skenario 7 yang sebelumnya hanya mengandalkan persona AI
  tanpa validasi kode). Test: `tests/test_topic_guard.py`,
  `tests/test_customer_channel.py`, `tests/test_document_agent.py`
  (`DocumentAgentTopicRestrictionTests`).

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
- ~~Sambungkan model AI ke Lead Agent untuk memahami intent pesan bebas pelanggan.~~ **Selesai**: `app/customer_intent.py` (`CustomerIntentClassifier`) memakai provider AI (DeepSeek) untuk mengklasifikasikan action_type dari bahasa natural pelanggan, dengan validasi kutipan bukti (meniru pola `IntakeInterpreter`). AI hanya menentukan *action_type*; teks balasan tetap deterministik (`LeadAgent._CUSTOMER_REPLY_TEXT`) supaya guardrail hallucination-prevention tidak pernah dilewati. Fail-safe: kalau AI belum dikonfigurasi/gagal/hasilnya tidak valid, `LeadAgent._classify_customer_intent()` otomatis jatuh ke router kata kunci lama (`_detect_customer_action`). Router admin (`handle_admin_message`) masih murni keyword/regex — belum termasuk cakupan ini.

Kriteria selesai: pesan pelanggan simulasi bisa diproses end-to-end (trust check -> intent -> agent yang tepat -> approval bila perlu -> balasan), semuanya tercatat di audit log.

## Fase 4: WhatsApp Adapter
Tujuan: channel WhatsApp benar-benar tersambung, sesudah tiga fase di atas siap.

### Keputusan provider
**WhatsApp Business Platform Cloud API resmi dari Meta, langsung — bukan BSP pihak ketiga** (Qiscus/Wati/360dialog/dst). Alasannya (riset Sept 2026):
- Sejak Juli 2025 Meta memakai skema per-pesan (bukan lagi per-percakapan). Pesan balasan dalam jendela sesi 24 jam ("service"/non-template — yaitu hampir semua balasan reaktif ke pelanggan yang baru saja menghubungi kita) saat ini **gratis** di Cloud API resmi.
- Tidak ada biaya langganan bulanan tambahan dari BSP; sejalan dengan prinsip pay-as-you-go yang sudah dipakai untuk provider AI.
- BSP tetap layak dipertimbangkan nanti kalau volume pesan marketing/broadcast (kategori yang selalu berbayar, tanpa jendela gratis) membesar dan onboarding non-teknis jadi prioritas — bukan kebutuhan sekarang.

Deliverables (status):
- [x] Modul `app/whatsapp.py`: `WhatsAppHTTPClient` (kirim pesan lewat Cloud API), `verify_webhook_challenge`/`verify_webhook_signature` (handshake GET + verifikasi `X-Hub-Signature-256` — webhook tanpa tanda tangan valid selalu ditolak), `extract_inbound_messages` (parse payload Meta), `WhatsAppCustomerAdapter.process_webhook_event()` yang memanggil `LeadAgent.handle_customer_message()` untuk setiap pesan lalu mengirim balasannya. Semua pesan WhatsApp wajib lewat Fase 1-3 dulu — tidak ada jalur pintas ke agent lain.
- [x] Slot `.env` lengkap: `WHATSAPP_PROVIDER`, `WHATSAPP_API_TOKEN`, `WHATSAPP_PHONE_NUMBER_ID`, `WHATSAPP_WEBHOOK_VERIFY_TOKEN`, `WHATSAPP_APP_SECRET`.
- [x] Test: `tests/test_whatsapp.py` (verifikasi webhook, parsing payload, alur trust->intent->approval->balasan, pemotongan teks panjang).
- [x] Endpoint publik sungguhan: `whatsapp_main.py`, mengikuti pola `http.server` stdlib di `app/web_admin.py`. `GET /webhook` menangani handshake verifikasi Meta; `POST /webhook` memverifikasi `X-Hub-Signature-256` dari body mentah SEBELUM parsing JSON (payload tanpa tanda tangan valid ditolak 403 tanpa diproses sama sekali), lalu meneruskan ke `WhatsAppCustomerAdapter.process_webhook_event()`. Mode `--check` memeriksa kelengkapan `.env` tanpa menjalankan server. Nomor pemakai AI intent classifier (`app/customer_intent.py`) otomatis dipakai bila `DEEPSEEK_API_KEY` terisi; kalau belum, fallback kata kunci tetap aktif. Test: `tests/test_whatsapp_main.py`.
- [x] **WhatsApp tersambung ke Document Agent** — sebelumnya `handle_customer_message()` TIDAK PERNAH memanggil Document Agent sama sekali (pelanggan yang minta dibuatkan makalah hanya dibalas template generik "boleh diceritakan kebutuhannya?" berulang, tidak pernah benar-benar diproses). Sekarang: `LeadAgent.document_factory` (dirakit di `whatsapp_main.py`) membuat satu `DocumentAgent` tersendiri per nomor WhatsApp (`source_scope` = `DOCSRC-WHATSAPP-<nomor>`, lewat `_customer_document_agent`), sehingga sesi/brief satu pelanggan tidak pernah tercampur pelanggan lain. Action_type baru `buat_dokumen_pelanggan` (Level 2, terdaftar di `policies/permissions.md`) memulai sesi; pesan-pesan berikutnya otomatis diteruskan ke Document Agent tanpa diklasifikasikan ulang (`_continue_customer_document`), sama seperti pola admin. Pedoman penomoran/format yang dipakai SAMA PERSIS dengan admin — `skills/document_academic/` dan `policies/document_format_policy.md`, tidak ada pedoman baru yang perlu dibuat khusus WhatsApp. Begitu file Word final selesai, `WhatsAppHTTPClient.upload_media()`/`send_document()` mengunggah lalu mengirim file itu langsung ke pelanggan (lewat Media endpoint Cloud API — file dibaca dari disk lokal, TIDAK PERNAH perlu dihosting di URL publik), dan tercatat sebagai `unggah_file_ke_pelanggan` di Approval Gate untuk audit trail. Test: `tests/test_customer_channel.py` (sesi baru vs sesi aktif, prioritas guardrail harga vs niat dokumen, fallback saat `document_factory` belum aktif, log `unggah_file_ke_pelanggan` saat file final), `tests/test_whatsapp.py` (upload media + kirim dokumen ke pelanggan), `tests/test_approval_gate.py` (`buat_dokumen_pelanggan` = Level 2, auto-jalan), `tests/test_document_agent.py` (properti `final_docx_path`/`final_pdf_path`).
- [ ] **Belum**: keputusan hosting final (VPS mana yang akan dipakai) dan menjalankan `whatsapp_main.py` di sana dengan HTTPS publik. Bisa diuji dulu dari komputer sendiri + ngrok sebelum pindah ke VPS.
- [ ] **Belum**: verifikasi bisnis di Meta Business Manager, nomor WhatsApp bisnis, dan pengisian token asli ke `.env` — langkah ini dilakukan Ananda sendiri (tidak pernah lewat sesi ini, sesuai aturan credential).
- [x] **Kill switch** (`app/kill_switch.py`) — state on/off tersimpan di SQLite (tabel `kill_switch_state` + `kill_switch_log` append-only), per scope ("global" mematikan semua channel pelanggan sekaligus, atau scope bernama seperti "whatsapp" untuk satu channel saja). `LeadAgent.handle_customer_message()` mengecek `is_active(channel)` PALING AWAL — sebelum Trust Layer/Approval Gate/AI/Document Agent disentuh sama sekali — supaya menutup langkah pertama "Incident Response" di `policies/security_policy.md` ("aktifkan kill switch; hentikan channel/agent terdampak"). Admin mengatur lewat command yang sama seperti /status, /sync, dst. (jalan dari Telegram maupun Web Admin karena keduanya berbagi `app/admin_runtime.py`): `/matikan_otomatis [whatsapp] <alasan>`, `/nyalakan_otomatis [whatsapp]`, `/status_otomatis`. Karena `whatsapp_main.py` dan admin runtime memakai `DATABASE_PATH` yang sama, kill switch yang diaktifkan admin dari Telegram langsung berlaku di proses WhatsApp yang terpisah tanpa restart. Test: `tests/test_kill_switch.py`.
- [x] **Topic restriction** — action_type baru `di_luar_topik` (Level 3, auto-send rutin seperti `jawab_faq`) menutup gap di bagian "Guardrail Tambahan" di atas. Dikenali dua lapis, sama seperti pola AI-first + fallback yang sudah ada: `app/customer_intent.py` (AI-first, lewat bullet baru di `INTENT_PROMPT`) untuk nuansa bahasa bebas, dan `LeadAgent._OFF_TOPIC_WORDS` (fallback kata kunci pendek dan sengaja konservatif — curhat pribadi, topik sensitif) saat AI belum dikonfigurasi/gagal. Dicek SETELAH semua kata kunci bisnis (harga/status/FAQ/dokumen) supaya kebutuhan bisnis yang jelas tidak pernah salah tertahan. Balasannya pengalihan sopan yang tidak membahas isi topiknya sama sekali dan tetap membuka pintu untuk kebutuhan layanan. Test: `tests/test_customer_intent.py`, `tests/test_customer_channel.py`, `tests/test_approval_gate.py`.
- [x] **Price List & Order Status (hallucination prevention untuk harga/status, bukan cuma dokumen)** — sebelumnya `kirim_estimasi_harga_standar`/`kirim_status_antrean` SELALU dibalas teks generik "belum bisa dipastikan otomatis, diteruskan admin", walau adminnya sendiri sudah tahu harganya. `app/price_list.py` (data bisnis, sama untuk semua pelanggan, dicari lewat pencocokan substring dua-arah nama layanan vs pesan pelanggan, prioritas nama paling spesifik) dan `app/order_status.py` (data PER PELANGGAN, setiap query wajib difilter `sender_id` — isolasi antar pelanggan ditegakkan di kode, bukan cuma instruksi AI) keduanya SQLite, dikelola admin lewat command Telegram/Web Admin: `/harga_set <layanan> | <harga> | <catatan>`, `/harga_hapus`, `/harga_list`, `/status_set <nomor_wa> <order_id> | <status>`, `/status_lihat <nomor_wa>`. `LeadAgent._augment_reply_with_real_data()` mengganti balasan generik dengan data asli KALAU ketemu; kalau tidak ketemu, tetap balasan lama — tidak pernah menebak. Test: `tests/test_price_list.py`, `tests/test_order_status.py`.
- [x] **Attachment Security pipeline** — sebelumnya isi file yang dikirim pelanggan TIDAK PERNAH diunduh atau diperiksa; `has_attachment` hanya jadi sinyal boolean untuk Trust Layer, dan seluruh pipeline "Pemeriksaan Attachment" di `policies/attachment_link_security.md` 0% ditegakkan kode. Sekarang: `WhatsAppHTTPClient.download_media()` mengunduh isi file (dua langkah resmi Meta Media API: metadata -> URL CDN sementara -> isi file), lalu `app/attachment_guard.py` (`AttachmentGuard.inspect()`) memvalidasi ekstensi (termasuk ekstensi ganda yang menyamarkan tipe asli, mis. "malware.exe.pdf"), ukuran, dan menghasilkan risk level LOW/MEDIUM/HIGH/CRITICAL persis seperti definisi policy — arsitektur menyisakan slot `scanner` opsional (belum ada scanner sungguhan, sesuai "Scanner eksternal bersifat opsional dan tidak boleh menjadi satu-satunya lapisan pertahanan"). File SELALU disimpan ke folder quarantine (`ATTACHMENT_QUARANTINE_DIR`, default `data/quarantine`) dan tercatat di tabel `attachment_log` (sender, filename, hash, risk level, scan status, action) — tidak pernah ke folder kerja. `WhatsAppCustomerAdapter._handle_attachment_message()` menjalankan ini SEBELUM pesan disentuh Trust Layer/intent sama sekali; file HIGH/CRITICAL (atau gagal diunduh/diverifikasi) tidak diproses otomatis — pelanggan dapat balasan netral (tidak menuduh), dan admin dapat eskalasi otomatis lewat action_type baru `tinjau_attachment_pelanggan` (Level 4, selalu wajib approval). File aman (LOW/MEDIUM) tetap lanjut ke `handle_customer_message()` seperti biasa. Test: `tests/test_attachment_guard.py`, penambahan di `tests/test_whatsapp.py`.
- [ ] Rollout bertahap: mulai dari nomor uji terbatas (owner + beberapa orang terpercaya) dulu, baru nomor bisnis utama ke seluruh pelanggan setelah stabil — menyusul setelah hosting dan verifikasi bisnis siap.

## Fase 5: Evaluasi & Observability (paralel, mulai bareng Fase 1)
Tujuan: tahu apakah jawaban AI dari tiap agent benar-benar bagus, bukan cuma "kodenya jalan tanpa error". Ini beda dari `tests/` yang sudah ada (itu menguji logika Python deterministik).

Deliverables:
- Kumpulan skenario uji per agent (misalnya 15-20 contoh percakapan nyata/realistis untuk Nara, Finance Agent, Social Media Agent) yang jawabannya dicek manual dulu oleh kamu sebagai patokan "baik/tidak baik". **Diimplementasikan (draft awal, ~8 skenario per agent, menuju target 15-20):** `eval/scenarios/nara.md`, `eval/scenarios/finance_agent.md`, `eval/scenarios/social_media_agent.md` — lihat `eval/scenarios/README.md` untuk status dan cara pakai. Ini draft AI, bukan standar tervalidasi — perlu ditinjau/disesuaikan owner.
- Simpan setiap interaksi produksi (setelah live) sebagai data yang bisa ditinjau ulang — bukan cuma respons berhasil dikirim lalu dilupakan. Ini nyambung ke `docs/agent_memory_v1.md` (Long-Term Feedback Memory) yang sudah dirancang. **Diimplementasikan:** `app/interaction_log.py` (`InteractionLogStore`), tersambung ke jalur pelanggan (`LeadAgent.handle_customer_message`, agent "taqi"/"nara") dan Content Studio (`ContentStudio.generate_draft`, agent "kirana").
- Evaluasi percakapan penuh (multi-turn), bukan cuma satu pertanyaan-satu jawaban — agent yang bertanya klarifikasi, menjaga konteks, dan pulih dari kesalahan itu baru kelihatan bagus/tidaknya di percakapan penuh, bukan potongan tunggal. Skenario di `eval/scenarios/` sudah ditulis dalam bentuk multi-turn (percakapan lanjutan), bukan satu pertanyaan tunggal.
- Tinjauan berkala (mingguan/bulanan) atas sampel percakapan asli untuk menangkap penurunan kualitas lebih awal, terutama setelah ganti model atau update prompt. **Diimplementasikan:** perintah Telegram Admin `/eval_sample [agent] [n]` (ambil sampel belum ditinjau), `/eval_tandai <id> | baik/perlu_perbaikan/tidak_baik | <catatan>` (catat hasil tinjauan), `/eval_status [agent]` (ringkasan tren kualitas) — lihat `app/lead.py`.

Kriteria selesai: ada kumpulan skenario uji minimum untuk tiap agent yang sudah live dengan model AI sungguhan, dan proses (walau manual dulu) untuk meninjau sampel percakapan produksi secara berkala. **Infrastruktur dan draft awal sudah ada** (per catatan di atas); yang masih perlu dilakukan owner: (1) benar-benar menjalankan tinjauan berkala secara rutin begitu ada trafik produksi sungguhan, (2) menambah skenario menuju 15-20 per agent, terutama dari interaksi nyata yang ditandai `tidak_baik`/`perlu_perbaikan`. Finance Agent (Laras) belum memakai AI sungguhan di produksi (masih parsing deterministik), jadi belum ada trafik nyata untuk ditinjau lewat Interaction Log untuk agent ini — skenarionya tetap disiapkan untuk dipakai begitu bagian AI-nya (parsing teks/vision struk, lihat `docs/core_architecture.md`) diaktifkan.

## Ukuran Relatif Tiap Fase
Perkiraan kasar berdasarkan cakupan kerja, bukan estimasi waktu pasti (kecepatan tergantung waktu yang bisa dialokasikan):

| Fase | Ukuran | Ketergantungan |
| --- | --- | --- |
| 1. Security & Trust Layer (+ guardrails) | Sedang | Tidak ada, bisa mulai sekarang |
| 2. Approval Gate | Sedang | Tidak ada, bisa paralel dengan Fase 1 |
| 3. Input Gateway + Lead Agent Pelanggan | Sedang-Besar | Fase 1 dan 2 selesai |
| 4. WhatsApp Adapter | Kecil-Sedang (di luar riset provider) | Fase 1-3 selesai |
| 5. Evaluasi & Observability | Kecil di awal, berkelanjutan | Paralel dengan Fase 1, terus berjalan setelah live |

## Yang Tidak Perlu Menunggu Roadmap Ini
Finance Agent, Document Agent (Nara), Desktop Agent, Web Admin, dan Telegram Admin tetap aman dilanjutkan sekarang karena semuanya jalur owner-only, bukan publik.

## Status
- v0.3. Fase 1-4 sudah diimplementasikan (lihat checklist di masing-masing bagian fase di atas). Fase 5 (Evaluasi & Observability) infrastrukturnya sudah diimplementasikan (`app/interaction_log.py` + perintah Telegram `/eval_sample`, `/eval_tandai`, `/eval_status`) dan draft awal skenario uji sudah ada di `eval/scenarios/` — lihat detail status di bagian Fase 5 di atas. Guardrail hallucination prevention & topic restriction lintas-agent (`app/topic_guard.py`) diimplementasikan 19 September 2026 — lihat bagian "Guardrail Tambahan yang Perlu Masuk Fase 1" di atas dan `policies/security_policy.md`.
