"""Loader untuk policy format, struktur, dan skill dokumen akademik.

Policy/skill disimpan sebagai Markdown agar mudah dibaca dan diedit manusia, tetapi
juga benar-benar disisipkan ke prompt outline dan draft. Dengan begitu aturan
format tidak hanya menjadi dokumentasi pasif.
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path


_ROOT_DIR = Path(__file__).resolve().parent.parent
_POLICY_DIR = _ROOT_DIR / "policies"
_FORMAT_POLICY_PATH = _POLICY_DIR / "document_format_policy.md"
_TYPE_POLICY_PATH = _POLICY_DIR / "document_type_structure_policy.md"
_SKILL_PATH = _ROOT_DIR / "skills" / "document_academic" / "SKILL.md"
_CITATION_SKILL_PATH = _ROOT_DIR / "skills" / "document_academic" / "CITATION_STYLE.md"


def _read_policy(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8").strip()
    except OSError:
        return ""


@lru_cache(maxsize=1)
def load_document_format_policy() -> str:
    format_policy = _read_policy(_FORMAT_POLICY_PATH)
    type_policy = _read_policy(_TYPE_POLICY_PATH)
    academic_skill = _read_policy(_SKILL_PATH)
    citation_skill = _read_policy(_CITATION_SKILL_PATH)

    parts = [text for text in (format_policy, type_policy, academic_skill, citation_skill) if text]
    if not parts:
        return (
            "Deteksi jenis dokumen terlebih dahulu. Untuk Makalah gunakan struktur BAB I/BAB II/BAB III "
            "dengan hierarki A., 1., a.; untuk KTI gunakan 1, 1.1, 1.1.1; untuk Skripsi utamakan "
            "pedoman kampus. Jika tidak ada pedoman, gunakan fallback akademik: paragraf justify, "
            "first-line indent 1,27 cm, dan sitasi footnote + daftar pustaka yang konsisten. "
            "Instruksi guru/dosen/sekolah/kampus mengalahkan aturan default."
        )

    # Memuat policy + skill aktif tanpa membiarkan prompt tumbuh tanpa batas.
    return "\n\n---\n\n".join(parts)[:38000]


def policy_path() -> str:
    return str(_FORMAT_POLICY_PATH)


def type_policy_path() -> str:
    return str(_TYPE_POLICY_PATH)


def skill_path() -> str:
    return str(_SKILL_PATH)


def citation_skill_path() -> str:
    return str(_CITATION_SKILL_PATH)
