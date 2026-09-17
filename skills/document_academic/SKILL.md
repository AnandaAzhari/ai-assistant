# Document Academic Skill — Referensi Default

Skill ini adalah referensi aktif untuk Document Agent saat membuat Makalah, KTI, atau Skripsi ketika pelanggan **tidak memberikan pedoman resmi** dari guru, dosen, sekolah, program studi, fakultas, atau kampus.

## Prioritas aturan

1. Pedoman/template/rubrik resmi guru, dosen, sekolah, program studi, fakultas, atau kampus.
2. Instruksi khusus pelanggan yang jelas.
3. Policy jenis dokumen dan format Taqi AI.
4. Referensi fallback pada skill ini.

Jangan menganggap fallback sebagai aturan universal. Begitu ada pedoman resmi, pedoman resmi mengalahkan fallback hanya pada bagian yang diaturnya.

## Fallback tipografi akademik

Jika tidak ada arahan resmi, gunakan titik awal berikut:

- Kertas A4.
- Font Times New Roman 12 pt untuk naskah utama.
- Spasi baris 1,5 untuk teks utama.
- Margin awal yang aman: kiri 4 cm; atas, kanan, bawah 3 cm.
- Semua paragraf isi utama memakai **Justify / rata kiri-kanan**.
- Awal paragraf memakai **first-line indent sekitar 1,25–1,27 cm**. Engine Taqi AI memakai 1,27 cm / 0,5 inci sebagai default praktis; jika pedoman resmi menentukan 1,25 cm, ikuti pedoman tersebut.
- Jangan memakai karakter TAB manual atau spasi berulang untuk membentuk indentasi.
- Paragraf akademik idealnya fokus pada satu gagasan pokok, runtut, koheren, dan umumnya sekitar **3–5 kalimat** bila isi memungkinkan. Ini pedoman kualitas, bukan batas keras; jangan memaksa paragraf jika secara logis perlu lebih pendek atau lebih panjang.
- Hindari paragraf satu kalimat tanpa alasan yang jelas dan hindari paragraf sangat panjang yang mencampur banyak gagasan.

## Fallback Makalah

Struktur default:

`BAB I -> A. -> 1. -> a.`

Format heading:

- Heading 1: `BAB I`, `BAB II`, `BAB III`, dst.; rata tengah, tebal, dimulai pada halaman baru.
- `DAFTAR PUSTAKA` diperlakukan sebagai Heading 1 khusus bagian akhir dan dimulai pada halaman baru.
- Heading 2: `A.`, `B.`, `C.`, dst.; rata kiri pada margin utama (left indent 0 cm).
- Heading 3: `1.`, `2.`, `3.`, dst.; left indent sekitar 0,63 cm.
- Heading 4: `a.`, `b.`, `c.`, dst.; left indent sekitar 1,27 cm.
- Isi setelah Heading 2 dan Heading 3 memakai margin utama dengan first-line indent sekitar 1,25–1,27 cm dan Justify.
- **Khusus isi setelah Heading 4 (`a.`, `b.`, `c.`)**, gunakan left indent sekitar **0,63 cm** dan first-line indent sekitar **0,63 cm**. Jadi awal baris pertama tetap sekitar **1,27 cm** dari margin utama, sementara baris berikutnya dimulai sekitar **0,63 cm** dari margin utama. Ini adalah fallback visual yang dipilih agar hubungan sub-subbagian dengan paragrafnya lebih mudah dibaca tanpa membuat blok teks terlalu sempit.
- Level `1.` dan `a.` hanya dipakai jika memang dibutuhkan.

Daftar Isi default Makalah:

- Tampilkan Heading 1, Heading 2, dan Heading 3.
- Heading 1 = `BAB ...` dan `DAFTAR PUSTAKA`.
- Heading 2 = `A.`, `B.`, `C.`, dst.
- Heading 3 = `1.`, `2.`, `3.`, dst.
- **Heading 4 (`a.`, `b.`, `c.`) tidak ditampilkan di Daftar Isi secara default**, tetapi tetap dipakai di isi dokumen jika diperlukan.
- Engine memakai field Word `TOC \\o "1-3"` sebagai default Makalah.
- Jika pedoman resmi meminta kedalaman Daftar Isi yang berbeda, ikuti pedoman resmi.

Penomoran halaman default Makalah:

- Cover: tanpa nomor tampil.
- Kata Pengantar dan Daftar Isi: Romawi kecil mulai `i`.
- BAB I: reset ke angka Arab `1`.
- Angka Arab berlanjut sampai Daftar Pustaka.

