# Google Sheets Sync — Setup Webhook

Tujuan: menghubungkan Finance Agent lokal ke spreadsheet `AI Assistant - Finance Dashboard` tanpa menyimpan credential Google Cloud di GitHub.

SQLite tetap menjadi source of truth. Google Sheets hanya mirror/reporting layer.

Spreadsheet Finance Dashboard saat ini:
- Spreadsheet ID: `1eT10rk2eURDu1RlXvL6Bq_Ck1yK4UF79O4J3eAkpIiM`

## 1. Pasang Apps Script di spreadsheet
1. Buka spreadsheet Finance Dashboard.
2. Pilih **Extensions > Apps Script**.
3. Ganti isi `Code.gs` dengan isi file repo `integrations/google_sheets/Code.gs`.
4. Buka **Project Settings > Script Properties**.
5. Tambahkan dua property:
   - Name: `SYNC_SECRET`
   - Value: secret acak yang panjang dan hanya kamu simpan lokal.
   - Name: `SPREADSHEET_ID`
   - Value: `1eT10rk2eURDu1RlXvL6Bq_Ck1yK4UF79O4J3eAkpIiM`

Jangan commit secret ke GitHub. Spreadsheet ID bukan secret, tetapi tetap tidak perlu dibagikan ke pihak lain tanpa alasan.

Secret dapat dibuat lokal dengan Python:

```powershell
py -3 -c "import secrets; print(secrets.token_urlsafe(32))"
```

Simpan output itu untuk `SYNC_SECRET` dan `.env`. Jangan kirim secret tersebut ke chat.

## 2. Deploy Web App
1. Klik **Deploy > New deployment**.
2. Pilih type **Web app**.
3. Execute as: akun kamu sendiri.
4. Access: gunakan opsi yang mengizinkan request HTTPS dari AI Assistant lokal. Untuk akun personal biasanya `Anyone`.
5. Deploy dan salin URL Web App HTTPS yang berakhir `/exec`.

Endpoint memang dapat menerima request dari internet jika memakai opsi `Anyone`, tetapi write hanya diterima ketika `SYNC_SECRET` cocok. Jika opsi akses publik tidak tersedia pada akun Google kamu, jangan menurunkan keamanan dengan workaround acak; gunakan metode OAuth/service account pada tahap berikutnya.

## 3. Buat file `.env` lokal
Di root repo `ai-assistant`, buat `.env` jika belum ada. Isi minimal:

```env
DATABASE_PATH=data/assistant.db
GOOGLE_SHEETS_WEBHOOK_URL=https://script.google.com/macros/s/ISI_URL_DEPLOYMENT/exec
GOOGLE_SHEETS_SYNC_SECRET=ISI_SECRET_YANG_SAMA
```

Jika `.env` sudah berisi konfigurasi lain, cukup tambahkan dua baris `GOOGLE_SHEETS_...`; jangan menimpa konfigurasi yang sudah ada.

File `.env` sudah di-ignore Git dan tidak boleh di-upload.

## 4. Jalankan Web Admin
Tutup Web Admin lama lalu jalankan `JALANKAN_WEB_ADMIN.bat`.

Cek:

```text
/sync_status
```

Jika siap, jalankan:

```text
/sync
```

Sync akan melakukan upsert/reconciliation untuk:
- tab `Transaksi`, berdasarkan ID transaksi;
- tab `Akun`, berdasarkan nama akun;
- tab `Kategori`, berdasarkan nama kategori + jenis.

Retry manual aman karena transaksi menggunakan ID stabil dan tidak append duplikat untuk ID yang sama.

## Keamanan
- Webhook wajib HTTPS.
- Secret hanya disimpan di `.env` lokal dan Script Properties.
- Script membuka spreadsheet berdasarkan `SPREADSHEET_ID`, bukan active spreadsheet context.
- Jangan kirim PIN, OTP, password bank, atau API key ke spreadsheet.
- Kegagalan sync tidak membatalkan transaksi yang sudah tersimpan di SQLite.
