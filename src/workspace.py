"""
Project workspace permission store for the CLI sandbox.
"""

from __future__ import annotations

import json
import os
from datetime import datetime
from pathlib import Path
from typing import Any


def workspace_store_path() -> Path:
    env_path = os.getenv("ERLANGSHEN_WORKSPACE_FILE")
    if env_path:
        return Path(env_path).expanduser()
    return Path("~/.erlangshen/workspaces.json").expanduser()


def resolve_workspace_path(path: str | None = None) -> Path:
    raw = path or os.getenv("ERLANGSHEN_WORKSPACE")
    if not raw:
        store = load_workspace_store()
        raw = store.get("active_workspace") or os.getcwd()
    return Path(raw).expanduser().resolve()


def load_workspace_store() -> dict[str, Any]:
    path = workspace_store_path()
    if not path.exists():
        return {"workspaces": {}}
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
            return data if isinstance(data, dict) else {"workspaces": {}}
    except (OSError, json.JSONDecodeError):
        return {"workspaces": {}}


def save_workspace_store(store: dict[str, Any]) -> None:
    path = workspace_store_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(store, f, ensure_ascii=False, indent=2)
    try:
        os.chmod(path, 0o600)
    except OSError:
        pass


def workspace_status(path: str | Path | None = None) -> dict[str, Any]:
    workspace = resolve_workspace_path(str(path) if path else None)
    store = load_workspace_store()
    entry = (store.get("workspaces") or {}).get(str(workspace)) or {}
    return {
        "path": str(workspace),
        "allowed": bool(entry.get("allowed")),
        "mode": entry.get("mode") or ("read_write" if entry.get("allowed") else "restricted"),
        "approved_at": entry.get("approved_at"),
    }


def recent_workspaces(limit: int = 5) -> list[dict[str, Any]]:
    store = load_workspace_store()
    workspaces = store.get("workspaces") or {}
    active = str(store.get("active_workspace") or "")
    paths = sorted(
        [path for path in workspaces.keys() if path and path != active],
        key=lambda path: str((workspaces.get(path) or {}).get("approved_at") or ""),
        reverse=True,
    )
    result = []
    seen = set()
    for raw_path in [active, *paths]:
        if not raw_path or raw_path in seen:
            continue
        seen.add(raw_path)
        path = Path(raw_path).expanduser()
        if not path.exists() or not path.is_dir():
            continue
        status = workspace_status(path)
        result.append(status)
        if len(result) >= limit:
            break
    return result


def approve_workspace(path: str | Path | None = None, mode: str = "read_write") -> dict[str, Any]:
    workspace = resolve_workspace_path(str(path) if path else None)
    store = load_workspace_store()
    store["active_workspace"] = str(workspace)
    workspaces = store.setdefault("workspaces", {})
    workspaces[str(workspace)] = {
        "allowed": True,
        "mode": mode,
        "approved_at": datetime.now().isoformat(timespec="seconds"),
    }
    save_workspace_store(store)
    return workspace_status(workspace)


def select_workspace(path: str | Path | None = None) -> dict[str, Any]:
    workspace = resolve_workspace_path(str(path) if path else None)
    store = load_workspace_store()
    store["active_workspace"] = str(workspace)
    store.setdefault("workspaces", {})
    save_workspace_store(store)
    return workspace_status(workspace)


def revoke_workspace(path: str | Path | None = None) -> dict[str, Any]:
    workspace = resolve_workspace_path(str(path) if path else None)
    store = load_workspace_store()
    store["active_workspace"] = str(workspace)
    workspaces = store.setdefault("workspaces", {})
    workspaces[str(workspace)] = {
        "allowed": False,
        "mode": "restricted",
        "approved_at": None,
    }
    save_workspace_store(store)
    return workspace_status(workspace)


def ensure_inside_workspace(target: str | Path, workspace: str | Path | None = None) -> Path:
    root = resolve_workspace_path(str(workspace) if workspace else None)
    path = Path(target).expanduser().resolve()
    try:
        path.relative_to(root)
    except ValueError as exc:
        raise PermissionError(f"路径不在已授权项目文件夹内: {path}") from exc
    return path
