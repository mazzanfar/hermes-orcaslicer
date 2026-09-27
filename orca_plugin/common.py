"""Small, dependency-free primitives shared by plugin and command line."""
from __future__ import annotations

import hashlib
import json
import os
import re
import tempfile
from pathlib import Path


class OrcaError(Exception):
    """Actionable user-facing error, without credentials or remote response bodies."""


def read_json(path: Path):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise OrcaError(f"Cannot read JSON file: {path.name}") from exc


def write_json(path: Path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=path.parent, prefix=".orca-")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, allow_nan=False)
            f.write("\n")
        os.replace(tmp, path)
    finally:
        if os.path.exists(tmp):
            os.unlink(tmp)


def sha256(path: Path) -> str:
    with path.open("rb") as f:
        return hashlib.file_digest(f, "sha256").hexdigest()


def identifier(value: str) -> str:
    if not isinstance(value, str) or not re.fullmatch(r"[a-zA-Z0-9][a-zA-Z0-9_-]{0,79}", value):
        raise OrcaError("Use an identifier containing only letters, numbers, hyphens and underscores.")
    return value


CREDENTIAL_ENV_PATTERN = re.compile(r"(ORCA|HERMES_ORCA)_[A-Z0-9_]+")


def credential_env_name(value, option: str = "api_key_env") -> str:
    """Accept only plugin-scoped secret variable NAMES (ORCA_* / HERMES_ORCA_*).

    The plugin later sends os.environ[name] to a model-supplied URL, so an
    unscoped name could forward an unrelated provider secret to that host.
    """
    if not isinstance(value, str) or not CREDENTIAL_ENV_PATTERN.fullmatch(value):
        raise OrcaError(f"{option} must be the NAME of an environment variable starting with ORCA_ (for example ORCA_OCTOPRINT_KEY), "
                        "never a secret value or an unrelated provider variable.")
    return value


def existing_file(value: str, suffixes=None) -> Path:
    p = Path(value).expanduser().resolve()
    if not p.is_file():
        raise OrcaError(f"File not found: {p}")
    if suffixes and p.suffix.lower() not in suffixes:
        raise OrcaError(f"Expected one of: {', '.join(sorted(suffixes))}")
    return p


def home() -> Path:
    return Path(os.environ.get("HERMES_ORCA_HOME", Path.home() / ".hermes-orca")).expanduser().resolve()
