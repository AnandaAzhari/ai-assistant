# Document Type Structure Policy

Dokumen ini menetapkan struktur default berdasarkan **jenis dokumen**. Aturan ini dipakai hanya ketika pelanggan tidak memberikan pedoman resmi dari guru, dosen, sekolah, atau kampus.

## Prioritas

1. Pedoman/template/rubrik resmi guru, dosen, sekolah, program studi, fakultas, atau kampus.
2. Instruksi khusus pelanggan yang jelas.
3. Struktur default berdasarkan jenis dokumen di file ini.
4. Referensi fallback aktif pada `skills/document_academic/SKILL.md`.
5. Preferensi model AI.

AI tidak boleh mengganti struktur hanya karena model lebih menyukai format lain.

## 1. Makalah

Default **Makalah** Taqi AI menggunakan BAB untuk bagian utama dan huruf/angka untuk turunannya:

- Cover
- Kata Pengantar
- Daftar Isi
- BAB I — PENDAHULUAN
  - A. Latar Belakang
  - B. Rumusan Masalah
  - C. Tujuan Penulisan
  - D. Manfaat Penulisan bila diperlukan
- BAB II — PEMBAHASAN
  - A. Subbagian sesuai topik
  - B. Subbagian sesuai topik
    - 1. Rincian bila diperlukan
      - a. Rincian lebih lanjut bila diperlukan
      - b. Rincian lebih lanjut bila diperlukan
  - C. Subbagian sesuai topik
- BAB III — PENUTUP
  - A. Kesimpulan
  - B. Saran
- DAFTAR PUSTAKA

Hierarki default Makalah adalah:

`BAB I, BAB II, BAB III, ...` → `A, B, C, ...` → `1, 2, 3, ...` → `a, b, c, ...`

Level style Word default Makalah:

- `BAB ...` = Heading 1
- `DAFTAR PUSTAKA` = Heading 1 khusus bagian akhir
- `A.`, `B.`, `C.`, dst. = Heading 2
- `1.`, `2.`, `3.`, dst. = Heading 3
- `a.`, `b.`, `c.`, dst. = Heading 4

Huruf `C`, `D`, `M`, dan huruf lain yang kebetulan juga merupakan simbol angka Romawi **tetap dianggap huruf subbagian** bila ditulis seperti `C. Tujuan Penulisan`. Heading utama BAB Makalah hanya dikenali bila memakai label `BAB`; `DAFTAR PUSTAKA` adalah pengecualian khusus karena diperlakukan sebagai Heading 1 bagian akhir.

Level `1.` dan `a.` tidak wajib muncul. Gunakan hanya jika subbagian memang perlu dipecah lagi. Jangan mengubah Makalah menjadi pola `BAB I → 1.1 → 1.1.1` atau `I → A → 1 → a` tanpa instruksi resmi.

Setiap Heading 1 Makalah dimulai pada halaman baru. `BAB II` tidak boleh menyambung langsung setelah subbagian terakhir `BAB I`, dan `DAFTAR PUSTAKA` tidak boleh menempel di bawah isi `BAB III`. Page break antar-Heading 1 tidak mereset nomor halaman.

### Daftar Isi Makalah

Jika tidak ada pedoman khusus:

- Daftar Isi menampilkan **Heading 1 sampai Heading 3 saja**.
- Heading 1: BAB dan `DAFTAR PUSTAKA`.
- Heading 2: `A.`, `B.`, `C.`, dst.
- Heading 3: `1.`, `2.`, `3.`, dst.
- Heading 4 (`a.`, `b.`, `c.`) tetap boleh digunakan di isi, tetapi **tidak ditampilkan pada Daftar Isi default**.
- Jika pedoman resmi menetapkan kedalaman lain, pedoman resmi mengalahkan aturan ini.

### 1.1 Makalah Kuliah

Jika pelanggan adalah mahasiswa dan meminta **makalah kuliah**, sementara dosen/kampus tidak memberikan struktur khusus, gunakan struktur awal berikut:

1. **Halaman Sampul**
   - judul makalah;
   - nama penulis/anggota kelompok;
   - NIM bila tersedia;
   - nama mata kuliah;
   - nama dosen pengampu;
   - program studi/fakultas dan universitas bila tersedia;
   - tahun penulisan.
2. **Kata Pengantar** — singkat dan formal.
3. **Daftar Isi** — sesuai bagian dan nomor halaman final; default hanya sampai Heading 3.
4. **BAB I — PENDAHULUAN**
   - A. Latar Belakang
   - B. Rumusan Masalah
   - C. Tujuan Penulisan
   - D. Manfaat Penulisan bila diperlukan
5. **BAB II — PEMBAHASAN**
   - membahas jawaban atas rumusan masalah;
   - memakai subbab yang jelas;
   - didukung teori, data, pendapat ahli, dan referensi yang relevan;
   - opini pribadi tanpa dasar tidak boleh menjadi isi utama.
6. **BAB III — PENUTUP**
   - A. Kesimpulan — merangkum hasil pembahasan dan menjawab rumusan masalah tanpa menambah informasi baru;
   - B. Saran — rekomendasi yang relevan bila diperlukan.
