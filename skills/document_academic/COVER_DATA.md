# Cover Data Skill — Makalah

Dokumen ini menjadi referensi aktif untuk pengumpulan dan pembaruan data cover Makalah.

## Prinsip utama

Data cover tidak dianggap tertutup hanya karena data wajib sudah lengkap. Pelanggan tetap boleh menambahkan, mengganti, atau melengkapi data cover selama order/sesi masih aktif dan file final belum dikunci.

Contoh data yang boleh ditambahkan belakangan:

- nama sekolah/kampus/universitas;
- tahun ajaran/tahun akademik;
- nama guru/dosen/pembimbing/pengampu;
- nama atau nomor kelompok;
- anggota kelompok;
- data opsional lain yang memang dipakai pada cover.

## Bahasa pelanggan

Utamakan interpretasi AI dengan konteks percakapan, termasuk untuk pola jelas seperti:

- `Nama Sekolah SMK Negeri 2 Padangsidimpuan`
- `sekolah saya SMK Negeri 2 Padangsidimpuan`
- `tahun ajaran 2026/2027`
- `Nama Guru Purnama Sari`
- `dosen pengampu Budi Santoso`
- `Purnama Sari itu nama gurunya`
- `Nama Sekolah: SMK Negeri 2 Padangsidimpuan`
- `Nama gurunya bukan Purnama Sari, ganti menjadi Nurhayati.`

Pelanggan tidak wajib memakai tanda titik dua atau format formulir tertentu.

Interpreter `app/document_intake.py` membaca `CONVERSATION.md` dan menerima data cover sejak pesan pertama. Parser lokal hanya digunakan ketika provider gagal atau output tidak valid. Hasil AI yang valid tidak ditambal ulang oleh parser.

## Context-aware slot filling

Pengumpulan cover memakai konsep **slot filling**, bukan formulir berurutan.

- Setiap data cover adalah slot/field terpisah.
- Pertanyaan Nara hanya menunjukkan data wajib berikutnya yang masih kurang; pelanggan **tidak wajib menjawab sesuai urutan pertanyaan**.
- Pelanggan boleh mengirim data lain lebih dulu, satu per satu, atau beberapa sekaligus.
- Data yang sudah terbaca tetap disimpan ketika Nara kembali menanyakan field wajib yang belum lengkap.
- Bentuk nilai yang khas boleh dikenali walaupun tidak memakai label. Contoh: `2026/2027` dikenali sebagai tahun ajaran dan `SMK Negeri 2 Padangsidimpuan` dikenali sebagai sekolah.
- Jawaban nama polos hanya boleh langsung dipetakan ketika konteks pertanyaan aktif aman. Contoh: setelah Nara bertanya `Siapa nama penyusun?`, jawaban `Ananda Azhari Batubara` langsung menjadi `author_name`.
- Jika nama polos muncul tanpa konteks aman, jangan menebak. Minta klarifikasi apakah nama tersebut adalah nama penyusun/siswa, guru/dosen, atau anggota kelompok.
- AI mengusulkan klarifikasi singkat; field ambigu tidak diisi.

Contoh alur tidak berurutan:

1. Nara bertanya: `Tugas ini individu atau kelompok?`
2. Pelanggan menjawab: `2026/2027`
3. Sistem menyimpan tahun ajaran, lalu tetap menanyakan individu/kelompok.
4. Pelanggan: `SMK Negeri 2 Padangsidimpuan`
5. Sistem menyimpan sekolah, lalu tetap menanyakan individu/kelompok.
6. Pelanggan: `individu`
7. Nara meminta nama penyusun.
8. Pelanggan cukup menjawab: `Ananda Azhari Batubara`.

Hasil akhirnya tetap konsisten walaupun urutan jawaban berbeda dari urutan pertanyaan.

## Loop data cover

Alur yang diinginkan:

1. Kumpulkan data cover wajib secukupnya.
2. Setelah data wajib lengkap, lanjutkan order ke tahap siap membuat isi.
3. Jangan mengunci data cover opsional.
4. Setiap pesan baru tetap boleh diperiksa untuk pembaruan data cover.
5. Nilai `Tidak dicantumkan` bukan keputusan permanen; jika pelanggan kemudian memberi nilai nyata, nilai baru menggantikannya.
6. Jika pelanggan mengoreksi nilai lama, gunakan nilai terbaru untuk file final.
7. Jika ada perubahan yang berhasil dibaca, balas dengan konfirmasi nilai yang berubah agar pelanggan tahu datanya benar-benar tersimpan.
8. Loop tetap terbuka sampai pelanggan memilih melanjutkan proses atau file final dikunci.

Contoh:

- awal: `Sekolah/kampus: Tidak dicantumkan`
- kemudian pelanggan: `Nama sekolah SMK Negeri 2 Padangsidimpuan`
- hasil terbaru: `Sekolah/kampus: SMK Negeri 2 Padangsidimpuan`

Contoh koreksi:

- awal: `Guru/dosen: Purnama Sari`
- pelanggan: `Nama gurunya bukan Purnama Sari, ganti menjadi Nurhayati.`
- hasil terbaru: `Guru/dosen: Nurhayati`

## UX konfirmasi

Setelah pembaruan berhasil, respons sebaiknya ringkas dan eksplisit, misalnya:

`Data cover berhasil diperbarui:`

- `Sekolah/kampus: SMK Negeri 2 Padangsidimpuan`
- `Tahun ajaran: 2026/2027`
- `Guru/dosen: Purnama Sari`

Lalu jelaskan bahwa pelanggan tetap boleh menambahkan atau mengubah data cover lain sebelum file final dibuat. Pelanggan tidak perlu memakai slash command; bahasa natural seperti `lanjutkan` atau `sudah cukup` boleh dipakai untuk meneruskan proses.

Jangan membalas hanya dengan `Semua data utama sudah siap` ketika pesan pelanggan sebenarnya baru saja mengubah data cover, karena pelanggan perlu melihat konfirmasi nilai terbaru.

Jika input ambigu, respons harus menjelaskan ambiguitas secara spesifik, misalnya:

`Saya membaca Purnama Sari sebagai nama, tetapi belum aman menentukan untuk siapa. Apakah ini nama penyusun/siswa, nama guru/dosen, atau anggota kelompok?`

## Prioritas

1. Pedoman resmi guru/dosen/sekolah/kampus.
2. Koreksi terbaru pelanggan pada order yang sama.
3. Data cover yang sebelumnya tersimpan.
4. Fallback Taqi AI.

Jangan mengubah data cover order lain. Data harus tetap scoped per sesi/order.

## Implementasi

- `app/document_intake.py`: interpretasi AI, schema patch dan intent, evidence dari pesan terbaru.
- `app/document_agent.py`: menerapkan patch valid, menentukan fase, mengonfirmasi perubahan.
- `app/document_cover.py`: schema cover, kelengkapan, pertanyaan wajib, dan parser fallback.
- `app/document_session.py`: menyimpan sesi Web Admin ke SQLite, terpisah per scope.

Koreksi cover setelah draft memperbarui metadata `MakalahSpec`; Word/PDF lama dibatalkan
agar hasil berikutnya menggunakan data terbaru. Koreksi kebutuhan akademik membatalkan
draft/kerangka lama dan meminta persetujuan kerangka baru. Pembaruan field tidak boleh
menimpa field lain yang tidak disebut. Reset sesi melalui `/makalah_baru` juga disimpan.
