# Outline UX v2 + otomatisasi riset/draft

Implementasi 17 September 2026; melanjutkan snapshot upstream `5cfda87439953c06d9d137f69f44a230dee74ccb`.

## Perilaku pelanggan

1. Data inti lengkap → ringkasan Python, usulan fokus jika diperlukan, kerangka, satu petunjuk persetujuan.
2. Setujui → fokus yang terlihat dikunci ke brief, lanjut cover.
3. Cover lengkap → tetap boleh koreksi; `lanjutkan` / `sudah cukup` menjalankan riset dan draft.
4. Riset membuat maksimal dua kueri lalu memilih sumber berdasarkan metadata/abstrak. Sumber tanpa abstrak tidak dipakai otomatis.
5. Draft hanya menerima ID sumber terpilih dari scope order. Sitasi tidak dikenal, rusak, atau kosong ditolak.
6. Setelah draft siap, `lanjutkan` menjalankan CitationEngine/Word/PDF yang sudah ada.

Kegagalan revisi mengharuskan revisi selesai dan disetujui kembali. Kegagalan riset/draft mempertahankan data sesi; retry draft memakai sumber terpilih yang tersimpan. Permintaan serentak untuk agen yang sama ditolak sebagai sedang diproses.

## Batas pengujian

Pengujian lokal menggunakan model dan pencarian tiruan serta SQLite sementara. Belum ada uji langsung DeepSeek, OpenAlex/Crossref, maupun alur Word/PDF pada Windows pengguna untuk perubahan ini.

Riset otomatis menilai metadata dan abstrak, bukan teks penuh. Relevansi dan ketentuan sumber dinilai model, sehingga tetap membutuhkan review hasil; validasi deterministik memeriksa identitas kandidat dan marker sitasi, bukan seluruh kebenaran akademik.

Sesi percakapan/brief tetap berada di memori seperti implementasi sebelumnya; hanya registry sumber dan preferensi disimpan SQLite. Web Admin masih satu sesi admin. Parameter `source_scope` tersedia untuk instance agen per order; routing multi-pelanggan bukan bagian perubahan ini.

## Uji lokal

- `test_document_outline_flow.py`: 14 tes lulus.
- `test_document_automation.py`: 14 tes lulus.
- `test_makalah*.py`: 23 tes lulus.
- `test_citation*.py`: 7 tes lulus.

Suite `test_document*.py` pada snapshot awal memiliki empat kegagalan yang juga teramati sebelum perubahan:

- `test_document_agent_calls_provider`, `test_lead_routes_makalah_to_document_agent`, `test_unconfigured_provider_does_not_call_api`: ekspektasi lama belum mengikuti tahap `needs_requirements`.
- `test_judul_belum_is_not_saved_as_title`: parser lama menyimpan `belum, 8 halaman` sebagai judul.

Kegagalan lama tersebut belum diperbaiki pada perubahan ini. Jangan menyatakan seluruh suite hijau.

## Checkpoint pengguna

Mulai dari satu perintah Git Bash:

```bash
cd /d/ai-assistant && git pull --ff-only && python -m unittest discover -s tests -p "test_document_outline_flow.py"
```

Setelah hasil tes dikonfirmasi, jalankan ulang Web Admin dan coba order baru dengan input dari handoff. Periksa hanya satu petunjuk approval dan konfirmasi fokus sebelum melanjutkan uji cover → riset → draft.
