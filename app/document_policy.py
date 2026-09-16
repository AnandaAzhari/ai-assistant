"""Loader untuk policy format dokumen.

Policy disimpan sebagai Markdown agar mudah dibaca/diedit manusia, tetapi juga
benar-benar disisipkan ke prompt outline dan draft. Dengan begitu aturan format
tidak hanya menjadi dokumentasi pasif.
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path


_POLICY_PATH = Path(__file__).resolve().parent.parent / "policies" / "document_format_policy.md"


@lru_cache(maxsize=1)
def load_document_format_policy() -> str:
    try:
        text = _POLICY_PATH.read_text(encoding="utf-8").strip()
    except OSError:
        return (
            "Gunakan struktur makalah standar BAB I, BAB II, BAB III; heading turunan "
            "harus bernomor 1.1, 1.1.1, dst.; target halaman harus dihormati. "
            "Instruksi guru/dosen/sekolah/kampus mengalahkan aturan default."
        )
    return text[:12000]


def policy_path() -> str:
    return str(_POLICY_PATH)
