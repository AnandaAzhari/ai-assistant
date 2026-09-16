# Document Format Policy — Makalah

Dokumen ini adalah **aturan format default resmi untuk Makalah** pada Document Agent Taqi AI.
AI tidak boleh mengubah struktur, hierarki penomoran, tata letak daftar pustaka, atau cara menghitung target halaman hanya karena preferensi model.

## Urutan prioritas aturan

1. Instruksi/rubrik/template yang diberikan guru, dosen, sekolah, kampus, atau pelanggan.
2. Aturan khusus instansi yang diberikan pelanggan.
3. Policy default pada file ini dan `document_type_structure_policy.md`.
4. Referensi fallback pada `skills/document_academic/SKILL.md`.

Jika aturan tingkat 1 atau 2 bertentangan dengan policy ini, ikuti aturan yang lebih tinggi **hanya pada bagian yang bertentangan**. Bagian lain tetap mengikuti policy ini.

## Struktur default Makalah

Default Makalah Taqi AI:

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
    - 1. Rincian bila memang diperlukan
      - a. Rincian lebih lanjut bila memang diperlukan
      - b. Rincian lebih lanjut bila memang diperlukan
  - C. Subbagian sesuai topik
- BAB III — PENUTUP
  - A. Kesimpulan
  - B. Saran
- DAFTAR PUSTAKA

Jumlah dan nama subbagian boleh menyesuaikan topik dan kebutuhan tugas. Jangan memaksakan tingkat `1.` atau `a.` jika pembahasan sudah jelas pada tingkat `A.`.

## Hierarki penomoran dan indentasi

Default hierarki Makalah:

- Tingkat utama / **Heading 1**: `BAB I`, `BAB II`, `BAB III`, dst., serta `DAFTAR PUSTAKA` sebagai bagian akhir setingkat BAB.
- Tingkat kedua / **Heading 2**: `A.`, `B.`, `C.`, `D.`, dst.
- Tingkat ketiga / **Heading 3** bila diperlukan: `1.`, `2.`, `3.`, dst.
- Tingkat keempat / **Heading 4** bila diperlukan: `a.`, `b.`, `c.`, dst.
- Jadi pola default resmi Makalah adalah: **`BAB I → A. → 1. → a.`**
- Huruf seperti `C.`, `D.`, atau `M.` pada Makalah tetap harus dibaca sebagai **subbagian Heading 2**, bukan dianggap angka Romawi untuk Heading 1. Heading 1 BAB hanya berasal dari label `BAB ...`; `DAFTAR PUSTAKA` juga diperlakukan sebagai Heading 1 khusus bagian akhir.
- Jangan memakai `BAB I → 1.1 → 1.1.1` sebagai default Makalah.
- Jangan memakai `I. → A. → 1. → a.` sebagai default Makalah.
- Heading BAB ditampilkan terpisah, misalnya `BAB I` pada satu baris dan `PENDAHULUAN` pada baris berikutnya, rata tengah dan tebal.
- Heading memakai satu spasi normal antara penanda dan judul; jangan menambahkan TAB acak.

Fallback indent Word saat **tidak ada arahan resmi**:

- Heading 1 (`BAB ...` / `DAFTAR PUSTAKA`): rata tengah, left indent **0 cm**.
- Heading 2 (`A.`, `B.`, `C.`): rata kiri, left indent **0 cm**.
- Heading 3 (`1.`, `2.`, `3.`): rata kiri, left indent sekitar **0,63 cm**.
- Heading 4 (`a.`, `b.`, `c.`): rata kiri, left indent sekitar **1,27 cm**.
- Isi paragraf kembali memakai margin utama dan **tidak mewarisi left indent heading**.
- Paragraf isi memakai **first-line indent sekitar 1,25–1,27 cm**. Engine memakai 1,27 cm / 0,5 inci sebagai default praktis; jika pedoman institusi menetapkan 1,25 cm, ikuti pedoman tersebut.
- **Semua paragraf isi utama wajib memakai Justify / rata kiri-kanan**, bukan rata kiri biasa, kecuali pedoman resmi instansi menentukan lain.
- Teks utama memakai **spasi 1,5** sebagai fallback bila tidak ada arahan lain.
- Justify dan first-line indent harus diterapkan sebagai properti paragraf Word, bukan spasi atau karakter TAB manual.
- Bullet `•` tidak boleh menggantikan heading terstruktur.
- Bullet atau numbered list hanya dipakai di dalam isi jika memang berupa daftar, bukan sebagai pengganti hierarki heading.
- Pada tampilan kerangka untuk pelanggan, tampilkan struktur heading saja tanpa ringkasan paragraf di bawah setiap heading.

## Kualitas paragraf

Jika tidak ada pedoman resmi yang mengatur lain:

- Satu paragraf sebaiknya membahas **satu gagasan pokok**.
- Paragraf harus logis, runtut, koheren, dan mendukung argumen/pembahasan secara sistematis.
- Sebagai panduan kualitas, paragraf umumnya sekitar **3–5 kalimat** bila isi memungkinkan. Ini bukan batas keras; paragraf boleh lebih pendek atau lebih panjang jika struktur gagasannya memang menuntut demikian.
- Hindari paragraf satu kalimat tanpa alasan yang jelas.
- Hindari paragraf sangat panjang yang mencampur beberapa gagasan pokok sekaligus.
- Jangan memecah paragraf hanya untuk mengejar jumlah halaman.