### Makalah Kuliah — struktur awal bila tidak ada pedoman dosen/kampus

Untuk mahasiswa/kuliah, gunakan struktur berikut sebagai referensi awal:

1. **Halaman Sampul**
   - judul makalah;
   - nama penulis/anggota kelompok;
   - NIM bila tersedia;
   - mata kuliah;
   - nama dosen pengampu;
   - fakultas/program studi dan universitas bila tersedia;
   - tahun penulisan.
2. **Kata Pengantar** — singkat, formal, memuat tujuan penulisan dan ucapan terima kasih seperlunya.
3. **Daftar Isi** — harus sesuai dengan judul bagian dan nomor halaman final; default hanya menampilkan Heading 1 sampai Heading 3.
4. **BAB I — PENDAHULUAN**
   - A. Latar Belakang
   - B. Rumusan Masalah
   - C. Tujuan Penulisan
   - D. Manfaat Penulisan bila diperlukan
5. **BAB II — PEMBAHASAN**
   - uraikan materi sesuai rumusan masalah;
   - gunakan subbab yang jelas;
   - dukung pembahasan dengan teori, data, pendapat ahli, dan sumber ilmiah yang relevan;
   - hindari opini pribadi tanpa dasar.
6. **BAB III — PENUTUP**
   - A. Kesimpulan — merangkum jawaban atas rumusan masalah tanpa menambah informasi baru;
   - B. Saran — rekomendasi/harapan yang relevan bila diperlukan.
7. **DAFTAR PUSTAKA** — hanya sumber yang benar-benar digunakan, dengan gaya sitasi yang konsisten sesuai arahan dosen.

Struktur ini diadaptasi dari referensi makalah kuliah 2026 yang diberikan pengguna dan tetap tunduk pada pedoman resmi dosen/kampus.

## Fallback KTI

Jika tidak ada pedoman instansi:

- Struktur heading: `1 -> 1.1 -> 1.1.1`.
- Gunakan fallback tipografi akademik di atas untuk font, spasi, margin, paragraf, dan Justify.
- Struktur isi mengikuti `policies/document_type_structure_policy.md`.

## Fallback Skripsi

Skripsi paling bergantung pada pedoman kampus. Document Agent harus meminta atau menawarkan penggunaan pedoman kampus jika tersedia.

Jika pelanggan benar-benar tidak memiliki pedoman:

- gunakan fallback tipografi akademik di atas sebagai **draft awal**, bukan klaim standar kampus;
- gunakan struktur kerja awal Skripsi pada `policies/document_type_structure_policy.md`;
- bagian awal memakai angka Romawi kecil dan isi utama memakai angka Arab mulai BAB I;
- format BAB/subbab, posisi nomor halaman, margin, dan gaya sitasi harus dapat diganti saat pedoman kampus diberikan kemudian;
- sebelum finalisasi Skripsi, beri kesempatan pelanggan mengoreksi format institusinya.

## Prinsip Word

- Gunakan properti paragraph/style Word, bukan karakter TAB/spasi manual.
- Justify = properti paragraph alignment.
- First-line indent = properti paragraph indentation.
- Heading memakai style Heading 1/2/3/4 sesuai hierarki agar Daftar Isi otomatis stabil.
- Fallback visual level-4 tidak dibuat dengan karakter TAB manual; engine harus menggunakan `left indent` dan `first-line indent` Word.
- Untuk Makalah, field TOC default hanya mengambil Heading 1 sampai Heading 3; Heading 4 tetap tersedia di dokumen tetapi tidak tampil di Daftar Isi kecuali pedoman resmi meminta.

## Interaksi pelanggan saat persetujuan kerangka

- Pelanggan **tidak wajib** mengetahui kata khusus seperti `setuju` dan tidak boleh diwajibkan memakai slash command.
- Bahasa natural seperti `lanjutkan`, `lanjut aja`, `lanjut saja`, `oke lanjut`, `boleh lanjut`, `sudah sesuai`, `sudah pas`, `iya`, atau ungkapan persetujuan yang setara dapat dipakai untuk menyetujui kerangka.
- Kalimat yang mengandung revisi seperti `lanjutkan tapi ubah BAB II`, `belum sesuai`, `jangan lanjut dulu`, `tolong revisi`, `tambahkan`, `hapus`, atau `ganti` **tidak boleh** dianggap persetujuan.
- Persetujuan sederhana harus diproses lokal tanpa memanggil model AI lagi.
- Setelah kerangka dibuat, sistem menambahkan petunjuk balasan pelanggan secara deterministik. Jangan mengandalkan model untuk selalu menulis petunjuk ini karena output model dapat mencapai batas provider.
- Kerangka tidak boleh sengaja dipotong oleh batas kecil aplikasi. Runtime Document Agent memakai batas keluaran tinggi sesuai ceiling provider agar kerangka dapat selesai; provider/model tetap memiliki batas teknis maksimum yang tidak dapat dibuat benar-benar tak terbatas.

