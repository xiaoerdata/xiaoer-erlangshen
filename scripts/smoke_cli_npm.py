#!/usr/bin/env python3
"""Smoke test the npm wrapper for quiet, plain and json modes."""

from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
NODE_CLI = ROOT / "bin" / "cli.js"


def isolated_env(tmp: Path) -> dict[str, str]:
    env = os.environ.copy()
    env.update({
        "ERLANGSHEN_AUTH_FILE": str(tmp / "auth.json"),
        "ERLANGSHEN_CONFIG": str(tmp / "settings.json"),
        "ERLANGSHEN_WORKSPACE_FILE": str(tmp / "workspaces.json"),
        "ERLANGSHEN_COMMAND_USAGE_FILE": str(tmp / "command_usage.json"),
        "ERLANGSHEN_HISTORY_FILE": str(tmp / "history"),
        "ERLANGSHEN_MEMORY_FILE": str(tmp / "memory.json"),
        "ERLANGSHEN_RECORD_NON_TTY_COMMANDS": "1",
        "NO_COLOR": "1",
        "ERLANGSHEN_NO_OSC8": "1",
    })
    return env


def run_case(args: list[str], env: dict[str, str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["node", str(NODE_CLI), *args],
        cwd=str(ROOT),
        env=env,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        timeout=20,
        check=False,
    )


def assert_ok(name: str, result: subprocess.CompletedProcess[str]) -> None:
    if result.returncode != 0:
        raise AssertionError(f"{name}: exit {result.returncode}\nstdout={result.stdout}\nstderr={result.stderr}")


def main() -> int:
    failures: list[str] = []
    with tempfile.TemporaryDirectory(prefix="erlangshen-npm-smoke-") as tmp_dir:
        env = isolated_env(Path(tmp_dir))
        cases = {
            "quiet": ["--quiet", "/status"],
            "plain": ["--plain", "/help"],
            "json": ["--json", "/benchmarks"],
        }
        results = {name: run_case(args, env) for name, args in cases.items()}
        try:
            assert_ok("quiet", results["quiet"])
            quiet_text = results["quiet"].stdout + results["quiet"].stderr
            if "启动二郎神" in quiet_text or "🚀" in quiet_text:
                raise AssertionError("quiet: wrapper banner leaked into output")

            assert_ok("plain", results["plain"])
            plain_text = results["plain"].stdout
            if "\x1b[" in plain_text or "\x1b]8;" in plain_text:
                raise AssertionError("plain: ANSI or OSC8 escape sequence leaked")
            if "/commands usage" not in plain_text:
                raise AssertionError("plain: help output did not include expected command")

            assert_ok("json", results["json"])
            payload = json.loads(results["json"].stdout)
            if payload.get("ok") is not True or payload.get("command") != "/benchmarks":
                raise AssertionError(f"json: unexpected envelope {payload}")
            if "CLI 对标" not in payload.get("text", ""):
                raise AssertionError("json: benchmark text missing from envelope")
        except (AssertionError, json.JSONDecodeError) as exc:
            failures.append(str(exc))

    if failures:
        print("npm wrapper smoke failed:")
        for item in failures:
            print(f"- {item}")
        return 1
    print(f"npm wrapper smoke passed: {len(cases)} cases")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
