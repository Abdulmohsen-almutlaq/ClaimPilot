import pytest

from app.llm.registry import (
    PromptNotFoundError,
    UnknownProviderError,
    load_models_config,
    load_prompt,
)


def test_load_models_config_reads_repo_config() -> None:
    config = load_models_config()
    assert config.default_provider == "anthropic"
    assert "anthropic" in config.providers
    assert config.providers["anthropic"].model == "claude-sonnet-4-6"


def test_resolve_node_falls_back_to_defaults() -> None:
    config = load_models_config()
    node_cfg = config.resolve_node("intake")
    assert node_cfg.provider == "anthropic"
    assert node_cfg.temperature == 0.0  # overridden for intake
    assert node_cfg.max_retries == config.defaults["max_retries"]


def test_provider_unknown_raises() -> None:
    config = load_models_config()
    with pytest.raises(UnknownProviderError):
        config.provider("does-not-exist")


def test_prompt_version_lookup() -> None:
    config = load_models_config()
    assert config.prompt_version("intake_extract") == "v1"


def test_load_prompt_reads_file() -> None:
    text = load_prompt("intake_extract", "v1")
    assert "claims intake assistant" in text


def test_load_prompt_missing_raises() -> None:
    with pytest.raises(PromptNotFoundError):
        load_prompt("does_not_exist", "v1")
