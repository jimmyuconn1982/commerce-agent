from commerce_agent.embeddings import (
    BigModelEmbeddingProvider,
    DeterministicEmbeddingProvider,
    EMBEDDING_DIMENSION,
    SemanticIndexBuildResult,
    get_embedding_provider,
    vector_literal,
)
from commerce_agent.ids import SnowflakeLikeIdGenerator


def test_deterministic_embedding_provider_is_stable() -> None:
    provider = DeterministicEmbeddingProvider()
    first = provider.embed_text("mechanical keyboard")
    second = provider.embed_text("mechanical keyboard")

    assert first == second
    assert len(first) == EMBEDDING_DIMENSION


def test_vector_literal_formats_for_pgvector() -> None:
    literal = vector_literal([0.1, -0.2, 0.3])
    assert literal == "[0.10000000,-0.20000000,0.30000000]"


def test_semantic_index_build_result_carries_counts() -> None:
    result = SemanticIndexBuildResult(text_embeddings_built=6, image_embeddings_built=6)
    assert result.text_embeddings_built == 6
    assert result.image_embeddings_built == 6


def test_get_embedding_provider_defaults_to_deterministic(monkeypatch) -> None:
    monkeypatch.delenv("COMMERCE_AGENT_EMBEDDING_PROVIDER", raising=False)
    provider = get_embedding_provider()
    assert isinstance(provider, DeterministicEmbeddingProvider)


def test_bigmodel_provider_requires_api_key(monkeypatch) -> None:
    monkeypatch.delenv("BIGMODEL_API_KEY", raising=False)
    try:
        BigModelEmbeddingProvider()
    except ValueError as exc:
        assert "BIGMODEL_API_KEY" in str(exc)
    else:
        raise AssertionError("expected missing API key to raise ValueError")


def test_embedding_ids_are_stable_per_product_and_model() -> None:
    generator = SnowflakeLikeIdGenerator()
    first = generator.stable("text_embedding", "123:embedding-3")
    second = generator.stable("text_embedding", "123:embedding-3")
    image_id = generator.stable("image_embedding", "123:embedding-3")

    assert first == second
    assert first != image_id
