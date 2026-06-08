"""
Shared filesystem paths for Erlangshen.
"""

import os
import sys
from pathlib import Path


def get_project_root() -> Path:
    """Return the repository root."""
    return Path(__file__).resolve().parent.parent


def get_default_knowledge_dir() -> Path:
    """Return the default in-repository knowledge directory."""
    return get_project_root() / "knowledge"


def add_env_path(env_var: str) -> None:
    """Add an optional external dependency path from an environment variable."""
    path = os.getenv(env_var)
    if path and path not in sys.path:
        sys.path.insert(0, path)
