"""Config loading, validation, and defaults."""

import logging
import os
from copy import deepcopy
from pathlib import Path

import yaml

logger = logging.getLogger(__name__)

_PROJECT_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_CONFIG_PATH = str(_PROJECT_ROOT / "config.yaml")

DEFAULTS = {
    "domain": {"language": "ko"},
    "categories": [],
    "keywords": {"include": [], "exclude": []},
    "sources": {"tier_a": [], "tier_b": []},
    "collection": {
        "days_back": 5,
        "top_n": 10,
        "min_content_length": 200,
        "dedup": {
            "source_similarity_threshold": 0.75,
            "cross_similarity_threshold": 0.60,
            "min_overlap_tokens": 3,
            "event_key_enabled": True,
            "event_time_bucket": "month",
            "hash_len": 16,
        },
    },
    "llm": {
        "provider": "claude",
        "model": "",
        "max_input_chars": 8000,
    },
    "email": {
        "enabled": True,
        "sender_name": "",
        "subject_prefix": "",
        "recipients": [],
    },
    "sheets": {"spreadsheet_id": ""},
    "schedule": {"cron": "7 1 * * 1,3,5", "timezone": "Asia/Seoul"},
}


def load_config(path: str | None = None) -> dict:
    path = path or DEFAULT_CONFIG_PATH
    try:
        with open(path, encoding="utf-8") as f:
            return yaml.safe_load(f) or {}
    except FileNotFoundError:
        logger.error("config.yaml not found: %s", path)
        return {}
    except yaml.YAMLError as e:
        logger.error("config.yaml parse error: %s", e)
        return {}


def validate_config(config: dict) -> bool:
    domain = config.get("domain", {})
    if not domain.get("name") or not domain.get("description"):
        logger.error(
            "Setup required: set domain.name and domain.description in config.yaml"
        )
        return False
    return True


def _deep_merge(base: dict, override: dict) -> dict:
    result = deepcopy(base)
    for key, value in override.items():
        if (
            key in result
            and isinstance(result[key], dict)
            and isinstance(value, dict)
        ):
            result[key] = _deep_merge(result[key], value)
        else:
            result[key] = deepcopy(value)
    return result


def get_config_with_defaults(config: dict) -> dict:
    return _deep_merge(DEFAULTS, config)


def setup_logging(config: dict) -> None:
    level = os.environ.get("LOG_LEVEL", "INFO").upper()
    logging.basicConfig(
        level=getattr(logging, level, logging.INFO),
        format="[%(levelname)s] %(name)s: %(message)s",
    )
