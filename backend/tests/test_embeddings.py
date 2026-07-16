from app.llm.registry import EmbeddingsConfig
from app.rag.embeddings import DEFAULT_MODEL, FastEmbedEmbeddings, build_embedding_backend


def test_build_backend_is_fastembed_transformer() -> None:
    backend = build_embedding_backend()
    assert isinstance(backend, FastEmbedEmbeddings)
    assert backend.dim == 384
    # lazy: wiring the backend must not download/load the model (keeps CI offline)
    assert backend._model is None


def test_build_backend_defaults_model_when_unset() -> None:
    backend = build_embedding_backend(EmbeddingsConfig(model=None, dim=384))
    assert isinstance(backend, FastEmbedEmbeddings)
    assert backend._model_name == DEFAULT_MODEL


def test_default_model_is_the_multilingual_minilm() -> None:
    assert DEFAULT_MODEL == "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"
