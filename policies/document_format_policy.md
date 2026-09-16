# Document Format Policy — Makalah

Dokumen ini adalah **aturan format default resmi** untuk Document Agent Taqi AI.
AI tidak boleh mengubah struktur, hierarki penomoran, tata letak daftar pustaka, atau cara menghitung target halaman hanya karena preferensi model.

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

## Hierarki penomoran dan indentasi

- BAB: `BAB I`, `BAB II`, `BAB III`.
- Subbab tingkat 2: `1.1`, `1.2`, `2.1`, `2.2`, dst.
- Jika subbab memiliki subbagian sebagai heading, gunakan tingkat 3: `1.1.1`, `1.1.2`, `2.1.1`, dst.
- Judul subbab dan anak subbab dimulai dari margin kiri. **Jangan memakai TAB atau indent tambahan sebelum/di antara nomor heading dan judul.** Gunakan satu spasi normal, misalnya `1.1 Latar Belakang`.
- Paragraf isi setelah heading secara default memakai first-line indent sekitar **1,25 cm**. Ini berbeda dari heading: heading tetap rata kiri tanpa tab.
- Jangan memakai bullet `•` sebagai pengganti judul subbagian.
- Bullet/numbered list boleh dipakai **hanya di dalam isi** untuk daftar contoh, langkah, manfaat, jenis, atau poin lain; bukan untuk mengganti hierarki heading.
- Default maksimum sampai tingkat `x.x.x`. Jangan membuat tingkat lebih dalam kecuali instruksi resmi memintanya.
- Pada **tampilan kerangka untuk pelanggan**, tampilkan struktur heading saja. Jangan menambahkan bullet berisi ringkasan paragraf di bawah setiap heading karena itu membuat kerangka terlihat seperti isi makalah dan membingungkan pelanggan.

## Target jumlah halaman

- Jika pelanggan hanya mengatakan `8 halaman`, artikan sebagai target sekitar **8 halaman setelah cover**. Cover tidak dihitung.
- Halaman setelah cover seperti Kata Pengantar, Daftar Isi, BAB I–III, dan Daftar Pustaka ikut dalam target tersebut kecuali pelanggan/guru/dosen menjelaskan aturan lain.
- Jika pelanggan secara jelas mengatakan `8 halaman isi`, target berlaku khusus isi utama BAB I–III dan halaman awal/daftar pustaka tidak dihitung.
- Target adalah kisaran praktis, bukan alasan untuk menambah subbab yang tidak perlu.
- Untuk target sampai 8 halaman setelah cover, buat kerangka ringkas: BAB II umumnya cukup 3–4 subbab utama. Tambahkan `x.x.x` hanya bila benar-benar membantu struktur.
- Untuk target 9–12 halaman setelah cover, BAB II umumnya 4–6 subbab utama.
- Hindari outline terlalu rinci yang membuat dokumen melewati target halaman.
- Setelah render Word/PDF tersedia, jumlah halaman final harus menjadi acuan pemeriksaan panjang dokumen.

## Penomoran halaman

Default penomoran halaman:

- **Cover tidak menampilkan nomor halaman.**
- Bagian awal setelah cover, termasuk Kata Pengantar dan Daftar Isi, memakai angka Romawi kecil `i, ii, iii, ...` dimulai dari `i`.
- Saat masuk `BAB I`, penomoran di-reset dan **halaman pertama BAB I harus tampil sebagai `1`**, bukan melanjutkan hitungan fisik dokumen.
- Penomoran Arab kemudian berlanjut terus sampai bagian akhir termasuk Daftar Pustaka; jangan di-reset lagi.
- Nomor halaman default ditempatkan di tengah bawah/footer agar konsisten, kecuali instruksi guru/dosen/instansi menentukan posisi lain.
- DOCX dan PDF final harus memakai penomoran yang sama.

## Daftar isi

- Daftar isi diperbarui setelah struktur, nomor halaman, catatan kaki, dan Daftar Pustaka final selesai.
- Entri level utama seperti `BAB I`, `BAB II`, `BAB III`, dan `DAFTAR PUSTAKA` harus rata kiri pada tingkat yang sama.
- `DAFTAR PUSTAKA` tidak boleh tampil terpusat atau memiliki indent yang berbeda dari BAB pada daftar isi.
- Subbab `1.1`, `1.2`, `2.1`, dan seterusnya boleh memiliki indent konsisten sebagai level kedua.
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
- Judul `DAFTAR PUSTAKA` ditulis di tengah dan tebal.
- Entri daftar pustaka disusun alfabetis, rata kiri, memakai hanging indent sekitar **1,27 cm**, spasi tunggal, dan jarak antar-entri yang rapi.
- Nama jurnal untuk artikel atau judul buku/sumber non-jurnal dicetak miring sesuai format engine.
- Tata letak daftar pustaka mengikuti format engine yang telah ditetapkan; jangan diubah model AI.

## Prinsip stabilitas

Document Agent boleh menyesuaikan **isi** dengan topik, jenjang, dan instruksi pelanggan, tetapi tidak boleh mengubah aturan format default ini secara sepihak. Jika ada instruksi khusus dari guru/dosen/sekolah/kampus, sebutkan bahwa struktur disesuaikan karena instruksi tersebut.