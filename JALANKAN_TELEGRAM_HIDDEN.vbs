' Menjalankan JALANKAN_TELEGRAM_BACKGROUND.bat tanpa jendela terminal yang
' kelihatan. Dipanggil oleh Task Scheduler (lihat SETUP_AUTOSTART_TELEGRAM.bat),
' tidak perlu dijalankan manual.
Dim fso, scriptDir, shell
Set fso = CreateObject("Scripting.FileSystemObject")
scriptDir = fso.GetParentFolderName(WScript.ScriptFullName)
Set shell = CreateObject("WScript.Shell")
' 0 = jendela disembunyikan, False = tidak menunggu proses selesai
' (proses Telegram memang dirancang jalan terus/polling, bukan sekali jalan lalu berhenti)
shell.Run """" & scriptDir & "\JALANKAN_TELEGRAM_BACKGROUND.bat""", 0, False
