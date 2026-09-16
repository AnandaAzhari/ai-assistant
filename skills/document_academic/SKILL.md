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
- Spasi baris 1,5.
- Margin awal yang aman: kiri 4 cm; atas, kanan, bawah 3 cm.
- Semua paragraf isi utama memakai **Justify / rata kiri-kanan**.
- Awal paragraf memakai **first-line indent 1,27 cm** (720 twips / 0,5 inci), bukan karakter TAB manual.
- Jangan memakai spasi manual berulang untuk mengatur posisi teks.

## Fallback Makalah

Struktur default:

`BAB I -> A. -> 1. -> a.`

Format heading:

- Heading 1: `BAB I`, `BAB II`, `BAB III`, dst.; rata tengah, tebal, dimulai pada halaman baru.
- `DAFTAR PUSTAKA` diperlakukan sebagai Heading 1 khusus bagian akhir dan dimulai pada halaman baru.
- Heading 2: `A.`, `B.`, `C.`, dst.; rata kiri pada margin utama (left indent 0 cm).
- Heading 3: `1.`, `2.`, `3.`, dst.; left indent sekitar 0,63 cm.
- Heading 4: `a.`, `b.`, `c.`, dst.; left indent sekitar 1,27 cm.
- Isi paragraf tidak mengikuti indent heading; isi memakai margin utama dengan first-line indent 1,27 cm dan Justify.
- Level `1.` dan `a.` hanya dipakai jika memang dibutuhkan.

Penomoran halaman default Makalah:

- Cover: tanpa nomor tampil.
- Kata Pengantar dan Daftar Isi: Romawi kecil mulai `i`.
- BAB I: reset ke angka Arab `1`.
- Angka Arab berlanjut sampai Daftar Pustaka.

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

## Referensi awal fallback

Referensi ini dipakai sebagai dasar awal, bukan sebagai pengganti pedoman institusi:

1. UPN Veteran Jawa Timur, *Thesis Writing Guidelines 2025*: Times New Roman 12, margin kiri 4 cm dan sisi lain 3 cm, first-line indent 1 tab = 1,27 cm.
   https://agrotek.upnjatim.ac.id/wp-content/uploads/2025/09/Thesis-Writing-Guidelines-2025_.pdf
2. Fakultas Ushuluddin dan Pemikiran Islam UIN Sunan Kalijaga, *Pedoman Penulisan Proposal dan Skripsi*: spasi 1,5, first-line indent 1,27 cm, seluruh naskah justify, serta contoh hierarki `BAB -> A. -> 1. -> a.`.
   https://ushuluddin.uin-suka.ac.id/media/dokumen_akademik/05_20221207_4.%20Skripsi%20Final.pdf
3. Program Studi Kimia UIN Sunan Kalijaga, *Pedoman Penulisan Skripsi*: BAB sebagai Heading 1, `A./B./C.` sebagai Heading 2, dan penomoran bertingkat dengan pengaturan indentasi.
   https://kimia.uin-suka.ac.id/media/dokumen_akademik/63_20180806_PEDOMAN%20PENULISAN%20SKRIPSI.pdf

## Aturan stabilitas

Skill ini adalah **fallback**. Jangan diam-diam mengubah format yang sudah disepakati pengguna atau format resmi institusi hanya karena referensi lain terlihat lebih umum.