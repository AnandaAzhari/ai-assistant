"""Private owner Telegram adapter, with bounded retries and durable reply delivery.

Selain chat pribadi 1:1 (perilaku asli, tidak berubah), adapter ini juga bisa
menerima pesan dari topik-topik (forum topics) di SATU grup Telegram tertutup milik
owner sendiri — mis. grup "Taqi AI — Ruang Admin" dengan topik "🧠 Lead Agent",
"📁 Nara", "💰 Laras". Setiap topik dipetakan ke satu agent lewat
`AdminIdentity.topic_agents` (thread_id -> "lead"/"document"/"finance"); topik yang
tidak dipetakan (termasuk topik "General" bawaan) DIABAIKAN, tidak pernah diproses.
Balasan selalu dikirim kembali ke thread asal (`message_thread_id`), dan restriksi
admin (harus akun Telegram pemilik) berlaku SAMA baik di chat pribadi maupun di
grup — lihat `is_authorized`."""
from __future__ import annotations

import json
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass, field
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

    def send_message(self, chat_id: int, text: str, *, message_thread_id: int | None = None):
        if not text or len(text.encode('utf-16-le')) // 2 > 4096:
            raise ValueError('Balasan Telegram harus dipisahkan menjadi bagian yang lebih pendek.')
        data = {
            'chat_id': chat_id, 'text': text,
            'link_preview_options': json.dumps({'is_disabled': True}),
        }
        if message_thread_id is not None:
            # Hanya disertakan untuk pesan topik grup; chat pribadi tidak pernah
            # mengirim ini, jadi payload-nya identik dengan sebelum fitur topik ada.
            data['message_thread_id'] = message_thread_id
        return self._post('sendMessage', data, timeout=20)

    def edit_message_text(self, chat_id: int, message_id: int, text: str):
        """Perbarui isi pesan yang sudah terkirim di tempat yang sama (dipakai untuk
        pesan status berjalan — lihat `_StatusReporter` di bawah). Telegram menolak
        edit kalau teksnya identik dengan yang sekarang ("message is not modified");
        caller (`_StatusReporter`) sudah menghindari ini sendiri, tapi tetap dibiarkan
        sebagai TelegramError biasa kalau suatu saat terjadi, supaya ditangani seperti
        error Telegram lain (best-effort, tidak pernah menggagalkan alur utama)."""
        data = {
            'chat_id': chat_id, 'message_id': message_id, 'text': text,
            'link_preview_options': json.dumps({'is_disabled': True}),
        }
        return self._post('editMessageText', data, timeout=20)

    def delete_message(self, chat_id: int, message_id: int):
        return self._post('deleteMessage', {'chat_id': chat_id, 'message_id': message_id}, timeout=20)


class _StatusReporter:
    """Pelapor status satu-pesan untuk SATU update Telegram yang sedang diproses
    (dibuat ulang tiap `process_update`, tidak pernah dipakai ulang lintas pesan).
    Panggilan pertama kirim pesan status baru; panggilan berikutnya edit pesan yang
    sama di tempat lewat `editMessageText` — tidak pernah menumpuk beberapa pesan
    status terpisah. `clear()` menghapus pesan status begitu balasan final siap
    dikirim, supaya tidak ada pesan status yang tertinggal di riwayat chat.

    Diteruskan sebagai `on_status` ke `handler` (`LeadAgent.handle_admin_message`),
    yang meneruskannya apa adanya ke DocumentAgent/FinanceService/ContentStudio —
    lihat `_emit_status` di `app/document_agent.py`. Murni best-effort: kegagalan
    API Telegram di sini (jaringan, rate limit, dll.) TIDAK PERNAH menggagalkan
    pemrosesan pesan utama, hanya berarti status berjalan tidak tampil kali itu."""

    def __init__(self, client: TelegramHTTPClient, chat_id: int, thread_id: int | None):
        self._client = client
        self._chat_id = chat_id
        self._thread_id = thread_id
        self._message_id: int | None = None
        self._last_text: str | None = None

    def __call__(self, text: str) -> None:
        if not text or text == self._last_text:
            # Telegram menolak edit dengan teks yang identik dengan yang sekarang
            # ("message is not modified"); dicegah lebih dulu di sini.
            return
        try:
            if self._message_id is None:
                result = self._client.send_message(self._chat_id, text, message_thread_id=self._thread_id)
                if isinstance(result, dict) and type(result.get('message_id')) is int:
                    self._message_id = result['message_id']
            else:
                self._client.edit_message_text(self._chat_id, self._message_id, text)
            self._last_text = text
        except TelegramError:
            pass

    def clear(self) -> None:
        if self._message_id is None:
            return
        try:
            self._client.delete_message(self._chat_id, self._message_id)
        except TelegramError:
            pass
        self._message_id = None


