import os
from pathlib import Path


def _strip_wrapped_quotes(value: str) -> str:
    text = (value or "").strip()
    if len(text) >= 2 and ((text[0] == '"' and text[-1] == '"') or (text[0] == "'" and text[-1] == "'")):
        return text[1:-1]
    return text


def load_local_env() -> None:
    """Load backend .env/.ENV into process environment (without overriding existing vars)."""
    root = Path(__file__).resolve().parents[1]
    candidates = [root / ".env", root / ".ENV"]

    for env_path in candidates:
        if not env_path.exists():
            continue

        for raw_line in env_path.read_text(encoding="utf-8").splitlines():
            line = raw_line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            key = key.strip()
            if not key:
                continue
            os.environ.setdefault(key, _strip_wrapped_quotes(value))

        break
