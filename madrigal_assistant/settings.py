from __future__ import annotations

import json
import os
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent
DEFAULT_CONFIG_PATH = ROOT_DIR / "config" / "demo_region.rostov.json"
DEFAULT_DB_PATH = ROOT_DIR / "data" / "madrigal.db"
DEFAULT_SEED_PATH = ROOT_DIR / "data" / "seed_rostov_last7d.json"
DEFAULT_SOURCE_CATALOG_PATH = ROOT_DIR / "config" / "source_catalog.rostov.json"
DEFAULT_FRONTEND_DIST_PATH = ROOT_DIR / "Front" / "dist"


def get_db_path() -> Path:
    return Path(os.getenv("MADRIGAL_DB_PATH", DEFAULT_DB_PATH))


def get_config_path() -> Path:
    return Path(os.getenv("MADRIGAL_CONFIG_PATH", DEFAULT_CONFIG_PATH))


def get_seed_path() -> Path:
    return Path(os.getenv("MADRIGAL_SEED_PATH", DEFAULT_SEED_PATH))


def get_source_catalog_path() -> Path:
    return Path(os.getenv("MADRIGAL_SOURCE_CATALOG_PATH", DEFAULT_SOURCE_CATALOG_PATH))


def get_frontend_dist_path() -> Path:
    return Path(os.getenv("MADRIGAL_FRONTEND_DIST_PATH", DEFAULT_FRONTEND_DIST_PATH))


def _env_flag(name: str, default: bool) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() not in {"0", "false", "no", "off"}


def get_auto_refresh_enabled() -> bool:
    return _env_flag("MADRIGAL_AUTO_REFRESH_ENABLED", True)


def get_auto_refresh_interval_seconds() -> int:
    raw = os.getenv("MADRIGAL_AUTO_REFRESH_INTERVAL_SECONDS", "300")
    try:
        return max(30, int(raw))
    except ValueError:
        return 300


def get_auto_refresh_max_per_source() -> int:
    raw = os.getenv("MADRIGAL_AUTO_REFRESH_MAX_PER_SOURCE", "4")
    try:
        return max(1, int(raw))
    except ValueError:
        return 4


def get_chat_provider() -> str:
    return os.getenv("MADRIGAL_CHAT_PROVIDER", "gigachat").strip().lower()


def get_chat_context_limit() -> int:
    raw = os.getenv("MADRIGAL_CHAT_CONTEXT_LIMIT", "6")
    try:
        return max(3, min(12, int(raw)))
    except ValueError:
        return 6


def get_chat_history_limit() -> int:
    raw = os.getenv("MADRIGAL_CHAT_HISTORY_LIMIT", "8")
    try:
        return max(2, min(20, int(raw)))
    except ValueError:
        return 8


def get_gigachat_auth_key() -> str | None:
    return os.getenv("GIGACHAT_AUTH_KEY")


def get_gigachat_model() -> str:
    return os.getenv("GIGACHAT_MODEL", "GigaChat-2-Max")


def get_gigachat_scope() -> str:
    return os.getenv("GIGACHAT_SCOPE", "GIGACHAT_API_PERS")


def get_gigachat_base_url() -> str:
    return os.getenv("GIGACHAT_BASE_URL", "https://gigachat.devices.sberbank.ru/api/v1").rstrip("/")


def get_gigachat_oauth_url() -> str:
    return os.getenv("GIGACHAT_OAUTH_URL", "https://ngw.devices.sberbank.ru:9443/api/v2/oauth")


def get_gigachat_timeout_seconds() -> int:
    raw = os.getenv("GIGACHAT_TIMEOUT_SECONDS", "45")
    try:
        return max(10, int(raw))
    except ValueError:
        return 45


def get_gigachat_ca_bundle() -> str | None:
    return os.getenv("GIGACHAT_CA_BUNDLE") or None


def get_gigachat_allow_insecure_ssl() -> bool:
    return _env_flag("GIGACHAT_ALLOW_INSECURE_SSL", False)


def _load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _resolve_path(raw_path: str | None, base_dir: Path, default_path: Path) -> Path:
    if not raw_path:
        return default_path
    path = Path(raw_path)
    if not path.is_absolute():
        path = (base_dir / path).resolve()
    return path


def load_source_catalog(source_catalog_path: Path | None = None) -> dict:
    path = source_catalog_path or get_source_catalog_path()
    return _load_json(path)


def _build_live_sources(catalog_payload: dict | list) -> list[dict]:
    entries = catalog_payload.get("sources", catalog_payload) if isinstance(catalog_payload, dict) else catalog_payload
    live_sources: list[dict] = []
    for item in entries:
        if not item.get("enabled_in_live_config"):
            continue
        if item.get("status") == "blocked":
            continue
        required_env = item.get("requires_env")
        if required_env and not os.getenv(required_env):
            continue
        required_envs = item.get("requires_all_env") or []
        if required_envs and any(not os.getenv(env_name) for env_name in required_envs):
            continue
        live_sources.append(dict(item))
    return live_sources


def load_region_config(config_path: Path | None = None) -> dict:
    path = config_path or get_config_path()
    payload = _load_json(path)
    source_catalog_path = payload.get("source_catalog_path")
    if source_catalog_path:
        resolved_catalog_path = _resolve_path(source_catalog_path, path.parent, get_source_catalog_path())
        catalog_payload = load_source_catalog(resolved_catalog_path)
        payload["source_catalog_path"] = str(resolved_catalog_path)
        payload["source_catalog"] = catalog_payload.get("sources", catalog_payload)
        payload["sources"] = _build_live_sources(catalog_payload)
    return payload
