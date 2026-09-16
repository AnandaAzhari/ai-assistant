# Document Format Policy — Makalah

Dokumen ini adalah **aturan format default resmi** untuk Document Agent Taqi AI.
AI tidak boleh mengubah struktur, hierarki penomoran, cara menghitung target halaman, format nomor halaman, atau tata letak daftar pustaka hanya karena preferensi model.

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

- Jika pelanggan hanya mengatakan `8 halaman`, artikan sebagai target **8 halaman setelah cover**. Cover tidak dihitung ke target.
- Secara default halaman setelah cover mencakup halaman awal bernomor Romawi, isi BAB I–BAB III, dan Daftar Pustaka.
- Jika pelanggan secara jelas mengatakan `8 halaman isi`, target 8 halaman hanya berlaku pada isi utama BAB I–BAB III; halaman awal dan Daftar Pustaka berada di luar target itu.
- Target adalah kisaran praktis, bukan alasan untuk menambah subbab yang tidak perlu.
- Untuk target sampai 8 halaman setelah cover, buat kerangka ringkas: BAB II umumnya cukup 3–4 subbab utama. Tambahkan `x.x.x` hanya bila benar-benar membantu struktur.
- Untuk target 9–12 halaman setelah cover, BAB II umumnya 4–6 subbab utama.
- Hindari kerangka terlalu rinci yang membuat dokumen melewati target halaman.
- Setelah render Word/PDF tersedia, jumlah halaman final setelah cover harus menjadi acuan pemeriksaan panjang dokumen.

## Nomor halaman

Default penomoran halaman makalah:

- Cover: **tidak menampilkan nomor halaman** dan tidak dihitung ke target halaman.
- Bagian awal setelah cover, seperti Kata Pengantar dan Daftar Isi: gunakan angka Romawi kecil `i`, `ii`, `iii`, dan seterusnya, dimulai dari `i`.
- Ketika masuk `BAB I PENDAHULUAN`, nomor halaman di-reset dan dimulai lagi dari angka Arab `1`.
- Nomor Arab kemudian berlanjut terus melalui BAB II, BAB III, sampai Daftar Pustaka. Jangan reset lagi pada Daftar Pustaka.
- Nomor halaman diletakkan konsisten di footer tengah, kecuali instruksi resmi menentukan posisi lain.
- Jika guru/dosen/sekolah/kampus memberi aturan nomor halaman yang berbeda, ikuti aturan resmi tersebut.

## Bahasa dan isi

- Bahasa Indonesia formal, jelas, dan mudah dipahami sesuai jenjang siswa/mahasiswa.
- Jangan memakai istilah teknis jika ada kata yang lebih sederhana, kecuali istilah itu memang bagian materi.
- Jangan mengarang sumber, DOI, nama penulis, data penelitian, atau kutipan.
- Sumber hanya boleh berasal dari Source Registry yang sudah diverifikasi.

## Catatan kaki dan daftar pustaka

- Marker sumber internal `[[R1]]`, `[[R2]]`, dst. hanya untuk mesin dan tidak boleh terlihat pada dokumen final.
- Citation Engine mengubah marker menjadi catatan kaki Word asli.
- Daftar pustaka hanya memuat sumber yang benar-benar digunakan dan diurutkan alfabetis.
- Judul `DAFTAR PUSTAKA` berada di tengah dan tebal.
- Setiap entri daftar pustaka rata kiri dengan **hanging indent 1,27 cm**.
- Gunakan spasi tunggal di dalam satu entri dan jarak ringan antar-entri agar rapi dan mudah dibaca.
- Jangan memakai justify pada entri daftar pustaka karena dapat membuat jarak antarkata melebar.
- Nama jurnal dicetak miring untuk artikel jurnal; judul buku/sumber non-jurnal dicetak miring sesuai tipe sumber.
- Tata letak daftar pustaka ditangani Citation Engine secara deterministik dan tidak boleh diubah model AI secara sepihak.

## Prinsip stabilitas

Document Agent boleh menyesuaikan **isi** dengan topik, jenjang, dan instruksi pelanggan, tetapi tidak boleh mengubah aturan format default ini secara sepihak. Jika ada instruksi khusus dari guru/dosen/sekolah/kampus, sebutkan bahwa struktur disesuaikan karena instruksi tersebut.