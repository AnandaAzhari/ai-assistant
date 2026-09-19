"""Private owner Telegram adapter, with bounded retries and durable reply delivery."""
from __future__ import annotations

import json
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from typing import Callable

from app.lead import LeadReply
from app.telegram_store import TelegramUpdateStore


class TelegramError(RuntimeError):
    def __init__(self, message: str, *, retryable: bool = True, retry_after: int = 0):
        super().__init__(message)
        self.retryable = retryable
        self.retry_after = retry_after


def text_chunks(text: str, limit: int = 3500) -> list[str]:
    """Split without dropping text, respecting UTF-16 units for emoji as well."""
    if not text:
        return []
    parts = []
    start = units = last_break = 0
    for index, char in enumerate(text):
        size = 2 if ord(char) > 0xFFFF else 1
        while units + size > limit:
            end = last_break if last_break > start else index
            parts.append(text[start:end])
            start = end
            units = len(text[start:index].encode('utf-16-le')) // 2
            last_break = start
        units += size
        if char == '\n':
            last_break = index + 1
    if start < len(text):
        parts.append(text[start:])
    return parts


class TelegramHTTPClient:
    def __init__(self, token: str, *, api_base: str = 'https://api.telegram.org'):
        token = (token or '').strip()
        if not token or any(char.isspace() for char in token):
            raise ValueError('TELEGRAM_BOT_TOKEN kosong atau mengandung spasi.')
        self._base = f"{api_base.rstrip('/')}/bot{token}"

    @staticmethod
    def _api_error(code: int, payload=None) -> TelegramError:
        # Never echo raw API descriptions, exception URLs, message content, or tokens.
        messages = {
            400: 'Telegram menolak format permintaan. Periksa konfigurasi bot dan chat.',
            401: 'Token bot tidak valid. Periksa TELEGRAM_BOT_TOKEN di .env.',
            403: 'Bot tidak dapat mengirim pesan. Buka chat bot, tekan Start, dan pastikan bot tidak diblokir.',
            404: 'Bot atau endpoint tidak ditemukan. Periksa token bot.',
            409: 'Polling bot bentrok. Tutup runtime Telegram lain dan periksa webhook dengan --check.',
            429: 'Batas permintaan Telegram tercapai; pengiriman akan dicoba kembali.',
        }
        retry_after = 0
        if isinstance(payload, dict):
            parameters = payload.get('parameters')
            if isinstance(parameters, dict) and isinstance(parameters.get('retry_after'), int):
                retry_after = max(0, parameters['retry_after'])
        return TelegramError(messages.get(code, 'Layanan Telegram sementara tidak tersedia.'),
                             retryable=code == 429 or code >= 500, retry_after=retry_after)

    def _post(self, method: str, data: dict, *, timeout: int = 45):
        request = urllib.request.Request(
            f'{self._base}/{method}', data=urllib.parse.urlencode(data).encode('utf-8'),
            headers={'Content-Type': 'application/x-www-form-urlencoded'}, method='POST')
        try:
            with urllib.request.urlopen(request, timeout=timeout) as response:
                payload = json.loads(response.read().decode('utf-8'))
        except urllib.error.HTTPError as exc:
            try:
                payload = json.loads(exc.read().decode('utf-8'))
            except (ValueError, OSError):
                payload = None
            raise self._api_error(exc.code, payload) from None
        except (urllib.error.URLError, TimeoutError, OSError):
            raise TelegramError('Koneksi Telegram terputus atau melewati batas waktu. Periksa internet.') from None
        except (ValueError, UnicodeDecodeError):
            raise TelegramError('Respons Telegram tidak dapat dibaca.') from None
        if not isinstance(payload, dict):
            raise TelegramError('Format respons Telegram tidak valid.')
        if not payload.get('ok'):
            code = payload.get('error_code', 500)
            raise self._api_error(code if isinstance(code, int) else 500, payload)
        return payload.get('result')

    def get_me(self):
        return self._post('getMe', {}, timeout=20)

    def get_webhook_info(self):
        return self._post('getWebhookInfo', {}, timeout=20)

    def delete_webhook(self):
        return self._post('deleteWebhook', {'drop_pending_updates': 'false'}, timeout=20)

    def set_my_commands(self, commands: list[tuple[str, str]]):
        """Daftarkan menu "/" bawaan Telegram lewat `setMyCommands`. Murni kosmetik
        (autocomplete di client Telegram) — pesan tetap diproses normal lewat
        `get_updates`/`send_message` di atas walau method ini tidak pernah dipanggil
        atau gagal, jadi caller sebaiknya memperlakukan kegagalan ini sebagai
        best-effort, bukan fatal (lihat `telegram_main.py`)."""
        payload = [{'command': command, 'description': description} for command, description in commands]
        return self._post('setMyCommands', {'commands': json.dumps(payload)}, timeout=20)

    def get_updates(self, *, offset: int | None = None, timeout: int = 30):
        data = {'timeout': timeout, 'allowed_updates': json.dumps(['message'])}
        if offset is not None:
            data['offset'] = offset
        result = self._post('getUpdates', data, timeout=timeout + 10)
        if not isinstance(result, list):
            raise TelegramError('Daftar pesan Telegram tidak valid.')
        return result

    def send_message(self, chat_id: int, text: str):
        if not text or len(text.encode('utf-16-le')) // 2 > 4096:
            raise ValueError('Balasan Telegram harus dipisahkan menjadi bagian yang lebih pendek.')
        return self._post('sendMessage', {
            'chat_id': chat_id, 'text': text,
            'link_preview_options': json.dumps({'is_disabled': True}),
        }, timeout=20)


