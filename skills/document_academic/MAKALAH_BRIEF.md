# MakalahBrief v2 — Fondasi Document Agent

MakalahBrief adalah schema pusat untuk memahami kebutuhan pelanggan sebelum Nara membuat kerangka, melakukan riset, menulis isi, dan membangun Word/PDF.

## Prinsip arsitektur

Nara memakai pola **AI-first understanding + deterministic control**:

1. AI memahami bahasa pelanggan, typo, singkatan, urutan acak, dan koreksi.
2. AI mengembalikan update JSON terstruktur; bukan mengendalikan state aplikasi secara bebas.
3. Python memvalidasi, menyimpan, dan menentukan apakah data inti sudah cukup.
4. Parser lokal lama tetap tersedia sebagai fallback jika AI gagal atau output tidak valid.
5. Document Engine tetap menangani format Word/PDF secara deterministik.

Contoh pesan yang harus dipahami tanpa format khusus:

`Informatika, SMK, XII semseter 1`

Harus dipetakan menjadi:

- Jenjang: SMK
- Kelas/semester: Kelas XII, Semester 1
- Mata pelajaran: Informatika

Pelanggan tidak wajib memakai label seperti `Mapel:` atau `Kelas:`.

## Data inti sebelum membuat kerangka

Lima field berikut wajib cukup jelas sebelum kerangka dibuat:

- `institution_level` — jenjang sekolah/kampus;
- `class_semester` — kelas dan/atau semester;
- `subject` — mata pelajaran/mata kuliah;
- `topic_title` — topik/judul;
- `target_length` — target halaman/kata.

Arahan guru/dosen tidak wajib jika memang tidak ada.

## Data kualitas yang membantu hasil

Field berikut tidak memblokir pembuatan kerangka, tetapi harus disimpan jika pelanggan menyebutkannya:

- `teacher_instructions` — arahan/ketentuan guru atau dosen;
- `focus` — fokus pembahasan;
- `language_level` — tingkat bahasa yang diinginkan;
- `source_requirements` — ketentuan jenis/umur sumber;
- `citation_style` — gaya sitasi bila diwajibkan;
- `must_include` — materi yang wajib dimasukkan;
- `must_avoid` — hal yang harus dihindari;
- `official_guideline` — keberadaan/isi pedoman atau template resmi.

Jika fokus tidak diberikan pelanggan, Nara boleh mengusulkan fokus saat membuat kerangka. Usulan harus terlihat sebagai usulan, bukan dianggap instruksi pelanggan.

Usulan disimpan sementara dalam `_proposed_focus`. Persetujuan kerangka menguncinya melalui `MakalahBrief.approve_focus`; fokus eksplisit pelanggan tidak ditimpa. Nilai tersebut ikut dalam konteks pencarian, seleksi sumber, dan draft. Jika marker fokus tidak ada atau berbeda, teks usulan yang terlihat menjadi acuan. Revisi yang gagal tidak boleh mengunci usulan lama.

Preferensi pengulangan sitasi seperti `tanpa Ibid` atau `pakai short note` disimpan oleh `DocumentPreferenceStore`, bukan sebagai `must_avoid`. Jika pesan juga berisi larangan materi, bagian larangan materi tetap dipertahankan.

## Koreksi pelanggan

Nilai terbaru pelanggan mengalahkan nilai lama pada order yang sama.

Contoh:

- tersimpan: `Kelas XII, Semester 1`
- pelanggan: `eh salah semester 2`
- hasil: `Kelas XII, Semester 2`

Interpreter AI boleh memakai state lama untuk melengkapi bagian gabungan yang masih berlaku, tetapi field yang tidak disebut pada pesan terbaru harus `null` agar data lama tidak tertimpa tanpa alasan.

## Urutan percakapan

Pelanggan boleh memberi data dalam urutan apa pun dan boleh mencicilnya beberapa chat.

Alur kerja:

`Chat bebas pelanggan -> AI interpretasi -> update MakalahBrief -> validasi field inti -> tanya hanya yang masih kurang -> kerangka -> persetujuan/revisi -> cover -> riset -> draft -> validasi sitasi -> Word/PDF`

Pertanyaan Nara bukan formulir wajib. Jika Nara sedang menanyakan kelas tetapi pelanggan lebih dulu memberi mata pelajaran, data mata pelajaran tetap harus disimpan.

## Hubungan dengan cover

MakalahBrief menyimpan kebutuhan akademik dan kualitas isi. Data cover administratif tetap dikelola `MakalahCoverData` agar tanggung jawab terpisah dan mudah divalidasi.

Data cover boleh masuk sejak pesan pertama atau menyusul setelah kerangka disetujui. Interpreter membaca `CONVERSATION.md`; schema dan kelengkapan mengikuti `COVER_DATA.md`.

## Sumber kebenaran runtime

- Schema brief: `app/makalah_brief.py`
- AI interpreter: `app/document_intake.py`
- Orkestrasi fase: `app/document_agent.py`
- Fallback parser lama: `app/document_requirements.py`
- Cover: `app/document_cover.py`

Jangan menghapus fallback lokal hanya karena AI-first aktif. Fallback diperlukan agar percakapan masih dapat diproses secara dasar ketika provider AI gagal.
