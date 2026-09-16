# Customer Interaction Policy

Status: **WAJIB / permanen** untuk semua channel pelanggan (Customer Webapp, WhatsApp, dan channel pelanggan lain di masa depan).

## Prinsip utama

**Slash command = admin/internal. Natural language = pelanggan.**

Pelanggan tidak diwajibkan mengetahui atau mengetik perintah seperti `/research`, `/sources`, `/draft`, `/sync`, atau command internal lain. Command dengan awalan `/` hanya untuk Web Admin, debugging, maintenance, atau operator yang memang memiliki akses admin.

## Aturan percakapan pelanggan

1. Pelanggan berkomunikasi dengan bahasa biasa, misalnya:
   - `Saya mau buat makalah tentang pencemaran lingkungan.`
   - `Kelas XI, Biologi, sekitar 10 halaman.`
   - `Sudah sesuai, lanjut.`
   - `Tolong revisi bagian kesimpulan.`

2. Sistem menerjemahkan maksud pelanggan menjadi aksi internal tanpa menampilkan command teknis.

3. Pertanyaan kepada pelanggan hanya meminta data yang benar-benar diperlukan. Data yang tidak penting untuk melanjutkan pekerjaan harus bersifat opsional.

4. Gunakan kata yang mudah dipahami siswa/i. Istilah teknis internal tidak ditampilkan bila ada padanan sederhana.
   - `requirement` -> `data yang diperlukan` / `data utama`
   - `outline` -> `kerangka makalah`
   - `draft` -> `isi makalah` / `versi awal makalah`
   - `source registry` -> `daftar sumber`
   - `citation` -> `kutipan/sumber`
   - `footnote` -> `catatan kaki`
   - `generate` -> `buat`

5. Instruksi/arahan guru atau dosen bersifat **opsional**. Jika pelanggan tidak memberikan arahan khusus, sistem memakai format standar.

6. Data cover yang tidak selalu diperlukan juga opsional, kecuali memang diperlukan untuk menghasilkan cover yang diminta pelanggan. Nama guru/dosen dan tahun ajaran tidak boleh menghalangi proses bila tidak diberikan.

7. Sebelum aksi yang memakai token AI besar atau menghasilkan file final, sistem meminta persetujuan dengan bahasa sederhana, misalnya `Kerangkanya sudah sesuai?` atau `Boleh saya lanjut membuat isi makalah?`.

8. Pelanggan tidak diperlihatkan nama class, status internal, marker `[[R1]]`, token routing, command admin, atau istilah implementasi lain.

## Pemisahan channel

### Admin
Boleh memakai slash command dan melihat detail teknis, status provider, token, sumber R1/R2, path file, dan informasi debugging.

### Pelanggan
Hanya memakai bahasa natural. Sistem menjalankan aksi internal secara otomatis berdasarkan fase pekerjaan dan konfirmasi pelanggan.

## Contoh pemetaan internal

Pelanggan: `Tolong carikan sumber yang cocok.`

Internal: menjalankan Research Manager dan Source Registry tanpa menampilkan `/research` atau `/research_save`.

Pelanggan: `Sudah sesuai, lanjut buat isinya.`

Internal: memanggil generator isi makalah setelah syarat dan sumber siap, tanpa menampilkan `/draft`.

Pelanggan: `Buatkan file Word dan PDF.`

Internal: menjalankan Citation Engine + Document Engine, tanpa meminta pelanggan mengetahui command teknis.

## Catatan implementasi

Setiap customer-facing adapter harus memanggil intent/action internal secara langsung, bukan meneruskan slash command ke UI pelanggan. Slash command tetap dipertahankan untuk Web Admin agar debugging dan pengujian cepat tetap tersedia.
