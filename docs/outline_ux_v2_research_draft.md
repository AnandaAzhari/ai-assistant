# Outline UX v2 + otomatisasi riset/draft

Implementasi 17 September 2026; melanjutkan snapshot upstream `5cfda87439953c06d9d137f69f44a230dee74ccb`.

## Perilaku pelanggan

1. Data inti lengkap → ringkasan Python, usulan fokus jika diperlukan, kerangka, satu petunjuk persetujuan.
2. Setujui → fokus yang terlihat dikunci ke brief, lanjut cover.
3. Pada alur AI-first Nara, persetujuan kerangka diingat selama cover dilengkapi; setelah lengkap, riset/draft berjalan. Jeda membatalkan kelanjutan otomatis. Fallback lokal tetap mendukung `lanjutkan` / `sudah cukup`.
4. Riset membuat maksimal dua kueri lalu memilih sumber berdasarkan metadata/abstrak. Sumber tanpa abstrak tidak dipakai otomatis.
5. Draft hanya menerima ID sumber terpilih dari scope order. Sitasi tidak dikenal, rusak, atau kosong ditolak.
6. Setelah draft siap, `lanjutkan` menjalankan CitationEngine/Word/PDF yang sudah ada.

Kegagalan revisi mengharuskan revisi selesai dan disetujui kembali. Kegagalan riset/draft mempertahankan data sesi; retry draft memakai sumber terpilih yang tersimpan. Permintaan serentak untuk agen yang sama ditolak sebagai sedang diproses.

## Batas pengujian

Pengujian lokal menggunakan model dan pencarian tiruan serta SQLite sementara. Belum ada uji langsung DeepSeek, OpenAlex/Crossref, maupun alur Word/PDF pada Windows pengguna untuk perubahan ini.

Riset otomatis menilai metadata dan abstrak, bukan teks penuh. Relevansi dan ketentuan sumber dinilai model, sehingga tetap membutuhkan review hasil; validasi deterministik memeriksa identitas kandidat dan marker sitasi, bukan seluruh kebenaran akademik.

Web Admin kini menyimpan brief, cover, kerangka, fokus, percakapan terakhir, draft, dan status ke SQLite melalui DocumentSessionStore. Web Admin tetap satu sesi admin. Parameter `source_scope` tersedia untuk instance agen per order; routing multi-pelanggan bukan bagian perubahan ini.

## Uji lokal

- `test_document_outline_flow.py`: 14 tes lulus.
- `test_document_automation.py`: 19 tes lulus setelah perbaikan pesan kegagalan/retry.
- `test_document_cover_loop.py`: 25 tes lulus setelah perbaikan pesan gabungan.
- `test_makalah*.py`: 23 tes lulus.
- `test_citation*.py`: 7 tes lulus.

Suite `test_document*.py` pada snapshot awal memiliki empat kegagalan yang juga teramati sebelum perubahan:

- `test_document_agent_calls_provider`, `test_lead_routes_makalah_to_document_agent`, `test_unconfigured_provider_does_not_call_api`: ekspektasi lama belum mengikuti tahap `needs_requirements`.
- `test_judul_belum_is_not_saved_as_title`: parser lama menyimpan `belum, 8 halaman` sebagai judul.

Kegagalan lama tersebut belum diperbaiki pada perubahan ini. Jangan menyatakan seluruh suite hijau.

## Checkpoint pengguna

Mulai dari satu perintah Git Bash:

```bash
cd /d/ai-assistant && git pull --ff-only && python -m unittest discover -s tests -p "test_document_outline_flow.py"
```

Setelah hasil tes dikonfirmasi, jalankan ulang Web Admin dan coba order baru dengan input dari handoff. Periksa hanya satu petunjuk approval dan konfirmasi fokus sebelum melanjutkan uji cover → riset → draft.

## Perbaikan dari uji langsung cover

