"""Aturan interaksi channel Taqi AI.

Prinsip permanen:
- slash command = admin/internal
- natural language = pelanggan

Modul kecil ini menjadi acuan bersama untuk Customer Webapp, WhatsApp, dan adapter
pelanggan lain agar command teknis tidak bocor ke pengalaman pelanggan.
"""

from __future__ import annotations


ADMIN_COMMAND_PREFIX = "/"

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
