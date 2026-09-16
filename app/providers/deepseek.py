"""DeepSeek provider via OpenAI-compatible Chat Completions API.

Default model `deepseek-flash` mengarah ke DeepSeek V4.1 Flash.
Implementasi memakai Python standard library agar runtime tetap ringan.
"""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.request

from app.providers.base import ModelReply


class DeepSeekProvider:
    def __init__(
        self,
        api_key: str = "",
        model: str = "deepseek-flash",
        base_url: str = "https://api.deepseek.com",
    ):
        self.api_key = (api_key or "").strip()
        self.model = (model or "deepseek-flash").strip() or "deepseek-flash"
        self.base_url = (base_url or "https://api.deepseek.com").strip().rstrip("/")

    @classmethod
    def from_env(cls) -> "DeepSeekProvider":
        return cls(
            api_key=os.environ.get("DEEPSEEK_API_KEY", ""),
            model=os.environ.get("DEEPSEEK_MODEL", "deepseek-flash"),
            base_url=os.environ.get("DEEPSEEK_BASE_URL", "https://api.deepseek.com"),
        )

    @property
    def configured(self) -> bool:
        return bool(self.api_key and self.base_url.startswith("https://"))

    @property
    def provider_name(self) -> str:
        return "DeepSeek"

    @property
    def model_name(self) -> str:
        return self.model

    def generate(
        self,
        messages: list[dict[str, str]],
        *,
        max_tokens: int = 1200,
        temperature: float = 0.4,
        timeout: int = 45,
    ) -> ModelReply:
        if not self.configured:
            return ModelReply(
                "belum_dikonfigurasi",
                "DeepSeek belum dikonfigurasi. Isi DEEPSEEK_API_KEY pada file .env lokal.",
                self.provider_name,
                self.model_name,
            )
        if not messages:
            return ModelReply("gagal", "Pesan model kosong.", self.provider_name, self.model_name)

        endpoint = self.base_url + "/chat/completions"
        payload = {
            "model": self.model,
            "messages": messages,
            "max_tokens": max(1, min(int(max_tokens), 8000)),
            "temperature": max(0.0, min(float(temperature), 2.0)),
        }
        data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        request = urllib.request.Request(
            endpoint,
            data=data,
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json; charset=utf-8",
                "Accept": "application/json",
            },
            method="POST",
        )

        try:
            with urllib.request.urlopen(request, timeout=timeout) as response:
                raw = response.read().decode("utf-8")
            result = json.loads(raw)
        except urllib.error.HTTPError as exc:
            return ModelReply(
                "gagal",
                f"DeepSeek API menolak request (HTTP {exc.code}). Periksa API key, saldo, dan model.",
                self.provider_name,
                self.model_name,
            )
        except (urllib.error.URLError, TimeoutError) as exc:
            return ModelReply(
                "gagal",
                f"Tidak dapat terhubung ke DeepSeek API: {exc}.",
                self.provider_name,
                self.model_name,
            )
        except (json.JSONDecodeError, UnicodeDecodeError, TypeError, ValueError):
            return ModelReply(
                "gagal",
                "Respons DeepSeek API tidak dapat dibaca.",
                self.provider_name,
                self.model_name,
            )

        try:
            content = result["choices"][0]["message"]["content"]
        except (KeyError, IndexError, TypeError):
            return ModelReply(
                "gagal",
                "DeepSeek API tidak mengembalikan jawaban teks yang diharapkan.",
                self.provider_name,
                self.model_name,
            )
        if not isinstance(content, str) or not content.strip():
            return ModelReply("gagal", "Jawaban DeepSeek kosong.", self.provider_name, self.model_name)

        usage = result.get("usage") if isinstance(result, dict) else {}
        if not isinstance(usage, dict):
            usage = {}
        return ModelReply(
            "berhasil",
            content.strip(),
            self.provider_name,
            self.model_name,
            int(usage.get("prompt_tokens", 0) or 0),
            int(usage.get("completion_tokens", 0) or 0),
        )
