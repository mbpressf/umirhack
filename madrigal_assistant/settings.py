from __future__ import annotations

import json
import os
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent
DEFAULT_CONFIG_PATH = ROOT_DIR / "config" / "demo_region.rostov.json"
DEFAULT_DB_PATH = ROOT_DIR / "data" / "madrigal.db"
DEFAULT_SEED_PATH = ROOT_DIR / "data" / "seed_rostov_last7d.json"


def get_db_path() -> Path:
    return Path(os.getenv("MADRIGAL_DB_PATH", DEFAULT_DB_PATH))


def get_config_path() -> Path:
    return Path(os.getenv("MADRIGAL_CONFIG_PATH", DEFAULT_CONFIG_PATH))


def get_seed_path() -> Path:
    return Path(os.getenv("MADRIGAL_SEED_PATH", DEFAULT_SEED_PATH))


def load_region_config(config_path: Path | None = None) -> dict:
    path = config_path or get_config_path()
    return json.loads(path.read_text(encoding="utf-8"))
