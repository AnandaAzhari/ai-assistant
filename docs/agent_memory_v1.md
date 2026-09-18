# Agent Memory V1

## Tujuan
Menjelaskan bagaimana agent (Lead Agent, Nara/Document Agent, Finance Agent, Social Media Agent) menyimpan konteks supaya percakapan bisa **sambung-menyambung** antar sesi/restart, dan supaya sistem **makin pintar** dari waktu ke waktu tanpa melatih ulang model AI-nya. Dokumen ini merapikan pola yang sudah berjalan di kode (`DocumentSessionStore`, `DraftStore`, `finance_corrections`) menjadi satu prinsip yang konsisten, dipakai juga oleh Social Media Agent.

Lihat juga `docs/core_architecture.md` bagian 10 (Memory & Database) untuk gambaran besar; dokumen ini turunannya yang lebih teknis.

## Tiga Lapis Memory

### 1. Working Memory (per sesi/alur kerja aktif)
Konteks satu alur kerja yang sedang berjalan, misalnya satu sesi penyusunan makalah, satu draft konten yang belum final, atau satu percakapan Telegram yang belum selesai.

Pola yang sudah dipakai: `DocumentSessionStore` (`app/document_session.py`) — SQLite, key `scope_id`, isi berupa JSON `payload` dengan field `version`, disimpan lewat `load()`/`save()`. `DraftStore` (`app/document_draft_store.py`) memakai pola serupa berbasis file JSON per scope untuk isi makalah.

Prinsip:
- Kunci penyimpanan (`scope_id`) harus bisa dibentuk ulang dari identitas alur kerja (contoh: `usaha:platform:content_id`, atau `order_id` untuk dokumen), bukan dari riwayat chat mentah.
- Payload berisi **state terstruktur** (field yang sudah terisi, tahap saat ini, keputusan yang sudah diambil) — bukan transkrip percakapan lengkap.
- Wajib ada field `version` di payload supaya perubahan skema di masa depan tidak merusak data lama (sudah dipraktikkan di `DocumentSessionStore`).
- Working Memory boleh dianggap habis/direset setelah alur kerja selesai (dokumen jadi, konten sudah publish) — tidak perlu disimpan selamanya.

### 2. Long-Term Feedback Memory (lintas sesi, permanen)
Ini yang membuat agent "makin pintar" dari waktu ke waktu: kumpulan koreksi, keputusan, dan hasil nyata yang terus bertambah, dibaca ulang sebagai referensi saat agent mengambil keputusan baru.

Pola yang sudah dipakai: tabel audit `finance_corrections` (`app/finance_corrections.py`) — setiap koreksi dicatat sebagai baris baru (`original_transaction_id`, `replacement_transaction_id`, `old_value`, `new_value`, `reason`), transaksi lama ditandai `reversed`, bukan dihapus.

Social Media Agent memakai prinsip yang sama untuk Content Learning (`agents/social_media_agent.md`): draft yang disetujui/diedit, dan data performa konten, disimpan sebagai event historis per usaha.

Prinsip:
- **Append, jangan overwrite.** Riwayat lama tetap ada; koreksi/perubahan baru dicatat sebagai entri baru yang mereferensikan entri lama.
- Setiap entri minimal punya: `created_at`, `scope`/`usaha`, `field/aspek yang dikoreksi`, `nilai lama`, `nilai baru`, `alasan/sumber`.
- Data ini yang dibaca ulang sebagai **konteks tambahan** saat agent membuat keputusan baru (contoh: kategori transaksi, draft caption) — bukan dipakai untuk melatih ulang model AI. AI Model tetap sama; yang berubah adalah konteks/contoh yang diberikan kepadanya.
- Prioritaskan pola yang berulang dibanding satu kejadian tunggal (lihat aturan Content Learning dan Auto Category Learning).

### 3. Reference / Static Knowledge (tidak berubah otomatis)
Pengetahuan yang jadi acuan tetap, hanya berubah kalau owner mengedit filenya secara sengaja.

Contoh: `agents/*.md`, `brand_profiles/*.md`, `policies/*.md`, `docs/social_media_content_research.md`, `skills/document_academic/*.md`.

Prinsip:
- File ini dibaca sebagai instruksi/pengetahuan, tidak pernah ditulis otomatis oleh agent tanpa sepengetahuan owner.
- Riwayat di Long-Term Feedback Memory tidak boleh diam-diam "menimpa" aturan di lapisan ini (contoh: draft yang sering dikoreksi tetap harus sesuai Brand Profile, bukan mengubah Brand Profile itu sendiri secara otomatis). Kalau pola koreksi menunjukkan Brand Profile perlu diperbarui, itu harus diajukan ke owner sebagai usulan, bukan diubah sendiri oleh agent.

## Bagaimana "Sambung-Menyambung" Bekerja
Yang membuat percakapan terasa nyambung bukan agent mengirim ulang seluruh riwayat chat ke model AI setiap kali (boros token, gampang "lupa" karena kepotong, dan berisiko privasi kalau disimpan mentah selamanya). Yang dipakai adalah:

1. Working Memory dipanggil balik pakai `scope_id` yang konsisten setiap kali alur kerja yang sama dilanjutkan (via Telegram, Web Admin, atau restart proses) — sehingga agent tahu "sedang di tahap mana" tanpa user mengulang dari awal.
2. Long-Term Feedback Memory dipanggil sebagai referensi tambahan yang relevan dengan usaha/topik saat itu saja (bukan seluruh riwayat sekaligus), supaya tetap ringkas dan relevan.
3. Reference/Static Knowledge selalu dibaca sebagai dasar aturan, terlepas dari sesi mana pun.

## Retensi & Privasi
Mengikuti `policies/security_policy.md` dan `policies/permissions.md`:
- Tidak menyimpan secret/API key/token di lapisan memory manapun.
- Working Memory boleh dibersihkan setelah alur kerja selesai; Long-Term Feedback Memory tidak dihapus permanen (audit trail), tapi bisa diarsipkan kalau volumenya besar.
- Data pelanggan pada Working Memory dibatasi seperlunya untuk tugas yang sedang berjalan, sesuai prinsip Data Isolation di `security_policy.md`.

## Status
- v0.1-draft. Working Memory dan Long-Term Feedback Memory untuk Finance Agent dan Document Agent sudah ada implementasinya. Untuk Social Media Agent, ini masih rancangan yang mengikuti pola yang sama dan menunggu implementasi kode.
