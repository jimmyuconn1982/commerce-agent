from __future__ import annotations

"""Embedding utilities and build jobs.

Inputs:
- text fields and image references from PostgreSQL
- local database connection settings

Outputs:
- deterministic embedding vectors for local development
- upserted text and image embeddings inside PostgreSQL

Role:
- build the first semantic retrieval layer without external dependencies
- keep embedding generation isolated from repository query logic

Upgrade path:
- replace the deterministic provider with OpenAI or another embedding backend
- add multimodal embedding jobs later
"""

import hashlib
import math
import os
from dataclasses import dataclass

import psycopg

from .seed_data import DEFAULT_DATABASE_URL

EMBEDDING_DIMENSION = 1536
TEXT_EMBEDDING_ID_BASE = 823450000000000000
IMAGE_EMBEDDING_ID_BASE = 823460000000000000


@dataclass(slots=True)
class SemanticIndexBuildResult:
    """Summary of the local semantic index build pipeline."""

    text_embeddings_built: int
    image_embeddings_built: int


class DeterministicEmbeddingProvider:
    """Local deterministic embedding provider for development and tests."""

    def embed_text(self, text: str) -> list[float]:
        """Convert text into a stable development embedding."""
        return self._embed_seed(f"text::{text}")

    def embed_image_reference(self, image_ref: str) -> list[float]:
        """Convert an image reference into a stable development embedding."""
        return self._embed_seed(f"image::{image_ref}")

    def _embed_seed(self, seed: str) -> list[float]:
        digest = hashlib.sha256(seed.encode("utf-8")).digest()
        values: list[float] = []
        counter = 0
        while len(values) < EMBEDDING_DIMENSION:
            block = hashlib.sha256(digest + counter.to_bytes(4, "big")).digest()
            for idx in range(0, len(block), 2):
                chunk = int.from_bytes(block[idx : idx + 2], "big")
                values.append((chunk / 65535.0) * 2.0 - 1.0)
                if len(values) == EMBEDDING_DIMENSION:
                    break
            counter += 1

        norm = math.sqrt(sum(value * value for value in values)) or 1.0
        return [round(value / norm, 8) for value in values]


def build_text_embeddings(database_url: str | None = None) -> int:
    """Build and upsert text embeddings for all products."""
    provider = DeterministicEmbeddingProvider()
    database_url = database_url or os.getenv("DATABASE_URL", DEFAULT_DATABASE_URL)
    count = 0

    with psycopg.connect(database_url) as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT
                    p.id,
                    p.title,
                    p.short_description,
                    p.long_description,
                    COALESCE(c.name, '') AS category_name,
                    COALESCE(psd.search_text, '') AS search_text
                FROM products p
                LEFT JOIN categories c ON c.id = p.category_id
                LEFT JOIN product_search_documents psd ON psd.product_id = p.id
                ORDER BY p.id
                """
            )
            rows = cur.fetchall()
            for index, row in enumerate(rows, start=1):
                product_id, title, short_description, long_description, category_name, search_text = row
                source_text = " ".join(
                    part.strip()
                    for part in [title, short_description, long_description, category_name, search_text]
                    if part and part.strip()
                )
                embedding = provider.embed_text(source_text)
                cur.execute(
                    """
                    INSERT INTO product_embeddings (
                        id, product_id, embedding_type, model_name, model_version,
                        embedding, source_text, source_image_url
                    )
                    VALUES (
                        %(id)s, %(product_id)s, 'text', 'deterministic-local', 'v1',
                        %(embedding)s::vector, %(source_text)s, NULL
                    )
                    ON CONFLICT (product_id, embedding_type, model_name) DO UPDATE
                    SET model_version = EXCLUDED.model_version,
                        embedding = EXCLUDED.embedding,
                        source_text = EXCLUDED.source_text,
                        source_image_url = EXCLUDED.source_image_url
                    """,
                    {
                        "id": TEXT_EMBEDDING_ID_BASE + index,
                        "product_id": product_id,
                        "embedding": vector_literal(embedding),
                        "source_text": source_text,
                    },
                )
                count += 1
        conn.commit()
    return count


def build_image_embeddings(database_url: str | None = None) -> int:
    """Build and upsert image embeddings for products with primary media."""
    provider = DeterministicEmbeddingProvider()
    database_url = database_url or os.getenv("DATABASE_URL", DEFAULT_DATABASE_URL)
    count = 0

    with psycopg.connect(database_url) as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT
                    p.id,
                    p.title,
                    COALESCE(pm.url, '') AS image_url,
                    COALESCE(pm.alt_text, '') AS alt_text
                FROM products p
                JOIN product_media pm ON pm.product_id = p.id AND pm.is_primary = TRUE
                ORDER BY p.id
                """
            )
            rows = cur.fetchall()
            for index, row in enumerate(rows, start=1):
                product_id, title, image_url, alt_text = row
                source = " ".join(part.strip() for part in [title, alt_text, image_url] if part and part.strip())
                embedding = provider.embed_image_reference(source)
                cur.execute(
                    """
                    INSERT INTO product_embeddings (
                        id, product_id, embedding_type, model_name, model_version,
                        embedding, source_text, source_image_url
                    )
                    VALUES (
                        %(id)s, %(product_id)s, 'image', 'deterministic-local', 'v1',
                        %(embedding)s::vector, NULL, %(source_image_url)s
                    )
                    ON CONFLICT (product_id, embedding_type, model_name) DO UPDATE
                    SET model_version = EXCLUDED.model_version,
                        embedding = EXCLUDED.embedding,
                        source_text = EXCLUDED.source_text,
                        source_image_url = EXCLUDED.source_image_url
                    """,
                    {
                        "id": IMAGE_EMBEDDING_ID_BASE + index,
                        "product_id": product_id,
                        "embedding": vector_literal(embedding),
                        "source_image_url": image_url,
                    },
                )
                count += 1
        conn.commit()
    return count


