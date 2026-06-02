from __future__ import annotations

import hashlib
import os
import re
import time
from dataclasses import dataclass
from typing import Any

from google import genai
from google.genai import errors as genai_errors
from google.genai import types

from app.config import load_env

load_env()

DEFAULT_MODELS = (
    "gemini-2.5-flash",
    "gemini-2.0-flash-lite",
    "gemini-2.0-flash",
)

JSON_CONFIG = types.GenerateContentConfig(
    temperature=0.1,
    response_mime_type="application/json",
)


@dataclass
class LLMResult:
    text: str
    model: str


class QuotaExhaustedError(RuntimeError):
    """All Gemini models exhausted free-tier quota."""


class LLMServiceError(RuntimeError):
    """Gemini call failed for a non-quota reason."""


def is_valid_key_format(api_key: str) -> bool:
    return api_key.startswith("AIza") or api_key.startswith("AQ.")


def get_client() -> genai.Client:
    api_key = os.getenv("GEMINI_API_KEY", "").strip()
    if not api_key or api_key == "your_gemini_api_key_here":
        raise RuntimeError(
            "GEMINI_API_KEY is not set. Add it to assignment/.env — "
            "https://aistudio.google.com/app/apikey"
        )
    if not is_valid_key_format(api_key):
        raise RuntimeError(
            "GEMINI_API_KEY format not recognized. Copy the full key from "
            "https://aistudio.google.com/app/apikey (starts with AIza or AQ.)."
        )
    return genai.Client(api_key=api_key)


def model_fallback_chain() -> list[str]:
    primary = os.getenv("GEMINI_MODEL", "gemini-2.5-flash").strip()
    extras = os.getenv("GEMINI_MODEL_FALLBACKS", ",".join(DEFAULT_MODELS))
    chain: list[str] = []
    for model in [primary, *extras.split(",")]:
        model = model.strip()
        if model and model not in chain:
            chain.append(model)
    return chain


def _retry_delay_seconds(exc: genai_errors.ClientError) -> float | None:
    message = str(exc.details or exc.message or "")
    match = re.search(r"retry in ([0-9.]+)s", message, re.IGNORECASE)
    if match:
        return min(float(match.group(1)) + 0.5, 60.0)
    return None


def _is_retryable_error(exc: genai_errors.ClientError) -> bool:
    if exc.code in (429, 503, 408):
        return True
    message = str(exc.details or exc.message or "").lower()
    return any(
        token in message
        for token in ("resource_exhausted", "quota", "unavailable", "high demand", "overloaded")
    )


def generate_json(
    client: genai.Client,
    contents: str | list[Any],
    *,
    max_attempts_per_model: int = 2,
) -> LLMResult:
    """Try models in fallback order; retry transient errors with server-suggested delay."""
    failures: list[str] = []

    for model in model_fallback_chain():
        for attempt in range(max_attempts_per_model):
            try:
                response = client.models.generate_content(
                    model=model,
                    contents=contents,
                    config=JSON_CONFIG,
                )
                return LLMResult(text=response.text or "{}", model=model)
            except genai_errors.ClientError as exc:
                if _is_retryable_error(exc):
                    delay = _retry_delay_seconds(exc)
                    if attempt + 1 < max_attempts_per_model and delay is not None:
                        time.sleep(delay)
                        continue
                    if attempt + 1 < max_attempts_per_model:
                        time.sleep(1.5 * (attempt + 1))
                        continue
                    failures.append(f"{model}: {exc.code} {exc.status or 'UNAVAILABLE'}")
                    break
                raise LLMServiceError(f"Gemini error on {model}: {exc.message or exc}") from exc
            except Exception as exc:
                raise LLMServiceError(f"Gemini request failed on {model}: {exc}") from exc

    raise QuotaExhaustedError(
        "Gemini API unavailable or free-tier quota exhausted for all configured models "
        f"({', '.join(model_fallback_chain())}). "
        "Wait ~1 minute and retry, use Demo mode (no API), or create a new API key in a "
        "fresh Google Cloud project at https://aistudio.google.com/app/apikey. "
        f"Details: {'; '.join(failures)}"
    )
