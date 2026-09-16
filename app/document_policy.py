"""Loader untuk policy format dan struktur dokumen.

Policy disimpan sebagai Markdown agar mudah dibaca/diedit manusia, tetapi juga
benar-benar disisipkan ke prompt outline dan draft. Dengan begitu aturan format
tidak hanya menjadi dokumentasi pasif.
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path


_POLICY_DIR = Path(__file__).resolve().parent.parent / "policies"
_FORMAT_POLICY_PATH = _POLICY_DIR / "document_format_policy.md"
_TYPE_POLICY_PATH = _POLICY_DIR / "document_type_structure_policy.md"


def _read_policy(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8").strip()
    except OSError:
        return ""


@lru_cache(maxsize=1)
def load_document_format_policy() -> str:
    format_policy = _read_policy(_FORMAT_POLICY_PATH)
    type_policy = _read_policy(_TYPE_POLICY_PATH)

    parts = [text for text in (format_policy, type_policy) if text]
    if not parts:
        return (
            "Deteksi jenis dokumen terlebih dahulu. Untuk makalah gunakan struktur BAB I, BAB II, BAB III "
            "dengan heading 1.1 dan 1.1.1; untuk KTI gunakan 1, 1.1, 1.1.1; untuk skripsi utamakan "
            "pedoman kampus. Instruksi guru/dosen/sekolah/kampus mengalahkan aturan default."
        )

    # Cukup besar untuk dua policy, tetapi tetap membatasi prompt agar tidak membengkak.
    return "\n\n---\n\n".join(parts)[:22000]


def policy_path() -> str:
    return str(_FORMAT_POLICY_PATH)


def type_policy_path() -> str:
    return str(_TYPE_POLICY_PATH)
