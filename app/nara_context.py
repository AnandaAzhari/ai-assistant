"""Load maintained Nara instructions; never derive instruction paths from a chat."""

from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def load_nara_identity() -> str:
    return (ROOT / "agents/document_agent.md").read_text(encoding="utf-8").strip()


def load_nara_conversation() -> str:
    return (ROOT / "skills/document_academic/CONVERSATION.md").read_text(encoding="utf-8").strip()
