"""Abstraksi provider model untuk agent Taqi AI.

Provider layer menjaga agent tidak tergantung langsung pada SDK/vendor tertentu.
Semua secret tetap dibaca dari environment lokal, tidak disimpan di repo.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True)
class ModelReply:
    status: str
    text: str
    provider: str
    model: str
    input_tokens: int = 0
    output_tokens: int = 0


class ModelProvider(Protocol):
    @property
    def configured(self) -> bool: ...

    @property
    def provider_name(self) -> str: ...

    @property
    def model_name(self) -> str: ...

    def generate(
        self,
        messages: list[dict[str, str]],
        *,
        max_tokens: int = 1200,
        temperature: float = 0.4,
        timeout: int = 45,
    ) -> ModelReply: ...