@dataclass(frozen=True)
class AdminIdentity:
    user_id: int
    chat_id: int | None = None
    # Id grup Telegram "Ruang Admin" (angka negatif, wajar untuk supergroup) dan peta
    # thread_id topik -> nama agent ("lead"/"document"/"finance"). Keduanya opsional
    # (default: fitur topik nonaktif, hanya chat pribadi seperti sebelumnya) — lihat
    # `telegram_main.py` untuk cara mengisinya dari .env lewat mode --discover-topics.
    group_chat_id: int | None = None
    topic_agents: dict[int, str] = field(default_factory=dict)

    def __post_init__(self):
        if type(self.user_id) is not int or self.user_id <= 0:
            raise ValueError('TELEGRAM_ADMIN_USER_ID harus angka positif.')
        if self.chat_id is not None and (type(self.chat_id) is not int or self.chat_id <= 0):
            raise ValueError('Tahap ini memakai chat pribadi; TELEGRAM_ADMIN_CHAT_ID harus angka positif.')
        if self.group_chat_id is not None and type(self.group_chat_id) is not int:
            raise ValueError('TELEGRAM_ADMIN_GROUP_CHAT_ID harus angka (biasanya negatif untuk grup/supergroup).')

    @property
    def effective_chat_id(self) -> int:
        return self.chat_id if self.chat_id is not None else self.user_id

    def agent_for_topic(self, thread_id: int | None) -> str | None:
        """Nama agent ("lead"/"document"/"finance") untuk thread_id topik grup
        tertentu, atau None kalau topik itu belum dipetakan (termasuk topik "General"
        yang tidak pernah mengirim message_thread_id) — pesan dari topik yang tidak
        dikenal SENGAJA tidak diproses sama sekali, lihat `is_authorized`."""
        if thread_id is None:
            return None
        return self.topic_agents.get(thread_id)


INTERRUPTED_REPLY = (
    'Pemrosesan pesan sebelumnya terhenti sebelum hasilnya dapat dipastikan. '
    'Saya tidak mengulangi tindakan itu secara otomatis. Periksa /hari_ini atau /dokumen_status '
    'terlebih dahulu sebelum mengirim ulang permintaan yang sama.'
)


