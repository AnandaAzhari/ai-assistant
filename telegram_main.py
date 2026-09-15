"""Telegram Admin runtime minimum.

Pemakaian:
  py -3 telegram_main.py --discover-admin
  py -3 telegram_main.py

Token dan ID admin dibaca dari .env lokal, bukan GitHub.
"""

from __future__ import annotations

import argparse
import os

from app.env import load_env
from app.lead import LeadAgent
from app.telegram import AdminIdentity, TelegramAdminAdapter, TelegramHTTPClient, TelegramError


def positive_int(name: str, value: str | None, *, required: bool = True) -> int | None:
    raw = (value or "").strip()
    if not raw:
        if required:
            raise ValueError(f"{name} belum diisi di .env")
        return None
    try:
        return int(raw)
    except ValueError as exc:
        raise ValueError(f"{name} harus berupa angka Telegram ID.") from exc


def discover_admin(client: TelegramHTTPClient) -> int:
    print("Mode penemuan ID admin aktif.")
    print("Sekarang kirim satu pesan ke bot dari akun Telegram owner. Tekan Ctrl+C untuk batal.")
    offset = None
    try:
        while True:
            updates = client.get_updates(offset=offset, timeout=30)
            for update in updates:
                update_id = update.get("update_id")
                if isinstance(update_id, int):
                    offset = update_id + 1
                message = update.get("message") or {}
                sender = message.get("from") or {}
                chat = message.get("chat") or {}
                user_id = sender.get("id")
                chat_id = chat.get("id")
                if isinstance(user_id, int) and isinstance(chat_id, int):
                    print("\nID ditemukan:")
                    print(f"TELEGRAM_ADMIN_USER_ID={user_id}")
                    print(f"TELEGRAM_ADMIN_CHAT_ID={chat_id}")
                    print("Salin dua baris di atas ke file .env lokal. Jangan masukkan token ke GitHub.")
                    return 0
    except KeyboardInterrupt:
        print("\nDibatalkan.")
        return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="AI Assistant — Telegram Admin minimum")
    parser.add_argument("--discover-admin", action="store_true", help="Temukan user_id dan chat_id owner tanpa menjalankan agent")
    args = parser.parse_args()

    load_env(".env")
    token = os.environ.get("TELEGRAM_BOT_TOKEN", "").strip()
    if not token:
        print("TELEGRAM_BOT_TOKEN belum diisi. Salin config/.env.example menjadi .env lalu isi token bot lokal.")
        return 2

    try:
        client = TelegramHTTPClient(token)
        if args.discover_admin:
            return discover_admin(client)

        user_id = positive_int("TELEGRAM_ADMIN_USER_ID", os.environ.get("TELEGRAM_ADMIN_USER_ID"))
        chat_id = positive_int("TELEGRAM_ADMIN_CHAT_ID", os.environ.get("TELEGRAM_ADMIN_CHAT_ID"), required=False)
        lead = LeadAgent()
        adapter = TelegramAdminAdapter(client, AdminIdentity(user_id=user_id, chat_id=chat_id), lead.handle_admin_message)
    except ValueError as exc:
        print(f"Konfigurasi Telegram belum lengkap: {exc}")
        return 2

    print("Telegram Admin aktif. Hanya owner pada allowlist yang diproses.")
    print("Kirim /status atau /bantuan ke bot. Tutup dengan Ctrl+C.")
    try:
        adapter.run_forever()
    except TelegramError as exc:
        print(f"Telegram gagal dijalankan: {exc}")
        return 1
    print("Telegram Admin ditutup.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