- Pesan gabungan dipisahkan pada koma, titik koma, atau baris baru; semua field yang jelas diproses sebelum menyelesaikan nama polos berdasarkan konteks.
- Satu nama polos pada tugas individu yang sedang menunggu nama dapat mengisi penyusun. Jika terdapat beberapa nama tanpa peran yang jelas, data sekolah/tahun tetap disimpan dan nama dimintakan klarifikasi.
- Gelar dengan titik dan daftar anggota eksplisit mempertahankan koma. Koreksi `bukan ..., ganti menjadi ...` tetap diproses sebagai satu bagian.
- Konfirmasi cover yang belum lengkap tidak lagi mengajak pelanggan melanjutkan; cover lengkap menampilkan satu petunjuk melanjutkan.
- `sudah cukup` sudah merupakan persetujuan riset, bukan kegagalan pengenalan intent. Pesan penyiapan sumber kini membedakan tahap gagal: kata kunci AI, pencarian, kelengkapan metadata/abstrak, atau seleksi sumber.
- `coba lagi` / `ulangi riset` diterima untuk mengulang di fase siap draft. Respons tidak lagi memberi kesan pelanggan wajib mengganti `sudah cukup` dengan `lanjutkan`.
- Penyebab kegagalan riset pada uji Windows sebelumnya belum dapat ditentukan karena pesan versi lama menggabungkan semua kegagalan. Perubahan ini memberi diagnosis tahap; tidak mengklaim koneksi provider/sumber telah diperbaiki.
- Data yang sudah tercampur oleh parser lama perlu dikirim kembali setelah pembaruan; tidak dilakukan migrasi otomatis terhadap nilai ambigu. Sesi yang diproses setelah pembaruan Nara disimpan saat tiap giliran selesai, juga sebelum panggilan outline/riset yang lama. Data RAM dari versi lama yang belum pernah tersimpan tidak bisa dipulihkan setelah restart.

## Nara AI-first — pemahaman lintas fase dan sesi persisten

- `agents/document_agent.md` menetapkan identitas Nara, dimuat ke interpreter, outline, dan draft.
- `skills/document_academic/CONVERSATION.md` adalah panduan aktif interpretasi percakapan.
- Satu panggilan interpreter menerima brief, cover, fase, kerangka, dan riwayat terkini.
- JSON mengembalikan patch brief/cover, evidence kutipan pesan, intent, jawaban pertanyaan,
  dan klarifikasi. Schema/type/nilai/evidence divalidasi sebelum mutasi; nilai null tidak mengubah data.
- Kutipan evidence memeriksa asal perubahan, bukan membuktikan bahwa penafsiran model selalu benar.
- AI sukses tidak ditambal parser lokal. Provider gagal/output tidak valid memakai fallback lama;
  mode pemahaman terakhir terlihat melalui `/dokumen_status`.
- Pertanyaan tidak otomatis merevisi outline. Jeda menghentikan kelanjutan. Koreksi kebutuhan
  membatalkan hasil lama dan meminta persetujuan kerangka baru. Cover yang dikoreksi setelah
  draft memperbarui metadata draft, membatalkan file lama, tanpa membuat isi ulang.
- Persetujuan/kelengkapan selalu diperiksa program. Model tidak dapat mengirim perintah alat.
- Web Admin menyimpan sesi ke DATABASE_PATH; sumber dan preferensi tetap dalam penyimpanan
  masing-masing. Instance DocumentAgent lain harus diberi session_store untuk mengaktifkannya.
- Pemulihan tidak menjalankan riset otomatis saat startup. Reset lewat Lead juga melalui handle
  sehingga disimpan dan tidak menghidupkan sesi lama kembali setelah restart.
- Belum ada pemisahan banyak pelanggan di Web Admin. Belum ada pelatihan model otomatis.
- Revisi isi saat ini kembali lewat kerangka dan pembuatan draft; belum editor revisi paragraf.
- Endpoint riset masih menilai metadata/abstrak; kualitas sumber dan keluaran Word/PDF tetap
  perlu diperiksa pada uji Windows. Pergantian provider bukan bagian perubahan ini.

### Validasi perubahan Nara

`python -m unittest discover -s tests -p "test_nara_conversation.py"`

28 tes baru dan 148 tes relevan lulus secara lokal. Tes baru memakai provider simulasi dan SQLite sementara: pesan gabungan, koreksi parsial,
cover awal, persetujuan semantik, revisi bersyarat, pertanyaan, jeda, kelengkapan, invalidasi
draft, koreksi cover setelah draft, pemisahan scope, restart, reset, schema/evidence invalid,
dan kegagalan penyimpanan. Tes tidak membuktikan akurasi bahasa model live.

Tes regresi cover/outline/otomatisasi kini menghitung satu panggilan interpretasi tambahan.
Empat kegagalan lama yang disebut di atas tetap ada; jangan menyatakan seluruh suite lulus.

### Skenario uji langsung berikutnya

1. Restart Web Admin setelah git pull. Mulai pesanan baru.
2. Kirim brief makalah lengkap, lalu setujui outline dengan bahasa sehari-hari.
3. Kirim lima data cover dalam satu kalimat. Periksa seluruh nilai tercatat dan nama tidak
   ditanyakan lagi; bila cover lengkap Nara melanjutkan riset berdasar persetujuan sebelumnya.
4. Untuk memeriksa sesi: pada pesanan lain, kirim data sebagian, restart, lalu lengkapi sisanya.
   Data lama harus tetap muncul dalam konteks. Jangan mengasumsikan riwayat tampilan browser
   adalah bukti pemulihan database; periksa data yang dipakai Nara.
