"""
Local CLI auth session storage.
"""

import json
import os
from datetime import datetime
from pathlib import Path
from typing import Any, Optional


def get_auth_session_path() -> Path:
    env_path = os.getenv("ERLANGSHEN_AUTH_FILE")
    if env_path:
        return Path(env_path).expanduser()
    return Path("~/.erlangshen/auth.json").expanduser()


def load_auth_session() -> dict[str, Any]:
    path = get_auth_session_path()
    if not path.exists():
        return {}
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
            return data if isinstance(data, dict) else {}
    except (OSError, json.JSONDecodeError):
        return {}


def save_auth_session(session: dict[str, Any]) -> None:
    path = get_auth_session_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        **session,
        "saved_at": datetime.now().isoformat(timespec="seconds"),
    }
    with open(path, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)
    try:
        os.chmod(path, 0o600)
    except OSError:
        pass


def clear_auth_session() -> None:
    path = get_auth_session_path()
    try:
        path.unlink()
    except FileNotFoundError:
        pass


def get_saved_token() -> Optional[str]:
    token = load_auth_session().get("token")
    return str(token).strip() if token else None


def format_bearer_token(token: str) -> str:
    token = token.strip()
    if token.lower().startswith("bearer "):
        return token
    return f"Bearer {token}"
