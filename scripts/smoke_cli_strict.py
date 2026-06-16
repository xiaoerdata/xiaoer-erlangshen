#!/usr/bin/env python3
"""Smoke test strict CLI exit-code classification without external services."""

from __future__ import annotations

import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.cli import _strict_exit_code  # noqa: E402


CASES = [
    ("unknown command", "/statsu", "未知命令: /statsu", 64),
    ("bad chart args", "/chart", "请提供图表标题和 JSON 数据。", 64),
    ("workspace", "/doctor", "NEED workspace\nfix   workspace", 65),
    ("account", "/status", "未登录", 66),
    ("model", "/model", "missing key", 67),
    ("server", "/server status", "服务端连接失败", 68),
    ("local module", "/analyze", "当前安装包不包含 /analyze 的本地分析模块", 69),
    ("artifact", "/chart", "图表生成失败", 70),
    ("ok", "/benchmarks", "OK", 0),
]


def main() -> int:
    failures = []
    for name, command, text, expected in CASES:
        actual = _strict_exit_code(command, text)
        if actual != expected:
            failures.append(f"{name}: expected {expected}, got {actual}")
    if failures:
        print("strict smoke failed:")
        for item in failures:
            print(f"- {item}")
        return 1
    print(f"strict smoke passed: {len(CASES)} cases")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
