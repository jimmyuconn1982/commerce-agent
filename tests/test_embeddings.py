from commerce_agent.embeddings import (
    DeterministicEmbeddingProvider,
    EMBEDDING_DIMENSION,
    SemanticIndexBuildResult,
    vector_literal,
)


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
