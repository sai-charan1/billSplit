from __future__ import annotations

import base64
import json
import os
import re
import time
from dataclasses import dataclass
from typing import Any

import httpx

from app.config import load_env

load_env()

GROQ_API_URL = "https://api.groq.com/openai/v1/chat/completions"
GROQ_VISION_MODEL = os.getenv("GROQ_VISION_MODEL", "meta-llama/llama-4-scout-17b-16e-instruct")
GROQ_TEXT_MODEL = os.getenv("GROQ_TEXT_MODEL", "llama-3.3-70b-versatile")

GROQ_MODEL_CHAIN = [
    m.strip()
    for m in os.getenv(
        "GROQ_MODEL_FALLBACKS",
        "meta-llama/llama-4-scout-17b-16e-instruct,llama-3.3-70b-versatile,llama-3.1-8b-instant",
    ).split(",")
    if m.strip()
]


@dataclass
class GroqResult:
    text: str
    model: str


class GroqError(RuntimeError):
    pass


class GroqQuotaError(GroqError):
    pass


def is_groq_configured() -> bool:
    key = os.getenv("GROQ_API_KEY", "").strip()
    return bool(key) and key not in ("", "your_groq_api_key_here")


def _headers() -> dict[str, str]:
    key = os.getenv("GROQ_API_KEY", "").strip()
    if not is_groq_configured():
        raise GroqError(
            "GROQ_API_KEY is not set. Get a free key at https://console.groq.com/keys"
        )
    return {
        "Authorization": f"Bearer {key}",
        "Content-Type": "application/json",
    }


def _strip_json_fence(text: str) -> str:
    cleaned = text.strip()
    if cleaned.startswith("```"):
        cleaned = re.sub(r"^```(?:json)?\s*", "", cleaned)
        cleaned = re.sub(r"\s*```$", "", cleaned)
    return cleaned.strip()


def _parse_json_content(text: str) -> dict[str, Any]:
    cleaned = _strip_json_fence(text)
    return json.loads(cleaned)


def _is_retryable(status: int, body: str) -> bool:
    if status in (408, 429, 500, 502, 503, 504):
        return True
    lower = body.lower()
    return "rate limit" in lower or "quota" in lower or "overloaded" in lower


def _chat_completion(
    messages: list[dict[str, Any]],
    *,
    models: list[str] | None = None,
    max_attempts: int = 2,
) -> GroqResult:
    models = models or GROQ_MODEL_CHAIN
    failures: list[str] = []

    for model in models:
        for attempt in range(max_attempts):
            try:
                payload = {
                    "model": model,
                    "messages": messages,
                    "temperature": 0.1,
                    "response_format": {"type": "json_object"},
                }
                with httpx.Client(timeout=90.0) as client:
                    response = client.post(GROQ_API_URL, headers=_headers(), json=payload)

                if response.status_code >= 400:
                    body = response.text
                    if _is_retryable(response.status_code, body):
                        failures.append(f"{model}: HTTP {response.status_code}")
                        if attempt + 1 < max_attempts:
                            time.sleep(1.5 * (attempt + 1))
                            continue
                        break
                    raise GroqError(f"Groq error on {model}: HTTP {response.status_code} — {body[:200]}")

                data = response.json()
                content = data["choices"][0]["message"]["content"]
                return GroqResult(text=content, model=model)
            except GroqError:
                raise
            except httpx.HTTPError as exc:
                failures.append(f"{model}: {exc}")
                if attempt + 1 < max_attempts:
                    time.sleep(1.5 * (attempt + 1))
                    continue
                break
            except (KeyError, IndexError, json.JSONDecodeError) as exc:
                raise GroqError(f"Invalid Groq response from {model}: {exc}") from exc

    raise GroqQuotaError(
        "Groq free-tier rate limit reached for all models. Wait a minute and retry. "
        f"Details: {'; '.join(failures)}"
    )


def generate_json_text(prompt: str, *, models: list[str] | None = None) -> GroqResult:
    messages = [{"role": "user", "content": prompt}]
    return _chat_completion(messages, models=models or [GROQ_TEXT_MODEL, *GROQ_MODEL_CHAIN])


def generate_json_vision(
    prompt: str,
    image_bytes: bytes,
    mime_type: str = "image/jpeg",
    *,
    models: list[str] | None = None,
) -> GroqResult:
    b64 = base64.b64encode(image_bytes).decode("ascii")
    messages = [
        {
            "role": "user",
            "content": [
                {"type": "text", "text": prompt},
                {
                    "type": "image_url",
                    "image_url": {"url": f"data:{mime_type};base64,{b64}"},
                },
            ],
        }
    ]
    vision_models = models or [GROQ_VISION_MODEL, *GROQ_MODEL_CHAIN]
    return _chat_completion(messages, models=vision_models)
