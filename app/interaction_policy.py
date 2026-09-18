"""Aturan interaksi channel Taqi AI — Input Gateway pelanggan (Fase 3).

Prinsip permanen:
- slash command = admin/internal
- natural language = pelanggan

Modul ini menjadi acuan bersama untuk Customer Webapp, WhatsApp, dan adapter
pelanggan lain agar command teknis tidak bocor ke pengalaman pelanggan, dan
menjadi gateway yang memutuskan asal channel (admin/pelanggan/tidak dikenal)
sebelum pesan diteruskan ke `app/lead.py`
(`LeadAgent.handle_admin_message` vs `LeadAgent.handle_customer_message`).

Fail-safe: channel yang tidak terdaftar TIDAK PERNAH diperlakukan sebagai admin
maupun pelanggan secara default — pesannya ditolak, konsisten dengan
"Zero trust untuk input pelanggan" di `policies/security_policy.md`.
"""

from __future__ import annotations

from dataclasses import dataclass


ADMIN_COMMAND_PREFIX = "/"

ADMIN_CHANNELS = {"telegram_admin", "web_admin", "desktop"}
CUSTOMER_CHANNELS = {"whatsapp", "web_customer"}

CUSTOMER_TERM_MAP = {
    "requirement": "data yang diperlukan",
    "requirements": "data yang diperlukan",
    "outline": "kerangka makalah",
    "draft": "isi makalah",
    "source registry": "daftar sumber",
    "citation": "kutipan/sumber",
    "citations": "kutipan/sumber",
    "footnote": "catatan kaki",
    "footnotes": "catatan kaki",
    "generate": "buat",
}


def is_admin_command(message: str) -> bool:
    """True bila pesan memakai slash command internal/admin."""
    return (message or "").lstrip().startswith(ADMIN_COMMAND_PREFIX)


def customer_friendly_term(value: str) -> str:
    """Mengubah istilah internal sederhana menjadi kata yang lebih mudah dipahami."""
    clean = (value or "").strip()
    return CUSTOMER_TERM_MAP.get(clean.casefold(), clean)


def customer_channel_accepts(message: str) -> bool:
    """Customer-facing channel tidak menerima slash command sebagai UX normal."""
    return bool((message or "").strip()) and not is_admin_command(message)


@dataclass(frozen=True)
class RouteDecision:
    origin: str  # "admin" | "customer" | "rejected"
    reason: str


def classify_channel(channel: str) -> str:
    """Klasifikasikan nama channel menjadi "admin", "customer", atau "unknown".

    Channel baru harus didaftarkan secara eksplisit ke ADMIN_CHANNELS/CUSTOMER_CHANNELS
    sebelum dipakai; ini mencegah adapter baru yang belum ditinjau otomatis mendapat
    hak admin atau memotong Security & Trust Layer pelanggan.
    """
    normalized = (channel or "").strip().casefold()
    if normalized in ADMIN_CHANNELS:
        return "admin"
    if normalized in CUSTOMER_CHANNELS:
        return "customer"
    return "unknown"


def route_inbound_message(channel: str, message: str) -> RouteDecision:
    """Putuskan asal pesan masuk sebelum diteruskan ke Lead Agent.

    - Channel tidak dikenal: ditolak (fail-safe), tidak pernah diperlakukan sebagai
      admin maupun pelanggan secara default.
    - Command admin (`/...`) yang datang dari channel pelanggan: ditolak dan
      diperlakukan sebagai sinyal mencurigakan (bukan sekadar diabaikan), karena ini
      adalah pola percobaan mengambil alih hak admin dari jalur yang tidak tepercaya.
    """
    origin = classify_channel(channel)
    if origin == "unknown":
        return RouteDecision(
            "rejected",
            f"Channel '{channel}' belum terdaftar sebagai admin maupun pelanggan; pesan ditolak demi keamanan.",
        )
    if origin == "customer" and is_admin_command(message):
        return RouteDecision(
            "rejected",
            "Percobaan memakai command admin dari channel pelanggan; diperlakukan sebagai sinyal mencurigakan.",
        )
    return RouteDecision(origin, f"Dirutekan sebagai pesan {origin} dari channel '{channel}'.")
