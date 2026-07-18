"""Secrets store — passwords live here, NEVER in config.yaml.

LAYOUT
------
    config/config.yaml    ← committed choices (hosts, usernames, providers)
    config/secrets.yaml   ← gitignored passwords/tokens, chmod 600

Resolution order for a secret (env var wins — handy for CI and containers):
    1. Environment variable  EXEC_ASSISTANT_<KEY_UPPER>
    2. config/secrets.yaml

The file is plain YAML with a flat string→string mapping. Anything more
complex (keyring, vault) can be layered on later without touching callers.
"""

from __future__ import annotations

import os
import stat
from pathlib import Path

import yaml

from executive_assistant.config import PROJECT_ROOT

SECRETS_PATH = PROJECT_ROOT / "config" / "secrets.yaml"
ENV_PREFIX = "EXEC_ASSISTANT_"


def load_secrets(path: Path | None = None) -> dict[str, str]:
    path = path or SECRETS_PATH
    if not path.exists():
        return {}
    data = yaml.safe_load(path.read_text()) or {}
    return {str(k): str(v) for k, v in data.items()}


def get_secret(key: str, path: Path | None = None) -> str:
    """Resolve one secret: env var first, then the secrets file."""
    env_val = os.environ.get(f"{ENV_PREFIX}{key.upper()}")
    if env_val:
        return env_val
    return load_secrets(path).get(key, "")


def set_secret(key: str, value: str, path: Path | None = None) -> Path:
    """Write one secret, preserving the others; file is chmod 600."""
    path = path or SECRETS_PATH
    secrets = load_secrets(path)
    secrets[key] = value
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "# Passwords/tokens for executive-assistant. GITIGNORED. Do not commit.\n"
        + yaml.safe_dump(secrets, default_flow_style=False)
    )
    # Owner read/write only — this file exists precisely to hold passwords.
    path.chmod(stat.S_IRUSR | stat.S_IWUSR)
    return path
