"""WhatsApp Customer Adapter — Fase 4 (`docs/roadmap_customer_channel_v1.md`).

Provider: WhatsApp Business Platform Cloud API resmi dari Meta, langsung, bukan lewat
BSP pihak ketiga (Qiscus/Wati/360dialog/dst). Alasannya konsisten dengan prinsip
pay-as-you-go yang sudah dipakai untuk provider AI di `docs/core_architecture.md`:
per Juli 2025 Meta memakai skema per-pesan, dan pesan balasan dalam jendela sesi 24 jam
("service"/non-template, yaitu hampir semua balasan reaktif ke pelanggan yang baru saja
menghubungi kita) saat ini GRATIS di Cloud API resmi — tanpa biaya langganan bulanan
tambahan dari BSP. BSP pihak ketiga tetap bisa dipertimbangkan nanti kalau volume pesan
marketing/broadcast membesar dan onboarding non-teknis jadi prioritas.

Berbeda dari Telegram (polling lewat getUpdates), WhatsApp Cloud API bersifat WEBHOOK:
Meta yang mengirim POST ke URL publik milik kita. Modul ini SENGAJA tidak menjalankan
server HTTP sendiri — lihat `app/web_admin.py` untuk pola `http.server` stdlib yang
sudah dipakai di repo ini; endpoint publik sungguhan (`whatsapp_main.py`, mengikuti pola
yang sama) adalah langkah berikutnya setelah verifikasi bisnis dan token asli siap dari
Meta Business Manager. `WhatsAppCustomerAdapter.process_webhook_event()` di sini hanya
menerima payload yang SUDAH diverifikasi tanda tangannya (`verify_webhook_signature`)
dan sudah berbentuk dict, supaya adapter tetap independen dari framework web apa pun.

WAJIB dan tidak bisa dilewati: setiap pesan WhatsApp masuk melalui Fase 1-3
(`app/trust_layer.py` lalu `app/approval_gate.py` via
`LeadAgent.handle_customer_message()`) sebelum dibalas — tidak pernah langsung ke
agent lain, konsisten dengan "Zero trust untuk input pelanggan" di
`policies/security_policy.md`.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import urllib.error
import urllib.request
from dataclasses import dataclass

from app.lead import LeadAgent, LeadReply
from app.telegram import text_chunks

WHATSAPP_TEXT_LIMIT = 4096  # batas resmi WhatsApp Cloud API untuk satu pesan teks


class WhatsAppError(RuntimeError):
    def __init__(self, message: str, *, retryable: bool = True):
        super().__init__(message)
        self.retryable = retryable


class WhatsAppHTTPClient:
    """Klien HTTP minimal untuk WhatsApp Business Platform Cloud API resmi (Meta)."""

    def __init__(self, access_token: str, phone_number_id: str, *,
                 api_base: str = "https://graph.facebook.com", api_version: str = "v21.0"):
        access_token = (access_token or "").strip()
        phone_number_id = (phone_number_id or "").strip()
        if not access_token or any(char.isspace() for char in access_token):
            raise ValueError("WHATSAPP_API_TOKEN kosong atau mengandung spasi.")
        if not phone_number_id or not phone_number_id.isdigit():
            raise ValueError("WHATSAPP_PHONE_NUMBER_ID harus berupa ID angka dari Meta Business Manager.")
        self._access_token = access_token
        self._base = f"{api_base.rstrip('/')}/{api_version}/{phone_number_id}/messages"

    def send_text(self, to: str, text: str) -> None:
        if not text:
            return
        body = json.dumps({
            "messaging_product": "whatsapp",
            "to": to,
            "type": "text",
            "text": {"body": text, "preview_url": False},
        }).encode("utf-8")
        request = urllib.request.Request(
            self._base, data=body, method="POST",
            headers={"Authorization": f"Bearer {self._access_token}", "Content-Type": "application/json"},
        )
        try:
            with urllib.request.urlopen(request, timeout=20) as response:
                response.read()
        except urllib.error.HTTPError as exc:
            retryable = exc.code == 429 or exc.code >= 500
            raise WhatsAppError(f"WhatsApp menolak pengiriman pesan (HTTP {exc.code}).", retryable=retryable) from None
        except (urllib.error.URLError, TimeoutError, OSError):
            raise WhatsAppError("Koneksi ke WhatsApp terputus atau melewati batas waktu.") from None


def verify_webhook_challenge(*, mode: str, token: str, challenge: str, expected_verify_token: str) -> str | None:
    """Tangani handshake verifikasi webhook GET dari Meta saat endpoint didaftarkan.

    Kembalikan `challenge` untuk dikirim balik sebagai body respons bila valid,
    atau None bila permintaan harus ditolak (mode atau token tidak cocok).
    """
    if mode != "subscribe":
        return None
    if not expected_verify_token or not hmac.compare_digest(token or "", expected_verify_token):
        return None
    return challenge


def verify_webhook_signature(payload_bytes: bytes, signature_header: str, app_secret: str) -> bool:
    """Verifikasi header `X-Hub-Signature-256` dari Meta sebelum payload dipercaya.

    Webhook yang gagal verifikasi HARUS ditolak, bukan diproses "untuk jaga-jaga" —
    payload tanpa tanda tangan valid dianggap input tidak tepercaya, konsisten dengan
    "Zero trust untuk input pelanggan" di `policies/security_policy.md`.
    """
    if not signature_header or not signature_header.startswith("sha256="):
        return False
    expected = hmac.new((app_secret or "").encode("utf-8"), payload_bytes, hashlib.sha256).hexdigest()
    provided = signature_header[len("sha256="):]
    return hmac.compare_digest(expected, provided)


@dataclass(frozen=True)
class InboundWhatsAppMessage:
    sender_id: str
    text: str
    has_attachment: bool
    message_id: str


def extract_inbound_messages(payload: dict) -> list[InboundWhatsAppMessage]:
    """Ambil daftar pesan masuk dari payload webhook Meta (bisa berisi beberapa event sekaligus).

    Event non-pesan (status pengiriman "delivered"/"read", dsb.) dan tipe pesan yang
    belum dipahami (location, contacts, interactive, dst.) sengaja diabaikan di sini,
    bukan diproses tanpa pemahaman jelas.
    """
    messages: list[InboundWhatsAppMessage] = []
    if not isinstance(payload, dict):
        return messages
    for entry in payload.get("entry") or []:
        if not isinstance(entry, dict):
            continue
        for change in entry.get("changes") or []:
            if not isinstance(change, dict):
                continue
            value = change.get("value")
            if not isinstance(value, dict):
                continue
            for raw_message in value.get("messages") or []:
                if not isinstance(raw_message, dict):
                    continue
                sender_id = str(raw_message.get("from") or "").strip()
                message_id = str(raw_message.get("id") or "").strip()
                message_type = raw_message.get("type")
                if not sender_id:
                    continue
                if message_type == "text":
                    text_body = raw_message.get("text")
                    text = str(text_body.get("body") or "") if isinstance(text_body, dict) else ""
                    messages.append(InboundWhatsAppMessage(sender_id, text, False, message_id))
                elif message_type in {"image", "document", "audio", "video", "sticker"}:
                    # Isi lampiran belum diproses otomatis (lihat
                    # policies/attachment_link_security.md); kehadirannya cukup jadi
                    # sinyal positif untuk Trust Layer, isinya tidak diunduh di sini.
                    media = raw_message.get(message_type)
                    caption = str(media.get("caption") or "") if isinstance(media, dict) else ""
                    messages.append(InboundWhatsAppMessage(sender_id, caption, True, message_id))
    return messages


class WhatsAppCustomerAdapter:
    """Menjembatani webhook WhatsApp yang sudah diverifikasi ke LeadAgent.handle_customer_message()."""

    def __init__(self, client: WhatsAppHTTPClient, lead: LeadAgent):
        self.client = client
        self.lead = lead

    def process_webhook_event(self, payload: dict) -> list[LeadReply]:
        replies: list[LeadReply] = []
        for message in extract_inbound_messages(payload):
            reply = self.lead.handle_customer_message(
                message.sender_id, message.text, has_attachment=message.has_attachment,
            )
            replies.append(reply)
            for chunk in text_chunks(reply.text, WHATSAPP_TEXT_LIMIT):
                try:
                    self.client.send_text(message.sender_id, chunk)
                except WhatsAppError as exc:
                    print(f"Balasan WhatsApp belum terkirim ke {message.sender_id}: {exc}", flush=True)
                    break
        return replies
