"""Jalankan dengan: py -3 main.py"""

import argparse
import sys
from pathlib import Path

from app.desktop import DesktopAgent, Result
from app.lead import LeadAgent


HELP = """
Perintah:
  folder   - Buat satu folder pesanan.
  buka     - Buka file di dalam folder kerja.
  pesanan  - Buat folder pesanan, lalu buka file yang ditentukan.
  bantuan  - Tampilkan pilihan ini.
  keluar   - Tutup program.
Nama folder dan path file akan ditanyakan setelah memilih perintah.
"""


def report(result: Result) -> None:
    print(f"\nStatus: {result.status.replace('_', ' ')}")
    for message in result.messages:
        print(f"- {message}")
    if result.pending_file is not None:
        try:
            answer = input("Apakah file yang benar sudah terlihat? [y/n/Enter=belum tahu]: ").strip().lower()
        except (EOFError, KeyboardInterrupt):
            answer = ""
        if answer in {"y", "ya"}:
            print("Status akhir: berhasil. Verifikasi tampilan berdasarkan konfirmasi pengguna.")
        elif answer in {"n", "tidak"}:
            print("Status akhir: sebagian selesai. File belum terlihat dengan benar menurut pengguna.")
            print("Langkah folder yang sudah selesai tetap dipertahankan. Tidak ada percobaan ulang otomatis.")
        else:
            print("Status akhir: menunggu verifikasi. Keberhasilan membuka file belum dapat dipastikan.")


def main() -> int:
    parser = argparse.ArgumentParser(description="AI Assistant lokal v0.1 — uji terminal Windows.")
    parser.add_argument("--workspace", type=Path, help="Folder kerja yang sudah ada.")
    args = parser.parse_args()
    if sys.platform != "win32":
        print("Program terminal ini ditujukan untuk Windows. Pengujian unit dapat dijalankan di sistem lain.")
        return 1
    print("AI Assistant lokal v0.1 | Belum terhubung AI atau WhatsApp.")
    try:
        workspace = args.workspace
        if workspace is None:
            raw = input("Path folder kerja yang sudah ada (contoh D:\\Pesanan): ").strip().strip('"')
            if not raw:
                print("Folder kerja belum diisi. Jalankan ulang dan masukkan lokasi folder.")
                return 1
            workspace = Path(raw)
        desktop = DesktopAgent(workspace)
    except (OSError, ValueError, RuntimeError) as exc:
        print(f"Folder kerja tidak dapat digunakan: {exc}")
        return 1
    except (EOFError, KeyboardInterrupt):
        print("\nProgram ditutup.")
        return 0
    lead = LeadAgent(desktop)
    print(f"Folder kerja: {desktop.workspace}")
    print(HELP)
    try:
        while True:
            command = input("Perintah > ").strip().lower()
            if command == "keluar":
                break
            if command in {"bantuan", "help", "?"}:
                print(HELP)
                continue
            if not command:
                continue
            name = input("Nama folder pesanan: ").strip() if command in {"folder", "pesanan"} else ""
            path = input("Nama/path file (di dalam folder kerja): ").strip() if command in {"buka", "pesanan"} else ""
            report(lead.dispatch(command, name=name, path=path))
    except (EOFError, KeyboardInterrupt):
        print("\nInput dihentikan. Perubahan yang sudah selesai tetap tersimpan.")
    print("Program ditutup.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
