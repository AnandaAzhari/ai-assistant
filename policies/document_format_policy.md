# Document Format Policy — Makalah

Dokumen ini adalah **aturan format default resmi untuk Makalah** pada Document Agent Taqi AI.
AI tidak boleh mengubah struktur, hierarki penomoran, tata letak daftar pustaka, atau cara menghitung target halaman hanya karena preferensi model.

## Urutan prioritas aturan

1. Instruksi/rubrik/template yang diberikan guru, dosen, sekolah, kampus, atau pelanggan.
2. Aturan khusus instansi yang diberikan pelanggan.
3. Policy default pada file ini dan `document_type_structure_policy.md`.

Jika aturan tingkat 1 atau 2 bertentangan dengan policy ini, ikuti aturan yang lebih tinggi **hanya pada bagian yang bertentangan**. Bagian lain tetap mengikuti policy ini.

## Struktur default makalah

Default Makalah mengikuti pola referensi pelanggan:

- Cover
- Kata Pengantar
- Daftar Isi
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

Nama bagian boleh menyesuaikan topik dan kebutuhan tugas, tetapi pola penomoran default makalah harus tetap konsisten.

## Hierarki penomoran dan indentasi

Default hierarki Makalah:

- Tingkat utama: `I.`, `II.`, `III.`, `IV.`, dst.
- Tingkat kedua: `A.`, `B.`, `C.`, dst.
- Tingkat ketiga: `1.`, `2.`, `3.`, dst.
- Tingkat keempat bila perlu: `a.`, `b.`, `c.`, dst.
- Jangan memakai pola `BAB I → 1.1 → 1.1.1` sebagai default makalah. Pola itu dipakai untuk jenis dokumen lain atau jika instruksi resmi memintanya.
- Judul heading dimulai dari margin kiri sesuai levelnya dan tidak memakai TAB acak di antara nomor dan judul.
- Paragraf isi setelah heading secara default memakai first-line indent sekitar **1,25 cm**.
- Bullet `•` tidak boleh menggantikan heading terstruktur.
- Bullet/numbered list boleh dipakai hanya di dalam isi untuk daftar contoh, langkah, manfaat, jenis, atau poin lain.
- Pada **tampilan kerangka untuk pelanggan**, tampilkan struktur heading saja; jangan menambahkan ringkasan paragraf di bawah setiap heading.

## Target jumlah halaman

- Jika pelanggan hanya mengatakan `8 halaman`, artikan sebagai target sekitar **8 halaman setelah cover**. Cover tidak dihitung.
- Halaman setelah cover seperti Kata Pengantar, Daftar Isi, isi utama, dan Daftar Pustaka ikut dalam target tersebut kecuali pelanggan/guru/dosen menjelaskan aturan lain.
- Jika pelanggan secara jelas mengatakan `8 halaman isi`, target berlaku khusus isi utama dan halaman awal/daftar pustaka tidak dihitung.
- Target adalah kisaran praktis, bukan alasan untuk membuat tingkat heading terlalu dalam atau menambah bagian yang tidak perlu.
- Untuk target sampai 8 halaman setelah cover, gunakan struktur yang ringkas dan hanya pakai tingkat `1.` atau `a.` jika benar-benar diperlukan.
- Setelah render Word/PDF tersedia, jumlah halaman final harus menjadi acuan pemeriksaan panjang dokumen.

## Penomoran halaman

Default penomoran halaman:

- **Cover tidak menampilkan nomor halaman.**
- Bagian awal setelah cover, termasuk Kata Pengantar dan Daftar Isi, memakai angka Romawi kecil `i, ii, iii, ...` dimulai dari `i`.
- Saat masuk bagian isi utama `I. Pendahuluan`, penomoran halaman di-reset dan **halaman pertama isi utama harus tampil sebagai `1`**.
- Penomoran Arab kemudian berlanjut terus sampai bagian akhir termasuk Daftar Pustaka; jangan di-reset lagi.
- Nomor halaman default ditempatkan di tengah bawah/footer agar konsisten, kecuali instruksi guru/dosen/instansi menentukan posisi lain.
- DOCX dan PDF final harus memakai penomoran yang sama.

## Daftar isi

- Daftar isi diperbarui setelah struktur, nomor halaman, catatan kaki, dan Daftar Pustaka final selesai.
- Entri level utama seperti `I. Pendahuluan`, `II. Tinjauan Pustaka`, `III. Metodologi Penelitian`, dan `VI. Daftar Pustaka` harus berada pada tingkat TOC yang sama.
- Level `A.`, `B.`, `C.` berada satu tingkat di bawah bagian utama.
- Level `1.`, `2.`, `3.` berada satu tingkat lagi di bawahnya jika memang ditampilkan di daftar isi.
- Nomor halaman pada daftar isi harus mengikuti nomor final dokumen, bukan nomor fisik sebelum section numbering diterapkan.

## Bahasa dan isi

- Bahasa Indonesia formal, jelas, dan mudah dipahami sesuai jenjang siswa/mahasiswa.
- Jangan memakai istilah teknis jika ada kata yang lebih sederhana, kecuali istilah itu memang bagian materi.
- Jangan mengarang sumber, DOI, nama penulis, data penelitian, atau kutipan.
- Sumber hanya boleh berasal dari Source Registry yang sudah diverifikasi.

## Catatan kaki dan daftar pustaka

- Marker sumber internal `[[R1]]`, `[[R2]]`, dst. hanya untuk mesin dan tidak boleh terlihat pada dokumen final.
- Citation Engine mengubah marker menjadi catatan kaki Word asli.
- Daftar pustaka hanya memuat sumber yang benar-benar digunakan.
- Judul bagian Daftar Pustaka mengikuti hierarki Makalah, yaitu `VI. Daftar Pustaka`, kecuali instruksi resmi meminta bentuk lain.
- Entri daftar pustaka disusun alfabetis, rata kiri, memakai hanging indent sekitar **1,27 cm**, spasi tunggal, dan jarak antar-entri yang rapi.
- Nama jurnal untuk artikel atau judul buku/sumber non-jurnal dicetak miring sesuai format engine.
- Tata letak daftar pustaka mengikuti format engine yang telah ditetapkan; jangan diubah model AI.

## Prinsip stabilitas

Document Agent boleh menyesuaikan **isi** dengan topik, jenjang, dan instruksi pelanggan, tetapi tidak boleh mengubah aturan format default ini secara sepihak. Jika ada instruksi khusus dari guru/dosen/sekolah/kampus, struktur boleh disesuaikan hanya pada bagian yang diminta.