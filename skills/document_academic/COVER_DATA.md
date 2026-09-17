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

Utamakan parser lokal deterministik tanpa token AI untuk pola yang jelas, misalnya:

- `Nama Sekolah SMK Negeri 2 Padangsidimpuan`
- `sekolah saya SMK Negeri 2 Padangsidimpuan`
- `tahun ajaran 2026/2027`
- `Nama Guru Purnama Sari`
- `dosen pengampu Budi Santoso`
- `Nama Sekolah: SMK Negeri 2 Padangsidimpuan`
- `Nama gurunya bukan Purnama Sari, ganti menjadi Nurhayati.`

Pelanggan tidak wajib memakai tanda titik dua atau format formulir tertentu.

Jika pesan jelas dapat dipahami parser lokal, jangan memanggil AI. AI fallback hanya boleh dipakai nanti untuk pesan yang benar-benar ambigu dan tidak aman dipetakan secara deterministik.

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

## Prioritas

1. Pedoman resmi guru/dosen/sekolah/kampus.
2. Koreksi terbaru pelanggan pada order yang sama.
3. Data cover yang sebelumnya tersimpan.
4. Fallback Taqi AI.

Jangan mengubah data cover order lain. Data harus tetap scoped per sesi/order.

## Implementasi

Implementasi parser aktif berada di `app/document_cover.py`.

`MakalahCoverData.update()` dipanggil berulang selama fase cover dan fase `ready_for_draft`, sehingga data opsional dapat ditambahkan setelah data wajib selesai tanpa reset sesi dan tanpa token AI.

`DocumentAgent` membandingkan snapshot sebelum dan sesudah pembaruan. Jika ada nilai berubah, respons memakai status `cover_updated` dan menampilkan field yang berubah.

Jika di masa depan pembaruan cover diizinkan setelah draft dibuat, metadata `MakalahSpec` juga harus disinkronkan sebelum file final dibangun agar cover Word/PDF memakai nilai terbaru.
