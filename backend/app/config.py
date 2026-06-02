from __future__ import annotations

from pathlib import Path

from dotenv import load_dotenv

# backend/app/config.py -> backend -> project root
PROJECT_ROOT = Path(__file__).resolve().parents[2]
BACKEND_ROOT = Path(__file__).resolve().parents[1]


def load_env() -> None:
    """Load .env from project root, backend folder, then cwd."""
    for path in (PROJECT_ROOT / ".env", BACKEND_ROOT / ".env", Path.cwd() / ".env"):
        if path.is_file():
            load_dotenv(path, override=True)