@dataclass(frozen=True)
class AdminIdentity:
    user_id: int
    chat_id: int | None = None

    def __post_init__(self):
        if type(self.user_id) is not int or self.user_id <= 0:
            raise ValueError('TELEGRAM_ADMIN_USER_ID harus angka positif.')
        if self.chat_id is not None and (type(self.chat_id) is not int or self.chat_id <= 0):
            raise ValueError('Tahap ini memakai chat pribadi; TELEGRAM_ADMIN_CHAT_ID harus angka positif.')

    @property
    def effective_chat_id(self) -> int:
        return self.chat_id if self.chat_id is not None else self.user_id


INTERRUPTED_REPLY = (
    'Pemrosesan pesan sebelumnya terhenti sebelum hasilnya dapat dipastikan. '
    'Saya tidak mengulangi tindakan itu secara otomatis. Periksa /hari_ini atau /dokumen_status '
    'terlebih dahulu sebelum mengirim ulang permintaan yang sama.'
)


class TelegramAdminAdapter:
    def __init__(self, client: TelegramHTTPClient, identity: AdminIdentity,
                 handler: Callable[[str], LeadReply], *, store: TelegramUpdateStore | None = None):
        self.client = client
        self.identity = identity
        self.handler = handler
        self.store = store
        self._seen: set[int] = set()

    def is_authorized(self, message: dict) -> bool:
        sender, chat = message.get('from'), message.get('chat')
        if not isinstance(sender, dict) or not isinstance(chat, dict):
            return False
        return (type(sender.get('id')) is int and sender['id'] == self.identity.user_id
                and not sender.get('is_bot') and chat.get('type') == 'private'
                and type(chat.get('id')) is int and chat['id'] == self.identity.effective_chat_id)

    def _deliver(self, update_id: int, chat_id: int, text: str, sent: int = 0):
        chunks = text_chunks(text or 'Permintaan selesai tanpa balasan teks.')
        for index in range(sent, len(chunks)):
            self.client.send_message(chat_id, chunks[index])
            if self.store:
                self.store.delivered(update_id, index + 1, done=index + 1 == len(chunks))

    def flush_pending(self):
        if not self.store:
            return
        for row in self.store.pending(self.identity.effective_chat_id):
            if row['state'] == 'processing':
                self.store.complete(row['update_id'], INTERRUPTED_REPLY)
                row['reply'] = INTERRUPTED_REPLY
            self._deliver(row['update_id'], row['chat_id'], row['reply'], row['sent_chunks'])

    def process_update(self, update: dict) -> bool:
        if not isinstance(update, dict):
            return False
        message = update.get('message')
        update_id = update.get('update_id')
        if not isinstance(message, dict) or type(update_id) is not int or update_id < 0:
            return False
        if not self.is_authorized(message):
            return False
        chat_id = message['chat']['id']
        if self.store:
            if not self.store.reserve(update_id, chat_id):
                row = self.store.get(update_id)
                if row['chat_id'] != chat_id:
                    return False
                if row['state'] == 'sent':
                    return True
                if row['state'] == 'processing':
                    self.store.complete(update_id, INTERRUPTED_REPLY)
                    row['reply'] = INTERRUPTED_REPLY
                self._deliver(update_id, chat_id, row['reply'], row['sent_chunks'])
                return True
        elif update_id in self._seen:
            return True
        if not self.store:
            self._seen.add(update_id)
        text = message.get('text')
        if not isinstance(text, str):
            reply_text = 'Telegram saat ini menerima pesan teks. Foto struk, suara, dan lampiran belum diproses; tuliskan keterangannya terlebih dahulu.'
        elif len(text) > 8000:
            reply_text = 'Pesan terlalu panjang. Mohon kirim dalam beberapa bagian.'
        else:
            try:
                # Normalize Telegram's /command@bot form before passing to the app.
                head, sep, tail = text.strip().partition(' ')
                if head.startswith('/'):
                    text = head.split('@', 1)[0] + sep + tail
                reply = self.handler(text)
                reply_text = reply.text
            except ValueError:
                reply_text = 'Permintaan belum dapat diselesaikan. Periksa /hari_ini atau /dokumen_status dan pastikan data lengkap sebelum mencoba lagi.'
            except Exception as exc:
                print(f'Pemrosesan pesan terhenti ({type(exc).__name__}); rincian pesan tidak dicetak.', flush=True)
                reply_text = INTERRUPTED_REPLY
        if self.store:
            self.store.complete(update_id, reply_text)
        self._deliver(update_id, chat_id, reply_text)
        return True

    def run_forever(self, *, poll_timeout: int = 30) -> None:
        offset = self.store.offset() if self.store else None
        delay = 1
        while True:
            try:
                self.flush_pending()
                updates = self.client.get_updates(offset=offset, timeout=poll_timeout)
                for update in updates:
                    self.process_update(update)
                    update_id = update.get('update_id') if isinstance(update, dict) else None
                    if type(update_id) is int and update_id >= 0:
                        offset = max(offset or 0, update_id + 1)
                        if self.store:
                            self.store.advance(offset)
                delay = 1
            except KeyboardInterrupt:
                return
            except TelegramError as exc:
                if not exc.retryable:
                    raise
                print(f'Telegram sementara gagal: {exc}', flush=True)
                # Break long Retry-After intervals into interruptible short waits.
                remaining = max(delay, exc.retry_after)
                while remaining > 0:
                    try:
                        time.sleep(min(remaining, 30))
                    except KeyboardInterrupt:
                        return
                    remaining -= 30
                delay = min(delay * 2, 30)
