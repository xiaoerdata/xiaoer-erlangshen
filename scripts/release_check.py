#!/usr/bin/env python3
"""Run lightweight release checks for the CLI package."""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def run_step(label: str, args: list[str]) -> int:
    print(f"==> {label}", flush=True)
    result = subprocess.run(args, cwd=str(ROOT), text=True, check=False)
    return result.returncode


def main() -> int:
    parser = argparse.ArgumentParser(description="Run Erlangshen CLI release checks.")
    parser.add_argument(
        "--refresh-benchmarks",
        action="store_true",
        help="Refresh GitHub star snapshot before smoke checks. Requires network/GitHub access.",
    )
    args = parser.parse_args()

    steps: list[tuple[str, list[str]]] = []
    if args.refresh_benchmarks:
        steps.append(("refresh cli benchmarks", [sys.executable, "scripts/update_cli_benchmarks.py"]))
    else:
        print("==> refresh cli benchmarks skipped; pass --refresh-benchmarks when releasing", flush=True)
    steps.extend([
        ("strict exit-code smoke", [sys.executable, "scripts/smoke_cli_strict.py"]),
        ("npm wrapper smoke", [sys.executable, "scripts/smoke_cli_npm.py"]),
    ])

    for label, command in steps:
        code = run_step(label, command)
        if code != 0:
            return code
    print("release check passed", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