def build_semantic_indexes(database_url: str | None = None) -> SemanticIndexBuildResult:
    """Build both text and image semantic indexes with the local mock provider."""
    database_url = database_url or os.getenv("DATABASE_URL", DEFAULT_DATABASE_URL)
    return SemanticIndexBuildResult(
        text_embeddings_built=build_text_embeddings(database_url),
        image_embeddings_built=build_image_embeddings(database_url),
    )


def semantic_index_status(database_url: str | None = None) -> dict[str, int]:
    """Return a compact count summary for the semantic index tables."""
    database_url = database_url or os.getenv("DATABASE_URL", DEFAULT_DATABASE_URL)
    with psycopg.connect(database_url) as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT
                    COUNT(*) FILTER (WHERE embedding_type = 'text') AS text_count,
                    COUNT(*) FILTER (WHERE embedding_type = 'image') AS image_count,
                    COUNT(*) FILTER (WHERE embedding_type = 'multimodal') AS multimodal_count
                FROM product_embeddings
                """
            )
            text_count, image_count, multimodal_count = cur.fetchone()
    return {
        "text_embeddings": text_count,
        "image_embeddings": image_count,
        "multimodal_embeddings": multimodal_count,
    }


def build_text_embeddings_cli() -> None:
    """CLI wrapper for the text embedding build job."""
    count = build_text_embeddings()
    print(f"built {count} text embeddings")


def build_image_embeddings_cli() -> None:
    """CLI wrapper for the image embedding build job."""
    count = build_image_embeddings()
    print(f"built {count} image embeddings")


def build_semantic_indexes_cli() -> None:
    """CLI wrapper for the full local semantic indexing pipeline."""
    result = build_semantic_indexes()
    print(
        f"built {result.text_embeddings_built} text embeddings and "
        f"{result.image_embeddings_built} image embeddings"
    )


def semantic_index_status_cli() -> None:
    """CLI wrapper for semantic index count inspection."""
    import json

    print(json.dumps(semantic_index_status(), indent=2))


def vector_literal(values: list[float]) -> str:
    """Serialize a Python vector into the PostgreSQL vector literal format."""
    return "[" + ",".join(f"{value:.8f}" for value in values) + "]"
