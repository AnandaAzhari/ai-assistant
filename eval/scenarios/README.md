# Skenario Evaluasi (Fase 5)

Kumpulan skenario uji untuk menilai kualitas jawaban AI per agent — lihat
`docs/roadmap_customer_channel_v1.md` bagian "Fase 5: Evaluasi & Observability".
Ini BEDA dari `tests/` (yang menguji logika Python deterministik): file di sini
menguji apakah *jawaban* AI-nya bagus, dan penilaiannya manual oleh owner.

## Status penting

Skenario di folder ini adalah **draft awal dari AI (Claude)**, dibuat sebagai titik
awal — BUKAN standar "baik/tidak baik" yang sudah divalidasi. Sesuai
`docs/roadmap_customer_channel_v1.md`: "...yang jawabannya dicek manual dulu oleh
kamu sebagai patokan baik/tidak baik". Jadi:

- Baca tiap skenario, dan kalau kriteria "ciri jawaban baik"-nya tidak sesuai
  dengan yang Anda mau, ubah langsung di file markdown-nya (tidak perlu lewat AI).
- Target roadmap adalah 15-20 skenario per agent. File di sini baru berisi titik
  awal (~8 per agent) — tambah seiring waktu, terutama dari interaksi produksi
  nyata yang ditandai `tidak_baik`/`perlu_perbaikan` lewat `/eval_tandai` di
  Telegram Admin (lihat `app/interaction_log.py`). Interaksi nyata yang bermasalah
  adalah sumber skenario baru yang paling berharga — lebih baik dari mengarang
  skenario baru dari nol.

## Cara pakai

1. Jalankan skenario secara manual: kirim pesan pertama ke agent yang bersangkutan
   (WhatsApp untuk Nara/Taqi, Telegram Admin untuk Laras/Kirana), lanjutkan sesuai
   alur percakapan di skenario, lalu bandingkan jawaban asli dengan "Ciri jawaban
   baik"/"Ciri jawaban kurang baik" di bawah tiap skenario.
2. Tinjauan berkala interaksi produksi (mingguan/bulanan) lewat `/eval_sample
   <agent>` di Telegram Admin, lalu tandai dengan `/eval_tandai <id> |
   baik/perlu_perbaikan/tidak_baik | <catatan>`. Lihat tren lewat `/eval_status`.
3. Skenario di sini belum ada runner otomatis (v1 sengaja manual dulu, sesuai
   roadmap) — kalau nanti mau otomatisasi, bisa dikonversi ke format terstruktur
   (JSON/YAML) dan dijalankan lewat skrip yang memanggil agent langsung.

## Daftar file

- `nara.md` — Document Agent (penyusunan makalah/KTI/skripsi, Taqi Desk)
- `finance_agent.md` — Finance Agent/Laras (pencatatan keuangan, lintas usaha)
- `social_media_agent.md` — Social Media Agent/Kirana (Content Studio, draft caption)
