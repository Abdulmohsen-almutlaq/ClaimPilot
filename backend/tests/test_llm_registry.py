import pytest

from app.llm.registry import (
    PromptNotFoundError,
    UnknownProviderError,
    load_models_config,
    load_prompt,
)


def test_load_models_config_reads_repo_config() -> None:
    config = load_models_config()
    assert config.default_provider == "deepseek"
    assert set(config.providers) >= {"anthropic", "openai", "deepseek", "local"}
    assert config.providers["deepseek"].model == "deepseek-chat"
    assert config.providers["deepseek"].base_url == "https://api.deepseek.com/v1"


def test_resolve_node_falls_back_to_defaults() -> None:
    config = load_models_config()
    node_cfg = config.resolve_node("intake")
    assert node_cfg.provider == "deepseek"
    assert node_cfg.temperature == 0.0  # overridden for intake
    assert node_cfg.max_retries == config.defaults["max_retries"]


def test_embeddings_and_retrieval_config_loaded() -> None:
    config = load_models_config()
    assert config.embeddings.model == "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"
    assert config.embeddings.dim == 384
    assert config.retrieval.top_k >= 1
    assert 0 < config.retrieval.min_similarity < 1


def test_provider_unknown_raises() -> None:
    config = load_models_config()
    with pytest.raises(UnknownProviderError):
        config.provider("does-not-exist")


def test_prompt_version_lookup() -> None:
    config = load_models_config()
    # the active version tracks models.yaml; it must exist as a prompt file
    version = config.prompt_version("intake_extract")
    assert load_prompt("intake_extract", version)


def test_load_prompt_reads_file() -> None:
    text = load_prompt("intake_extract", "v1")
    assert "claims intake assistant" in text


def test_load_prompt_missing_raises() -> None:
    with pytest.raises(PromptNotFoundError):
        load_prompt("does_not_exist", "v1")
