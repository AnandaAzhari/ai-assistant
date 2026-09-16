# Document Type Structure Policy

Dokumen ini menetapkan struktur default berdasarkan **jenis dokumen**. Aturan ini dipakai hanya ketika pelanggan tidak memberikan pedoman resmi dari guru, dosen, sekolah, atau kampus.

## Prioritas

1. Pedoman/template/rubrik resmi guru, dosen, sekolah, program studi, fakultas, atau kampus.
2. Instruksi khusus pelanggan yang jelas.
3. Struktur default berdasarkan jenis dokumen di file ini.
4. Preferensi model AI.

AI tidak boleh mengganti struktur hanya karena model lebih menyukai format lain.

## 1. Makalah

Untuk **makalah**, gunakan pola penomoran seperti contoh referensi pelanggan:

- I. Pendahuluan
  - A. Latar Belakang
  - B. Rumusan Masalah
  - C. Tujuan Penulisan
- II. Tinjauan Pustaka
  - A. Pengertian Konsep
  - B. Teori yang Terkait
    - 1. Teori A
    - 2. Teori B
  - C. Kajian Literatur
- III. Metodologi Penelitian
  - A. Jenis Penelitian
  - B. Lokasi dan Waktu Penelitian
  - C. Teknik Pengumpulan Data
    - 1. Wawancara
    - 2. Observasi
    - 3. Studi Dokumen
  - D. Analisis Data
- IV. Hasil Penelitian dan Pembahasan
  - A. Deskripsi Hasil Penelitian
  - B. Analisis Data
    - 1. Analisis Statistik
      - a. Analisis Regresi
      - b. Analisis Korelasi
    - 2. Analisis Deskriptif
      - a. Analisis Frekuensi
      - b. Analisis Persentase
  - C. Pembahasan
- V. Kesimpulan dan Saran
  - A. Kesimpulan
  - B. Saran
  - C. Implikasi Penelitian bila diperlukan
- VI. Daftar Pustaka

Nama bagian boleh menyesuaikan topik dan kebutuhan tugas, tetapi **pola penomoran default makalah harus tetap**:

`I, II, III, ...` → `A, B, C, ...` → `1, 2, 3, ...` → `a, b, c, ...`

Jangan mengubah makalah menjadi pola `BAB I → 1.1 → 1.1.1` kecuali guru/dosen/sekolah/kampus memang meminta format tersebut.

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

Default harus dibedakan dengan tegas:

- **Makalah:** `I → A → 1 → a`
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