7. **DAFTAR PUSTAKA** — hanya sumber yang benar-benar dipakai dan ditulis konsisten sesuai gaya sitasi yang diminta.

Struktur Makalah Kuliah ini sejalan dengan referensi 2026 yang tercantum pada `skills/document_academic/SKILL.md`. Referensi web bukan pengganti pedoman resmi dosen/kampus.

## 2. Karya Tulis Ilmiah (KTI)

Jika pelanggan secara jelas meminta KTI dan tidak ada pedoman instansi, gunakan penomoran desimal bertingkat tanpa label `BAB` sebagai default:

- 1. Pendahuluan
- 2. Tinjauan Pustaka
  - 2.1 Konsep Dasar
  - 2.2 Kerangka Teori
- 3. Metode Penelitian
  - 3.1 Jenis Penelitian
  - 3.2 Populasi dan Sampel
  - 3.3 Teknik Pengumpulan Data
  - 3.4 Teknik Analisis Data
- 4. Hasil dan Pembahasan
  - 4.1 Deskripsi Data
  - 4.2 Analisis Data
- 5. Kesimpulan dan Saran
  - 5.1 Kesimpulan
  - 5.2 Saran
- Daftar Pustaka

Hierarki default KTI: `1` → `1.1` → `1.1.1`.

Nama bagian dapat menyesuaikan jenis KTI dan kebutuhan penelitian, tetapi pola penomorannya jangan diubah tanpa alasan.

## 3. Skripsi

Skripsi sangat bergantung pada pedoman program studi/fakultas/kampus. Jika pelanggan memiliki pedoman resmi, **pedoman tersebut wajib menjadi sumber utama**. Jangan mengasumsikan satu struktur berlaku untuk semua kampus.

Jika pelanggan belum memiliki pedoman, struktur kerja awal yang boleh dipakai adalah:

### Bagian awal

- Halaman Judul
- Halaman Pengesahan
- Abstrak
- Kata Pengantar
- Daftar Isi
- Daftar Tabel, bila ada
- Daftar Gambar, bila ada

### Isi utama

- BAB 1 / BAB I — Pendahuluan
  - 1.1 Latar Belakang
  - 1.2 Rumusan Masalah
  - 1.3 Tujuan Penelitian
  - 1.4 Manfaat Penelitian
  - 1.5 Kerangka Konsep bila diperlukan
- BAB 2 / BAB II — Tinjauan Pustaka
  - 2.1 Konsep Dasar
  - 2.2 Teori yang Berkaitan
  - 2.3 Penelitian Terdahulu
- BAB 3 / BAB III — Metode Penelitian
  - 3.1 Jenis Penelitian
  - 3.2 Lokasi dan Waktu Penelitian
  - 3.3 Populasi dan Sampel
  - 3.4 Teknik Pengumpulan Data
    - 3.4.1 Teknik Wawancara
    - 3.4.2 Teknik Observasi
  - 3.5 Teknik Analisis Data
- BAB 4 / BAB IV — Hasil dan Pembahasan
  - 4.1 Deskripsi Data
    - 4.1.1 Deskripsi Karakteristik Responden
    - 4.1.2 Deskripsi Variabel Penelitian
  - 4.2 Analisis Data
    - 4.2.1 Uji Validitas dan Reliabilitas
    - 4.2.2 Uji Normalitas
    - 4.2.3 Uji Hipotesis
  - 4.3 Pembahasan
- BAB 5 / BAB V — Kesimpulan dan Saran
  - 5.1 Kesimpulan
  - 5.2 Saran

### Bagian akhir

- Daftar Pustaka
- Lampiran, bila ada

Hierarki kerja awal Skripsi: `BAB I/BAB 1` → `1.1` → `1.1.1`.

Untuk skripsi, format `BAB I` versus `Bab 1`, letak nomor halaman, margin, gaya sitasi, susunan bab, dan bagian awal **harus mengikuti pedoman kampus bila tersedia**.

## 4. Tiga jenis dokumen tidak boleh dicampur

Default dibedakan dengan tegas:

- **Makalah:** `BAB I → A → 1 → a`
- **KTI:** `1 → 1.1 → 1.1.1`
- **Skripsi:** `BAB I/BAB 1 → 1.1 → 1.1.1`

Document Agent wajib mengenali jenis dokumen sebelum membuat kerangka. Jangan memakai struktur Makalah untuk KTI, struktur KTI untuk Skripsi, atau sebaliknya.

## 5. Penomoran halaman terpisah dari penomoran heading

Sistem heading di atas tidak menentukan nomor halaman. Default nomor halaman dokumen akademik tetap mengikuti `document_format_policy.md`:

- cover/halaman judul: tidak menampilkan nomor;
- bagian awal: Romawi kecil `i, ii, iii, ...`;
- isi utama: angka Arab dimulai dari `1`;
- angka Arab berlanjut sampai Daftar Pustaka dan bagian akhir yang termasuk isi bernomor, kecuali pedoman resmi menentukan lain.

## Prinsip stabilitas

Document Agent wajib mendeteksi jenis dokumen terlebih dahulu. Bila jenis dokumen tidak jelas, tanyakan pelanggan. Setelah jenis dipilih, struktur tidak boleh berpindah ke pola dokumen lain tanpa instruksi pelanggan atau pedoman resmi.