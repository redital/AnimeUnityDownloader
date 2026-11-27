"""Configuration of the Flask application, read from environment variables."""

import os
from pathlib import Path


def _env_bool(name: str, *, default: bool) -> bool:
    """Read a boolean environment variable ("1", "true", "yes", "on")."""
    value = os.environ.get(name)
    if value is None or value.strip() == "":
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _env_optional(name: str) -> str | None:
    """Read an optional string variable; empty or "None" means not set."""
    value = os.environ.get(name, "").strip()
    return None if value.lower() in {"", "none"} else value


flask_app_config = {
    "debug": _env_bool("FLASK_DEBUG", default=False),
    "host": os.environ.get("FLASK_HOST", "0.0.0.0"),
    "port": int(os.environ.get("FLASK_PORT", "5000")),
    "ssl_context": _env_optional("SSL_CONTEXT"),
}

# Folder under which downloads may be saved, including any custom path
download_root = os.environ.get("DOWNLOAD_ROOT", "").strip() or str(Path.cwd())

animeunity_url = (
    _env_optional("ANIMEUNITY_URL") or "https://www.animeunity.to"
).rstrip("/")
