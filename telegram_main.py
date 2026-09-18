"""Telegram Admin: connection check, explicit owner pairing, and service runtime."""
from __future__ import annotations

import argparse
import os
from pathlib import Path
import secrets
import sqlite3

from app.admin_runtime import create_admin_lead
from app.env import load_env
from app.telegram import AdminIdentity, TelegramAdminAdapter, TelegramHTTPClient, TelegramError
from app.telegram_store import TelegramUpdateStore
from app.telegram_lock import TelegramAlreadyRunning, telegram_process_lock


ROOT = Path(__file__).resolve().parent


def positive_int(name: str, value: str | None, *, required: bool = True) -> int | None:
    raw = (value or '').strip()
    if not raw:
        if required:
            raise ValueError(f'{name} belum diisi di .env')
        return None
    try:
        result = int(raw)
    except ValueError:
        raise ValueError(f'{name} harus berupa angka Telegram ID.') from None
    if result <= 0:
        raise ValueError(f'{name} harus positif. Gunakan chat pribadi dengan bot.')
    return result


def discover_admin(client: TelegramHTTPClient, *, challenge: str | None = None) -> int:
    code = challenge or secrets.token_hex(4)
    expected = '/hubungkan ' + code
    print('Mode penemuan ID admin. Buka chat PRIBADI dengan bot dari akun Anda sendiri.')
    print('Kirim pesan berikut persis (kode hanya berlaku selama program ini terbuka):')
    print(expected)
    print('Tekan Ctrl+C untuk batal. Token bot tidak perlu dikirim ke siapa pun.')
    offset = None
    try:
        while True:
            updates = client.get_updates(offset=offset, timeout=30)
            for update in updates:
                if not isinstance(update, dict):
                    continue
                update_id = update.get('update_id')
                if type(update_id) is int:
                    offset = update_id + 1
                message = update.get('message')
                if not isinstance(message, dict) or not isinstance(message.get('text'), str) or message['text'].strip() != expected:
                    continue
                sender, chat = message.get('from'), message.get('chat')
                if not isinstance(sender, dict) or not isinstance(chat, dict) or chat.get('type') != 'private':
                    continue
                user_id, chat_id = sender.get('id'), chat.get('id')
                if type(user_id) is int and type(chat_id) is int and user_id > 0 and chat_id > 0 and not sender.get('is_bot'):
                    print('\nID akun Anda ditemukan:')
                    print(f'TELEGRAM_ADMIN_USER_ID={user_id}')
                    print(f'TELEGRAM_ADMIN_CHAT_ID={chat_id}')
                    print('Salin dua baris ini ke .env lokal, lalu jalankan JALANKAN_TELEGRAM.bat.')
                    return 0
    except KeyboardInterrupt:
        print('\nDibatalkan.')
        return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description='Taqi AI — Telegram Admin, Nara dan pencatatan keuangan')
    modes = parser.add_mutually_exclusive_group()
    modes.add_argument('--discover-admin', action='store_true', help='Temukan ID owner lewat kode pairing pribadi')
    modes.add_argument('--check', action='store_true', help='Periksa token, koneksi, webhook dan konfigurasi tanpa mengirim chat')
    parser.add_argument('--remove-webhook', action='store_true', help='Pindah dari webhook ke polling, tanpa membuang pesan tertunda')
    args = parser.parse_args(argv)

    os.chdir(ROOT)
    load_env(ROOT / '.env')
    token = os.environ.get('TELEGRAM_BOT_TOKEN', '').strip()
    if not token:
        print('TELEGRAM_BOT_TOKEN belum diisi di .env lokal. Pertahankan pengaturan DeepSeek yang sudah ada.')
        return 2
    try:
        client = TelegramHTTPClient(token)
        bot = client.get_me()
        if not isinstance(bot, dict) or type(bot.get('id')) is not int or not bot.get('is_bot'):
            raise TelegramError('Identitas bot dari Telegram tidak valid.', retryable=False)
        print('Koneksi Telegram berhasil. Bot: @' + str(bot.get('username') or '(tanpa username)'))
        if args.remove_webhook:
            client.delete_webhook()
            print('Webhook dinonaktifkan sesuai opsi Anda; pesan tertunda tetap dipertahankan.')
        webhook = client.get_webhook_info()
        if not isinstance(webhook, dict):
            raise TelegramError('Status webhook tidak dapat dibaca.')
        if webhook.get('url'):
            print('Bot masih memakai webhook. Jika ingin memakai runtime PC ini, jalankan:')
            print('python telegram_main.py --remove-webhook --check')
            return 2
        if args.discover_admin:
            with telegram_process_lock(ROOT / 'data' / f'telegram-{bot["id"]}.lock'):
                return discover_admin(client)
        identity = AdminIdentity(
            user_id=positive_int('TELEGRAM_ADMIN_USER_ID', os.environ.get('TELEGRAM_ADMIN_USER_ID')),
            chat_id=positive_int('TELEGRAM_ADMIN_CHAT_ID', os.environ.get('TELEGRAM_ADMIN_CHAT_ID'), required=False))
        if args.check:
            print('Konfigurasi ID admin terisi; kecocokan akun diuji saat Anda mengirim /status ke bot.')
            print('Mode: polling chat pribadi. Pemeriksaan ini tidak mengirim pesan atau menjalankan transaksi.')
            print('Nara: ' + ('API key DeepSeek terisi; koneksi AI belum diuji.' if os.environ.get('DEEPSEEK_API_KEY', '').strip() else 'DEEPSEEK_API_KEY belum diisi.'))
            return 0
        with telegram_process_lock(ROOT / 'data' / f'telegram-{bot["id"]}.lock'):
            scope = f'DOCSRC-TELEGRAM-{bot["id"]}-{identity.user_id}-{identity.effective_chat_id}'
            lead = create_admin_lead(channel='telegram', document_scope=scope)
            db_path = os.environ.get('DATABASE_PATH', 'data/assistant.db').strip() or 'data/assistant.db'
            store = TelegramUpdateStore(db_path, bot['id'])
            adapter = TelegramAdminAdapter(client, identity, lead.handle_admin_message, store=store)
            print('Telegram Admin aktif untuk akun Anda. Kirim /status atau /bantuan ke bot.')
            print('Nara dan pencatatan keuangan terhubung. Sesi makalah Telegram terpisah dari Web Admin.')
            print('Biarkan terminal ini terbuka. Ctrl+C untuk berhenti; data sesi tersimpan di komputer.')
            adapter.run_forever()
    except TelegramAlreadyRunning as exc:
        print(str(exc))
        return 1
    except ValueError as exc:
        print('Konfigurasi atau data belum dapat digunakan: ' + str(exc))
        print('Jika ID admin belum tersedia, jalankan TEMUKAN_TELEGRAM_ID.bat terlebih dahulu.')
        return 2
    except TelegramError as exc:
        print('Telegram berhenti: ' + str(exc))
        return 1
    except (OSError, sqlite3.Error):
        print('Akses penyimpanan lokal gagal. Periksa lokasi DATABASE_PATH dan ruang penyimpanan; jangan hapus database lama.')
        return 1
    except KeyboardInterrupt:
        print('\nDihentikan.')
    print('Telegram Admin ditutup.')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