## Loop data cover

- Data cover **tidak dikunci permanen** hanya karena data wajib sudah lengkap.
- Pelanggan boleh menambah atau mengoreksi nama sekolah/kampus, tahun ajaran, nama guru/dosen, nama/nomor kelompok, atau data cover lain selama order masih aktif dan file final belum dikunci.
- Nilai seperti `Tidak dicantumkan` boleh diganti oleh nilai nyata yang diberikan pelanggan kemudian.
- Untuk pola yang jelas, gunakan parser lokal di `app/document_cover.py` tanpa token AI.
- Pelanggan tidak wajib memakai format `Label: Nilai`; bahasa seperti `Nama Sekolah SMK Negeri 2 Padangsidimpuan`, `tahun ajaran 2026/2027`, atau `Nama Guru Purnama Sari` harus dapat dipahami.
- Fase `ready_for_draft` tetap memanggil parser cover pada setiap pesan, sehingga data opsional dapat ditambahkan belakangan tanpa reset sesi.
- AI fallback hanya diperlukan jika bahasa pelanggan benar-benar ambigu dan tidak aman dipetakan secara lokal.
- Referensi detail implementasi: `skills/document_academic/COVER_DATA.md`.

## Referensi awal fallback

Referensi ini dipakai sebagai dasar awal, bukan sebagai pengganti pedoman institusi:

1. **Fakultas Ekonomi dan Bisnis Universitas Borneo Tarakan, Pedoman Penulisan Skripsi dan Tesis 2026**: teks utama 1,5 spasi; first-line indent 1,25 cm; teks Justify; paragraf ideal 3–5 kalimat dengan satu gagasan pokok; daftar pustaka 1 spasi dan hanging indent 1,25 cm.
   https://fe.ubt.ac.id/wp-content/uploads/2026/04/Pedoman-Penulisan-Skripsi-dan-Tesis-2026-4.pdf
2. **Sekolapedia / Teknokrat, Panduan Lengkap Cara Membuat Makalah Kuliah yang Baik untuk Mahasiswa (2026)**: struktur Halaman Sampul → Kata Pengantar → Daftar Isi → Pendahuluan → Pembahasan → Penutup → Daftar Pustaka; digunakan sebagai referensi struktur makalah kuliah, bukan pedoman institusi resmi.
   https://daftarsekolah.spmb.teknokrat.ac.id/2026/02/panduan-lengkap-cara-membuat-makalah-kuliah-yang-baik-untuk-mahasiswa/
3. UPN Veteran Jawa Timur, *Thesis Writing Guidelines 2025*: Times New Roman 12, margin kiri 4 cm dan sisi lain 3 cm, first-line indent 1 tab = 1,27 cm.
   https://agrotek.upnjatim.ac.id/wp-content/uploads/2025/09/Thesis-Writing-Guidelines-2025_.pdf
4. Fakultas Ushuluddin dan Pemikiran Islam UIN Sunan Kalijaga, *Pedoman Penulisan Proposal dan Skripsi*: spasi 1,5, first-line indent 1,27 cm, seluruh naskah justify, serta contoh hierarki `BAB -> A. -> 1. -> a.`.
   https://ushuluddin.uin-suka.ac.id/media/dokumen_akademik/05_20221207_4.%20Skripsi%20Final.pdf
5. Program Studi Kimia UIN Sunan Kalijaga, *Pedoman Penulisan Skripsi*: BAB sebagai Heading 1, `A./B./C.` sebagai Heading 2, dan penomoran bertingkat dengan pengaturan indentasi.
   https://kimia.uin-suka.ac.id/media/dokumen_akademik/63_20180806_PEDOMAN%20PENULISAN%20SKRIPSI.pdf

## Aturan stabilitas

Skill ini adalah **fallback**. Jangan diam-diam mengubah format yang sudah disepakati pengguna atau format resmi institusi hanya karena referensi lain terlihat lebih umum.