#!/usr/bin/env python3
"""
Refresh src/cli_benchmarks.json from the GitHub REST API.
"""

from __future__ import annotations

import json
import os
import sys
import urllib.request
from datetime import date
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
TARGET = ROOT / "src" / "cli_benchmarks.json"
API = "https://api.github.com/repos/{repo}"


def fetch_repo(repo: str) -> dict:
    headers = {
        "Accept": "application/vnd.github+json",
        "User-Agent": "erlangshen-cli-benchmark-refresh",
    }
    token = os.getenv("GITHUB_TOKEN")
    if token:
        headers["Authorization"] = f"Bearer {token}"
    request = urllib.request.Request(API.format(repo=repo), headers=headers)
    with urllib.request.urlopen(request, timeout=30) as response:
        return json.load(response)


def main() -> int:
    with open(TARGET, "r", encoding="utf-8") as f:
        payload = json.load(f)

    projects = payload.get("projects") or []
    if not isinstance(projects, list):
        raise SystemExit("cli_benchmarks.json must contain a projects list")

    refreshed = []
    for project in projects:
        if not isinstance(project, dict) or not project.get("repo"):
            continue
        repo = str(project["repo"])
        data = fetch_repo(repo)
        item = dict(project)
        item["stars"] = int(data.get("stargazers_count") or 0)
        item["source_url"] = data.get("html_url") or f"https://github.com/{repo}"
        refreshed.append(item)
        print(f"{item['stars']:>8}  {repo}")

    refreshed.sort(key=lambda item: int(item.get("stars") or 0), reverse=True)
    for index, item in enumerate(refreshed, 1):
        item["rank"] = index

    payload["checked_at"] = date.today().isoformat()
    payload.setdefault("source", {})
    payload["source"].update({
        "provider": "GitHub REST API",
        "field": "stargazers_count",
        "checked_with": API,
    })
    payload["projects"] = refreshed

    with open(TARGET, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)
        f.write("\n")
    print(f"updated {TARGET}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