class TelegramAdminAdapter:
    def __init__(self, client: TelegramHTTPClient, identity: AdminIdentity,
                 handler: Callable[..., LeadReply], *, store: TelegramUpdateStore | None = None):
        # `handler` dipanggil sebagai handler(text, agent_hint=..., on_status=...) —
        # agent_hint None untuk chat pribadi/topik "Lead Agent" (perilaku default
        # LeadAgent, tidak berubah), atau "document"/"finance" untuk topik
        # Nara/Laras; on_status adalah `_StatusReporter` satu-pesan per update
        # (lihat kelas itu dan `process_update`) yang diteruskan apa adanya sampai
        # ke DocumentAgent/FinanceService/ContentStudio (lihat
        # LeadAgent.handle_admin_message di app/lead.py).
        self.client = client
        self.identity = identity
        self.handler = handler
        self.store = store
        self._seen: set[int] = set()

    def is_authorized(self, message: dict) -> bool:
        """Sama seperti sebelumnya untuk chat pribadi (tidak berubah sama sekali).
        Untuk grup: WAJIB tetap akun Telegram owner yang sama (sender.id, dicek
        persis seperti chat pribadi) DAN chat_id-nya grup admin yang dikonfigurasi
        DAN pesannya ada di salah satu topik yang sudah dipetakan ke agent — topik
        lain (termasuk "General") tidak pernah dianggap terotorisasi."""
        sender, chat = message.get('from'), message.get('chat')
        if not isinstance(sender, dict) or not isinstance(chat, dict):
            return False
        if type(sender.get('id')) is not int or sender['id'] != self.identity.user_id or sender.get('is_bot'):
            return False
        chat_type, chat_id = chat.get('type'), chat.get('id')
        if chat_type == 'private':
            return type(chat_id) is int and chat_id == self.identity.effective_chat_id
        if chat_type in {'group', 'supergroup'} and self.identity.group_chat_id is not None:
            if type(chat_id) is not int or chat_id != self.identity.group_chat_id:
                return False
            return self.identity.agent_for_topic(message.get('message_thread_id')) is not None
        return False

    def _deliver(self, update_id: int, chat_id: int, text: str, thread_id: int | None = None, sent: int = 0):
        chunks = text_chunks(text or 'Permintaan selesai tanpa balasan teks.')
        for index in range(sent, len(chunks)):
            self.client.send_message(chat_id, chunks[index], message_thread_id=thread_id)
            if self.store:
                self.store.delivered(update_id, index + 1, done=index + 1 == len(chunks))

    def flush_pending(self):
        if not self.store:
            return
        # Chat pribadi DAN grup admin (kalau dikonfigurasi) sama-sama punya pesan
        # tertunda yang mungkin perlu dikirim ulang setelah restart — sebelum topik
        # ada, hanya chat pribadi yang dicek di sini.
        chat_ids = [self.identity.effective_chat_id]
        if self.identity.group_chat_id is not None:
            chat_ids.append(self.identity.group_chat_id)
        for chat_id in chat_ids:
            for row in self.store.pending(chat_id):
                if row['state'] == 'processing':
                    self.store.complete(row['update_id'], INTERRUPTED_REPLY)
                    row['reply'] = INTERRUPTED_REPLY
                self._deliver(row['update_id'], row['chat_id'], row['reply'], row.get('thread_id'), row['sent_chunks'])

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
        # thread_id None untuk chat pribadi (tidak pernah mengirim message_thread_id)
        # ATAU topik "General" grup (juga tidak mengirimnya) — is_authorized sudah
        # menolak topik grup lain yang tidak dipetakan, jadi kalau sampai sini dan
        # thread_id ada isinya, itu pasti salah satu dari tiga topik yang dikenal.
        thread_id = message.get('message_thread_id')
        thread_id = thread_id if type(thread_id) is int else None
        agent_hint = self.identity.agent_for_topic(thread_id) if message['chat'].get('type') != 'private' else None
        if self.store:
            if not self.store.reserve(update_id, chat_id, thread_id):
                row = self.store.get(update_id)
                if row['chat_id'] != chat_id:
                    return False
                if row['state'] == 'sent':
                    return True
                if row['state'] == 'processing':
                    self.store.complete(update_id, INTERRUPTED_REPLY)
                    row['reply'] = INTERRUPTED_REPLY
                self._deliver(update_id, chat_id, row['reply'], row.get('thread_id'), row['sent_chunks'])
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
            status_reporter = _StatusReporter(self.client, chat_id, thread_id)
            try:
                # Normalize Telegram's /command@bot form before passing to the app.
                head, sep, tail = text.strip().partition(' ')
                if head.startswith('/'):
                    text = head.split('@', 1)[0] + sep + tail
                reply = self.handler(text, agent_hint=agent_hint, on_status=status_reporter)
                reply_text = reply.text
            except ValueError:
                reply_text = 'Permintaan belum dapat diselesaikan. Periksa /hari_ini atau /dokumen_status dan pastikan data lengkap sebelum mencoba lagi.'
            except Exception as exc:
                print(f'Pemrosesan pesan terhenti ({type(exc).__name__}); rincian pesan tidak dicetak.', flush=True)
                reply_text = INTERRUPTED_REPLY
            finally:
                # Pesan status (kalau sempat terkirim) selalu dibersihkan sebelum
                # balasan final dikirim di bawah — baik proses berhasil, gagal, atau
                # meleset ke exception yang tidak terduga.
                status_reporter.clear()
        if self.store:
            self.store.complete(update_id, reply_text)
        self._deliver(update_id, chat_id, reply_text, thread_id)
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
