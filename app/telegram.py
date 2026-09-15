"""Telegram Bot API adapter untuk owner/admin.

Tidak menyimpan token. Semua secret dibaca dari environment lokal.
V1 hanya memproses pesan teks; foto struk dan approval buttons ditambahkan tahap berikutnya.
"""

from __future__ import annotations

import json
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from typing import Callable

from app.lead import LeadReply


class TelegramError(RuntimeError):
    pass


class TelegramHTTPClient:
    def __init__(self, token: str, *, api_base: str = "https://api.telegram.org"):
        token = (token or "").strip()
        if not token:
            raise ValueError("TELEGRAM_BOT_TOKEN belum diisi.")
        self._base = f"{api_base.rstrip('/')}/bot{token}"

    def _post(self, method: str, data: dict, *, timeout: int = 45):
        body = urllib.parse.urlencode(data).encode("utf-8")
        request = urllib.request.Request(
            f"{self._base}/{method}",
            data=body,
            headers={"Content-Type": "application/x-www-form-urlencoded"},
            method="POST",
        )
        try:
            with urllib.request.urlopen(request, timeout=timeout) as response:
                payload = json.loads(response.read().decode("utf-8"))
        except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as exc:
            raise TelegramError(f"Telegram API gagal: {exc}") from exc
        if not payload.get("ok"):
            raise TelegramError(f"Telegram API menolak permintaan: {payload.get('description', 'unknown error')}")
        return payload.get("result")

    def get_updates(self, *, offset: int | None = None, timeout: int = 30):
        data = {
            "timeout": timeout,
            "allowed_updates": json.dumps(["message"]),
        }
        if offset is not None:
            data["offset"] = offset
        return self._post("getUpdates", data, timeout=timeout + 10)

    def send_message(self, chat_id: int, text: str):
        return self._post(
            "sendMessage",
            {
                "chat_id": chat_id,
                "text": text[:3900],
                "disable_web_page_preview": "true",
            },
            timeout=20,
        )


@dataclass(frozen=True)
class AdminIdentity:
    user_id: int
    chat_id: int | None = None


class TelegramAdminAdapter:
    def __init__(
        self,
        client: TelegramHTTPClient,
        identity: AdminIdentity,
        handler: Callable[[str], LeadReply],
    ):
        self.client = client
        self.identity = identity
        self.handler = handler

    def is_authorized(self, message: dict) -> bool:
        sender = message.get("from") or {}
        chat = message.get("chat") or {}
        if sender.get("id") != self.identity.user_id:
            return False
        if self.identity.chat_id is not None and chat.get("id") != self.identity.chat_id:
            return False
        return True

    def process_update(self, update: dict) -> bool:
        message = update.get("message")
        if not isinstance(message, dict):
            return False
        if not self.is_authorized(message):
            # Sengaja diam untuk akun yang tidak ada di allowlist.
            return False
        text = message.get("text")
        chat = message.get("chat") or {}
        chat_id = chat.get("id")
        if not isinstance(text, str) or not isinstance(chat_id, int):
            return False
        reply = self.handler(text)
        self.client.send_message(chat_id, reply.text)
        return True

    def run_forever(self, *, poll_timeout: int = 30) -> None:
        offset = None
        delay = 1
        while True:
            try:
                updates = self.client.get_updates(offset=offset, timeout=poll_timeout)
                delay = 1
                for update in updates:
                    update_id = update.get("update_id")
                    if isinstance(update_id, int):
                        offset = update_id + 1
                    self.process_update(update)
            except KeyboardInterrupt:
                return
            except TelegramError as exc:
                print(f"Telegram sementara gagal: {exc}", flush=True)
                time.sleep(delay)
                delay = min(delay * 2, 30)
