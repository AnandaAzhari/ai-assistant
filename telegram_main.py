"""Telegram Admin: connection check, explicit owner pairing, and service runtime."""
from __future__ import annotations

import argparse
import os
from pathlib import Path
import secrets
import sqlite3

from app.admin_runtime import create_admin_lead
from app.env import load_env
from app.lead import TELEGRAM_COMMAND_MENU
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


def optional_signed_int(name: str, value: str | None) -> int | None:
    """Sama seperti positive_int tapi MENGIZINKAN angka negatif — dipakai untuk
    TELEGRAM_ADMIN_GROUP_CHAT_ID dan TELEGRAM_TOPIC_* (id chat supergroup Telegram
    selalu negatif, mis. -1001234567890; id topik/thread biasanya positif tapi
    aturan formatnya tidak dijamin sama seperti chat_id chat pribadi)."""
    raw = (value or '').strip()
    if not raw:
        return None
    try:
        return int(raw)
    except ValueError:
        raise ValueError(f'{name} harus berupa angka Telegram ID.') from None


# thread_id topik grup -> nama agent yang dikenal LeadAgent.handle_admin_message
# (lihat app/lead.py). Urutan env var di sini HARUS sesuai label topik yang
# diminta owner: "🧠 Lead Agent", "📁 Nara", "💰 Laras".
_TOPIC_ENV_TO_AGENT = (
    ('TELEGRAM_TOPIC_LEAD_AGENT', 'lead'),
    ('TELEGRAM_TOPIC_NARA', 'document'),
    ('TELEGRAM_TOPIC_LARAS', 'finance'),
)


def discover_topics(client: TelegramHTTPClient, *, challenge: str | None = None) -> int:
    """Mode penemuan id topik grup admin — sama seperti discover_admin, tapi untuk
    grup forum-topics (mis. "Taqi AI — Ruang Admin"). Owner kirim pesan pairing yang
    sama persis di SETIAP topik yang ingin dihubungkan; setiap kombinasi
    (chat_id, thread_id) baru yang ditemukan langsung dicetak, supaya owner tinggal
    salin ke .env satu per satu tanpa perlu tahu cara membaca API Telegram."""
    code = challenge or secrets.token_hex(4)
    expected = '/hubungkan_topik ' + code
    print('Mode penemuan ID topik grup. Di grup "Taqi AI — Ruang Admin", buka SETIAP topik yang')
    print('ingin dihubungkan (Lead Agent, Nara, Laras) satu per satu, lalu kirim pesan berikut PERSIS')
    print('di masing-masing topik (kode hanya berlaku selama program ini terbuka):')
    print(expected)
    print('Bot harus sudah jadi anggota grup dan Privacy Mode-nya dimatikan (@BotFather -> /setprivacy).')
    print('Tekan Ctrl+C setelah semua topik sudah dikirimi pesan ini.')
    offset = None
    seen: set[tuple[int, int | None]] = set()
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
                if (not isinstance(sender, dict) or not isinstance(chat, dict)
                        or chat.get('type') not in {'group', 'supergroup'} or sender.get('is_bot')):
                    continue
                chat_id, thread_id = chat.get('id'), message.get('message_thread_id')
                if type(chat_id) is not int:
                    continue
                key = (chat_id, thread_id if type(thread_id) is int else None)
                if key in seen:
                    continue
                seen.add(key)
                topic_label = str(thread_id) if type(thread_id) is int else '(topik General)'
                print(f'\nDitemukan — TELEGRAM_ADMIN_GROUP_CHAT_ID={chat_id}  thread_id={topic_label}')
                print('Salin ke .env sesuai nama topiknya (mis. TELEGRAM_TOPIC_NARA=<thread_id>), lalu lanjut ke topik berikutnya.')
    except KeyboardInterrupt:
        print('\nSelesai. Pastikan TELEGRAM_ADMIN_GROUP_CHAT_ID dan TELEGRAM_TOPIC_LEAD_AGENT/')
        print('TELEGRAM_TOPIC_NARA/TELEGRAM_TOPIC_LARAS sudah terisi di .env, lalu jalankan lagi.')
        return 0


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
    modes.add_argument('--discover-topics', action='store_true', help='Temukan ID topik grup admin (Lead Agent/Nara/Laras)')
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
        if args.discover_topics:
            with telegram_process_lock(ROOT / 'data' / f'telegram-{bot["id"]}.lock'):
                return discover_topics(client)
        topic_agents = {}
        for env_name, agent_key in _TOPIC_ENV_TO_AGENT:
            topic_id = optional_signed_int(env_name, os.environ.get(env_name))
            if topic_id is not None:
                topic_agents[topic_id] = agent_key
        identity = AdminIdentity(
            user_id=positive_int('TELEGRAM_ADMIN_USER_ID', os.environ.get('TELEGRAM_ADMIN_USER_ID')),
            chat_id=positive_int('TELEGRAM_ADMIN_CHAT_ID', os.environ.get('TELEGRAM_ADMIN_CHAT_ID'), required=False),
            group_chat_id=optional_signed_int('TELEGRAM_ADMIN_GROUP_CHAT_ID', os.environ.get('TELEGRAM_ADMIN_GROUP_CHAT_ID')),
            topic_agents=topic_agents)
        if args.check:
            print('Konfigurasi ID admin terisi; kecocokan akun diuji saat Anda mengirim /status ke bot.')
            print('Mode: polling chat pribadi. Pemeriksaan ini tidak mengirim pesan atau menjalankan transaksi.')
            if identity.group_chat_id is not None:
                print(f'Grup admin: terkonfigurasi ({len(topic_agents)}/3 topik terhubung — Lead Agent/Nara/Laras).')
            else:
                print('Grup admin: belum dikonfigurasi (TELEGRAM_ADMIN_GROUP_CHAT_ID kosong) — hanya chat pribadi yang aktif.')
            print('Nara: ' + ('API key DeepSeek terisi; koneksi AI belum diuji.' if os.environ.get('DEEPSEEK_API_KEY', '').strip() else 'DEEPSEEK_API_KEY belum diisi.'))
            return 0
        with telegram_process_lock(ROOT / 'data' / f'telegram-{bot["id"]}.lock'):
            scope = f'DOCSRC-TELEGRAM-{bot["id"]}-{identity.user_id}-{identity.effective_chat_id}'
            lead = create_admin_lead(channel='telegram', document_scope=scope)
            db_path = os.environ.get('DATABASE_PATH', 'data/assistant.db').strip() or 'data/assistant.db'
            store = TelegramUpdateStore(db_path, bot['id'])
            adapter = TelegramAdminAdapter(client, identity, lead.handle_admin_message, store=store)
            try:
                client.set_my_commands(list(TELEGRAM_COMMAND_MENU))
                print('Menu perintah "/" Telegram terdaftar (termasuk /help).')
            except TelegramError as exc:
                # Kosmetik saja (autocomplete menu Telegram) — semua perintah tetap
                # berfungsi normal walau pendaftaran menu ini gagal, jadi jangan
                # menghentikan runtime hanya karena ini.
                print(f'Menu perintah "/" Telegram belum bisa didaftarkan ({exc}); perintah tetap bisa diketik manual.')
            print('Telegram Admin aktif untuk akun Anda. Kirim /status atau /bantuan ke bot.')
            print('Nara dan pencatatan keuangan terhubung. Sesi makalah Telegram terpisah dari Web Admin.')
            if identity.group_chat_id is not None:
                print(f'Grup admin aktif: {len(topic_agents)}/3 topik terhubung ke agent (Lead Agent/Nara/Laras).')
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