## Pergantian Heading 1 / bagian utama

- `BAB I` dimulai pada halaman baru setelah Daftar Isi.
- **Setiap Heading 1 berikutnya wajib dimulai pada halaman baru.** Ini mencakup `BAB II`, `BAB III`, BAB berikutnya, dan `DAFTAR PUSTAKA`.
- `DAFTAR PUSTAKA` tidak boleh menempel di bawah isi `BAB III` pada halaman yang sama; bagian ini harus dimulai pada halaman baru sendiri.
- Pergantian Heading 1 memakai page break biasa, bukan reset nomor halaman.
- Nomor halaman Arab tetap berlanjut dari BAB I sampai Daftar Pustaka.

## Target jumlah halaman

- Jika pelanggan hanya mengatakan `8 halaman`, artikan sebagai target sekitar **8 halaman setelah cover**. Cover tidak dihitung.
- Kata Pengantar, Daftar Isi, BAB I–III, dan Daftar Pustaka ikut dalam target tersebut kecuali pelanggan/guru/dosen menjelaskan aturan lain.
- Jika pelanggan secara jelas mengatakan `8 halaman isi`, target berlaku khusus isi utama dan halaman awal/Daftar Pustaka tidak dihitung.
- Target adalah kisaran praktis; jangan menambah subbagian hanya untuk memperpanjang dokumen.
- Untuk target sampai 8 halaman setelah cover, utamakan struktur ringkas. Tingkat `1.` dan `a.` hanya digunakan bila benar-benar membantu struktur.
- Setelah render Word/PDF tersedia, jumlah halaman final menjadi acuan pemeriksaan panjang dokumen.

## Penomoran halaman

Default penomoran halaman:

- **Cover tidak menampilkan nomor halaman.**
- Bagian awal setelah cover, termasuk Kata Pengantar dan Daftar Isi, memakai angka Romawi kecil `i, ii, iii, ...` dimulai dari `i`.
- Saat masuk `BAB I`, penomoran halaman di-reset dan halaman pertama BAB I harus tampil sebagai **`1`**.
- Angka Arab kemudian berlanjut terus melalui BAB II, BAB III, sampai Daftar Pustaka; jangan di-reset lagi.
- Nomor halaman default ditempatkan di tengah bawah/footer kecuali instruksi resmi menentukan posisi lain.
- DOCX dan PDF final wajib memakai penomoran yang sama.

## Daftar isi

- Daftar isi diperbarui setelah struktur, nomor halaman, catatan kaki, dan Daftar Pustaka final selesai.
- Entri `BAB I`, `BAB II`, `BAB III`, dan `DAFTAR PUSTAKA` berada pada tingkat utama yang sama.
- Level `A.`, `B.`, `C.` berada satu tingkat di bawah BAB.
- Level `1.`, `2.`, `3.` berada satu tingkat lagi di bawah `A.` jika memang ditampilkan.
- Level `a.`, `b.`, `c.` berada satu tingkat lagi jika benar-benar diperlukan.
- Nomor halaman pada daftar isi harus mengikuti nomor final dokumen.

## Bahasa dan isi

- Bahasa Indonesia formal, jelas, dan mudah dipahami sesuai jenjang siswa/mahasiswa.
- Jangan memakai istilah teknis jika ada kata yang lebih sederhana, kecuali istilah itu memang bagian materi.
- Jangan mengarang sumber, DOI, nama penulis, data penelitian, atau kutipan.
- Sumber hanya boleh berasal dari Source Registry yang sudah diverifikasi.

## Catatan kaki dan daftar pustaka

- Marker internal `[[R1]]`, `[[R2]]`, dst. hanya untuk mesin dan tidak boleh terlihat pada dokumen final.
- Citation Engine mengubah marker menjadi catatan kaki Word asli.
- Daftar pustaka hanya memuat sumber yang benar-benar digunakan.
- Judul bagian ditulis **`DAFTAR PUSTAKA`** sebagai bagian akhir setingkat BAB / Heading 1, tetapi tidak diberi label `BAB IV` atau nomor Romawi/huruf tambahan kecuali instruksi resmi meminta begitu.
- `DAFTAR PUSTAKA` wajib dimulai pada halaman baru dan nomor halaman Arab tetap melanjutkan halaman sebelumnya.
- Entri daftar pustaka disusun alfabetis, rata kiri, memakai hanging indent sekitar **1,25–1,27 cm**, spasi tunggal, dan jarak antar-entri yang rapi.
- Nama jurnal untuk artikel atau judul buku/sumber non-jurnal dicetak miring sesuai format engine.
- Tata letak daftar pustaka mengikuti format engine yang telah ditetapkan; model AI tidak boleh mengubahnya sendiri.

## Prinsip stabilitas

Document Agent boleh menyesuaikan **isi** dengan topik, jenjang, dan instruksi pelanggan, tetapi tidak boleh mengubah pola default **`BAB I → A. → 1. → a.`** secara sepihak. Jika ada instruksi khusus dari guru/dosen/sekolah/kampus, struktur hanya disesuaikan pada bagian yang diminta. Jika tidak ada arahan resmi, gunakan fallback aktif pada `skills/document_academic/SKILL.md`.