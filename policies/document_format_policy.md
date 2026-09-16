# Document Format Policy — Makalah

Dokumen ini adalah **aturan format default resmi** untuk Document Agent Taqi AI.
AI tidak boleh mengubah struktur, hierarki penomoran, atau cara menghitung target halaman hanya karena preferensi model.

## Urutan prioritas aturan

1. Instruksi/rubrik/template yang diberikan guru, dosen, sekolah, kampus, atau pelanggan.
2. Aturan khusus instansi yang diberikan pelanggan.
3. Policy default pada file ini.

Jika aturan tingkat 1 atau 2 bertentangan dengan policy ini, ikuti aturan yang lebih tinggi **hanya pada bagian yang bertentangan**. Bagian lain tetap mengikuti policy ini.

## Struktur default makalah

Urutan default:

- Cover
- Kata Pengantar
- Daftar Isi
- BAB I PENDAHULUAN
  - 1.1 Latar Belakang
  - 1.2 Rumusan Masalah
  - 1.3 Tujuan Penulisan
  - 1.4 Manfaat Penulisan
  - 1.5 Batasan Masalah hanya bila memang diperlukan
- BAB II PEMBAHASAN
  - subbab 2.1, 2.2, 2.3, dan seterusnya sesuai topik
- BAB III PENUTUP
  - 3.1 Kesimpulan
  - 3.2 Saran
- Daftar Pustaka

Jangan menambah BAB atau bagian lain kecuali memang dibutuhkan topik atau diperintahkan guru/dosen/instansi.

## Hierarki penomoran

- BAB: `BAB I`, `BAB II`, `BAB III`.
- Subbab tingkat 2: `1.1`, `1.2`, `2.1`, `2.2`, dst.
- Jika subbab memiliki subbagian sebagai heading, gunakan tingkat 3: `1.1.1`, `1.1.2`, `2.1.1`, dst.
- Jangan memakai bullet `•` sebagai pengganti judul subbagian.
- Bullet/numbered list boleh dipakai **hanya di dalam isi** untuk daftar contoh, langkah, manfaat, jenis, atau poin lain; bukan untuk mengganti hierarki heading.
- Default maksimum sampai tingkat `x.x.x`. Jangan membuat tingkat lebih dalam kecuali instruksi resmi memintanya.
- Pada **tampilan kerangka untuk pelanggan**, tampilkan struktur heading saja. Jangan menambahkan bullet berisi ringkasan paragraf di bawah setiap heading karena itu membuat kerangka terlihat seperti isi makalah dan membingungkan pelanggan.

## Target jumlah halaman

- Jika pelanggan hanya mengatakan `8 halaman`, artikan sebagai target **total dokumen final**, bukan 8 halaman isi ditambah halaman awal.
- Jika pelanggan secara jelas mengatakan `8 halaman isi`, barulah target berlaku khusus isi utama.
- Target adalah kisaran praktis, bukan alasan untuk menambah subbab yang tidak perlu.
- Untuk target sampai 8 halaman total, buat kerangka ringkas: BAB II umumnya cukup 3–4 subbab utama. Tambahkan `x.x.x` hanya bila benar-benar membantu struktur.
- Untuk target 9–12 halaman total, BAB II umumnya 4–6 subbab utama.
- Hindari outline terlalu rinci yang membuat dokumen melewati target halaman.
- Setelah render Word/PDF tersedia, jumlah halaman final harus menjadi acuan pemeriksaan panjang dokumen.

## Bahasa dan isi

- Bahasa Indonesia formal, jelas, dan mudah dipahami sesuai jenjang siswa/mahasiswa.
- Jangan memakai istilah teknis jika ada kata yang lebih sederhana, kecuali istilah itu memang bagian materi.
- Jangan mengarang sumber, DOI, nama penulis, data penelitian, atau kutipan.
- Sumber hanya boleh berasal dari Source Registry yang sudah diverifikasi.

## Catatan kaki dan daftar pustaka

- Marker sumber internal `[[R1]]`, `[[R2]]`, dst. hanya untuk mesin dan tidak boleh terlihat pada dokumen final.
- Citation Engine mengubah marker menjadi catatan kaki Word asli.
- Daftar pustaka hanya memuat sumber yang benar-benar digunakan.
- Tata letak daftar pustaka mengikuti format engine yang telah ditetapkan; jangan diubah model AI.

## Prinsip stabilitas

Document Agent boleh menyesuaikan **isi** dengan topik, jenjang, dan instruksi pelanggan, tetapi tidak boleh mengubah aturan format default ini secara sepihak. Jika ada instruksi khusus dari guru/dosen/sekolah/kampus, sebutkan bahwa struktur disesuaikan karena instruksi tersebut.