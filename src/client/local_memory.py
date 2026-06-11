"""Local, redacted memory store for the Erlangshen CLI.

The store is intentionally small and dependency-free. It persists compact
cross-session notes on the user's machine and never syncs API keys or tokens to
the Erlangshen server.
"""

from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Iterable


SECRET_RE = re.compile(
    r"(?i)(sk-[a-z0-9_\-]{12,}|npm_[a-z0-9_\-]{12,}|"
    r"(?:api[_-]?key|token|authorization|password|secret)\s*[:=]\s*[^\s,;]+)"
)

DEFAULT_MEMORY_LIMIT = 80


def default_memory_path() -> Path:
    configured = os.getenv("ERLANGSHEN_MEMORY_FILE")
    if configured:
        return Path(configured).expanduser()
    return Path.home() / ".erlangshen" / "memory.json"


def redact_secrets(text: str) -> str:
    return SECRET_RE.sub("[hidden-secret]", str(text or ""))


def compact_text(text: str, limit: int = 360) -> str:
    value = " ".join(redact_secrets(text).split())
    if len(value) <= limit:
        return value
    return value[: max(0, limit - 1)].rstrip() + "..."


def extract_tags(*texts: str) -> list[str]:
    haystack = " ".join(texts)
    candidates = [
        "A股",
        "港股",
        "美股",
        "恒生指数",
        "恒生科技指数",
        "沪深300",
        "创业板",
        "黄金",
        "原油",
        "美元",
        "债券",
        "AI",
        "半导体",
        "红利",
        "新能源",
        "地缘政治",
        "MCP",
        "图表",
        "报告",
    ]
    return [item for item in candidates if item in haystack][:8]


@dataclass
class MemoryStats:
    count: int
    path: Path
    updated_at: str


class LocalMemoryStore:
    """Small JSON-backed memory store used by the npm CLI client."""

    def __init__(self, path: str | Path | None = None, limit: int = DEFAULT_MEMORY_LIMIT):
        self.path = Path(path).expanduser() if path else default_memory_path()
        self.limit = max(8, int(limit or DEFAULT_MEMORY_LIMIT))

    def load(self) -> dict:
        if not self.path.exists():
            return {"version": 1, "updated_at": "", "memories": []}
        try:
            with open(self.path, "r", encoding="utf-8") as handle:
                data = json.load(handle)
        except (OSError, json.JSONDecodeError, TypeError, ValueError):
            return {"version": 1, "updated_at": "", "memories": []}
        memories = data.get("memories") if isinstance(data, dict) else []
        if not isinstance(memories, list):
            memories = []
        return {
            "version": 1,
            "updated_at": str(data.get("updated_at") or "") if isinstance(data, dict) else "",
            "memories": [item for item in memories if isinstance(item, dict)][-self.limit:],
        }

    def save(self, data: dict) -> None:
        memories = data.get("memories") if isinstance(data, dict) else []
        if not isinstance(memories, list):
            memories = []
        payload = {
            "version": 1,
            "updated_at": datetime.now().isoformat(timespec="seconds"),
            "memories": memories[-self.limit:],
        }
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with open(self.path, "w", encoding="utf-8") as handle:
            json.dump(payload, handle, ensure_ascii=False, indent=2)

    def remember_turn(
        self,
        *,
        user_text: str,
        assistant_text: str,
        workspace: str = "",
        source: str = "conversation",
    ) -> dict:
        user = compact_text(user_text, 220)
        assistant = compact_text(assistant_text, 420)
        if not user:
            return {}
        data = self.load()
        entry = {
            "created_at": datetime.now().isoformat(timespec="seconds"),
            "source": compact_text(source, 40),
            "workspace": compact_text(workspace, 160),
            "user": user,
            "summary": assistant,
            "tags": extract_tags(user, assistant),
        }
        memories = [item for item in data.get("memories", []) if isinstance(item, dict)]
        memories.append(entry)
        data["memories"] = memories[-self.limit:]
        self.save(data)
        return entry

    def recent(self, limit: int = 6) -> list[dict]:
        data = self.load()
        memories = [item for item in data.get("memories", []) if isinstance(item, dict)]
        return memories[-max(1, int(limit or 1)) :]

    def context(self, limit: int = 6, char_budget: int = 1400) -> list[dict[str, object]]:
        items = []
        used = 0
        for item in reversed(self.recent(limit=limit * 2)):
            user = compact_text(str(item.get("user") or ""), 180)
            summary = compact_text(str(item.get("summary") or ""), 260)
            line_cost = len(user) + len(summary)
            if not user or used + line_cost > char_budget:
                continue
            items.append({
                "created_at": str(item.get("created_at") or ""),
                "source": str(item.get("source") or "conversation"),
                "user": user,
                "summary": summary,
                "tags": item.get("tags") if isinstance(item.get("tags"), list) else [],
            })
            used += line_cost
            if len(items) >= limit:
                break
        return list(reversed(items))

    def stats(self) -> MemoryStats:
        data = self.load()
        memories = [item for item in data.get("memories", []) if isinstance(item, dict)]
        return MemoryStats(
            count=len(memories),
            path=self.path,
            updated_at=str(data.get("updated_at") or ""),
        )

    def clear(self) -> None:
        self.save({"version": 1, "updated_at": "", "memories": []})

    def import_notes(self, notes: Iterable[str], source: str = "manual") -> int:
        count = 0
        for note in notes:
            if compact_text(note, 40):
                self.remember_turn(user_text=f"[{source}]", assistant_text=note, source=source)
                count += 1
        return count
