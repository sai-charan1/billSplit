from __future__ import annotations

import io

from PIL import Image


def extract_text_from_image(image_bytes: bytes) -> str | None:
    """Local OCR via Tesseract (free, no API). Returns None if unavailable."""
    try:
        import pytesseract
    except ImportError:
        return None

    try:
        image = Image.open(io.BytesIO(image_bytes))
        if image.mode not in ("RGB", "L"):
            image = image.convert("RGB")
        text = pytesseract.image_to_string(image)
        cleaned = text.strip()
        return cleaned if len(cleaned) >= 20 else None
    except Exception:
        return None
