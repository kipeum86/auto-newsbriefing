import pytest
import tempfile
import os
from pathlib import Path


def test_load_config_valid(tmp_path):
    from pipeline.config import load_config
    cfg_file = tmp_path / "config.yaml"
    cfg_file.write_text(
        "domain:\n  name: test\n  description: test domain\n  language: ko\n"
    )
    config = load_config(str(cfg_file))
    assert config["domain"]["name"] == "test"
    assert config["domain"]["language"] == "ko"


def test_load_config_missing_file(tmp_path):
    from pipeline.config import load_config
    config = load_config(str(tmp_path / "nope.yaml"))
    assert config == {}


def test_load_config_invalid_yaml(tmp_path):
    from pipeline.config import load_config
    cfg_file = tmp_path / "config.yaml"
    cfg_file.write_text("{{invalid: yaml: [")
    config = load_config(str(cfg_file))
    assert config == {}


def test_validate_config_valid():
    from pipeline.config import validate_config
    config = {
        "domain": {"name": "test", "description": "test domain"},
        "llm": {"provider": "claude"},
    }
    assert validate_config(config) is True


def test_validate_config_missing_domain():
    from pipeline.config import validate_config
    assert validate_config({}) is False
    assert validate_config({"domain": {}}) is False
    assert validate_config({"domain": {"name": ""}}) is False


def test_get_config_with_defaults():
    from pipeline.config import get_config_with_defaults
    config = {
        "domain": {"name": "test", "description": "desc"},
    }
    result = get_config_with_defaults(config)
    assert result["domain"]["language"] == "ko"
    assert result["collection"]["days_back"] == 5
    assert result["collection"]["top_n"] == 10
    assert result["collection"]["dedup"]["source_similarity_threshold"] == 0.75
    assert result["llm"]["provider"] == "claude"
    assert result["llm"]["max_input_chars"] == 8000
    assert result["email"]["enabled"] is True


def test_defaults_do_not_overwrite_user_values():
    from pipeline.config import get_config_with_defaults
    config = {
        "domain": {"name": "test", "description": "desc", "language": "en"},
        "collection": {"days_back": 3, "top_n": 5},
        "llm": {"provider": "openai", "model": "gpt-4o"},
    }
    result = get_config_with_defaults(config)
    assert result["domain"]["language"] == "en"
    assert result["collection"]["days_back"] == 3
    assert result["llm"]["provider"] == "openai"
    assert result["llm"]["model"] == "gpt-4o"
