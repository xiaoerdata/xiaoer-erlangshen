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


def get_auth_key_path() -> Path:
    env_path = os.getenv("ERLANGSHEN_AUTH_KEY_FILE")
    if env_path:
        return Path(env_path).expanduser()
    session_path = get_auth_session_path()
    if os.getenv("ERLANGSHEN_AUTH_FILE"):
        return session_path.with_suffix(session_path.suffix + ".key")
    return session_path.with_name("auth.key")


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
    sanitized = {
        key: value
        for key, value in session.items()
        if str(key).lower() not in {"password", "plain_password", "passwd"}
    }
    payload = {
        **sanitized,
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


def encrypt_auth_password(password: str) -> dict[str, str]:
    password = str(password or "")
    if not password:
        return {}
    fernet = _auth_fernet(create=True)
    if fernet is None:
        return {}
    return {
        "scheme": "fernet:v1",
        "ciphertext": fernet.encrypt(password.encode("utf-8")).decode("ascii"),
    }


def decrypt_auth_password(session: dict[str, Any]) -> Optional[str]:
    if not isinstance(session, dict):
        return None
    payload = session.get("password_encrypted") or session.get("encrypted_password")
    if not isinstance(payload, dict):
        return None
    if payload.get("scheme") != "fernet:v1":
        return None
    ciphertext = payload.get("ciphertext")
    if not isinstance(ciphertext, str) or not ciphertext:
        return None
    fernet = _auth_fernet(create=False)
    if fernet is None:
        return None
    try:
        return fernet.decrypt(ciphertext.encode("ascii")).decode("utf-8")
    except Exception:
        return None


def format_bearer_token(token: str) -> str:
    token = token.strip()
    if token.lower().startswith("bearer "):
        return token
    return f"Bearer {token}"


def _auth_fernet(*, create: bool):
    try:
        from cryptography.fernet import Fernet
    except Exception:
        return None
    key_path = get_auth_key_path()
    key = _read_auth_key(key_path)
    if not key and create:
        key_path.parent.mkdir(parents=True, exist_ok=True)
        key = Fernet.generate_key()
        with open(key_path, "wb") as f:
            f.write(key)
        try:
            os.chmod(key_path, 0o600)
        except OSError:
            pass
    if not key:
        return None
    try:
        return Fernet(key)
    except Exception:
        return None


def _read_auth_key(path: Path) -> bytes:
    try:
        key = path.read_bytes().strip()
    except OSError:
        return b""
    try:
        os.chmod(path, 0o600)
    except OSError:
        pass
    return key
