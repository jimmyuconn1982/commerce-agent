from __future__ import annotations

"""PostgreSQL-backed search repository.

Inputs:
- raw text-search queries
- parser output
- local database connection settings

Outputs:
- parsed query metadata
- product search hits joined from relational tables

Role:
- query PostgreSQL directly for text retrieval
- keep database read logic separate from the agent orchestrator

Upgrade path:
- add image and multimodal repository paths
- swap deterministic semantic scoring for real embedding models later
"""

import os
from dataclasses import asdict
from typing import Protocol

import psycopg

from .embeddings import DeterministicEmbeddingProvider, vector_literal
from .catalog import Catalog
from .models import ParsedSearchQuery, Product, ProductSearchHit
from .search_parser import SearchParser
from .seed_data import DEFAULT_DATABASE_URL


class SearchRepository(Protocol):
    """Protocol for pluggable search repositories."""

    def search_text(self, query: str, limit: int = 5) -> tuple[ParsedSearchQuery, list[ProductSearchHit]]:
        """Run text search and return parsed query plus ranked product cards."""
        ...


class CatalogSearchRepository:
    """Fallback in-memory repository backed by the local MVP catalog."""

    def __init__(self, catalog: Catalog) -> None:
        self.catalog = catalog
        self.parser = SearchParser()

    def search_text(self, query: str, limit: int = 5) -> tuple[ParsedSearchQuery, list[ProductSearchHit]]:
        """Run a lightweight in-memory fallback search over the local catalog."""
        categories = {product.category for product in self.catalog.all()}
        parsed = self.parser.parse(query, known_categories=categories)
        terms = set((parsed.remaining_query or parsed.normalized_query).split())

        hits: list[ProductSearchHit] = []
        for product in self.catalog.all():
            haystack = " ".join(
                [
                    product.name.lower(),
                    product.category.lower(),
                    product.description.lower(),
                    " ".join(tag.lower() for tag in product.tags),
                    " ".join(tag.lower() for tag in product.image_tags),
                    product.visual_description.lower(),
                ]
            )
            keyword_score = sum(1.0 for term in terms if term in haystack)
            if not terms:
                keyword_score = 1.0
            if keyword_score == 0:
                continue
            hits.append(
                ProductSearchHit(
                    product_id=product.id,
                    title=product.name,
                    short_description=product.description,
                    primary_image_url=product.image_url,
                    price=0.0,
                    currency="USD",
                    seller_name="Catalog Seed",
                    seller_rating=0.0,
                    review_count=max(0, int(product.rating * 42)),
                    inventory_count=0,
                    product_url=f"https://example.com/products/{product.id}",
                    category_name=product.category,
                    keyword_score=keyword_score,
                    semantic_score=0.0,
                    match_score=keyword_score,
                )
            )
        hits.sort(key=lambda item: (item.match_score, item.review_count), reverse=True)
        return parsed, hits[:limit]


class PostgresSearchRepository:
    """Repository that runs keyword and semantic text search in PostgreSQL."""

    def __init__(
        self,
        database_url: str | None = None,
        parser: SearchParser | None = None,
    ) -> None:
        self.database_url = database_url or os.getenv("DATABASE_URL", DEFAULT_DATABASE_URL)
        self.parser = parser or SearchParser()
        self.embedding_provider = DeterministicEmbeddingProvider()

    def search_text(self, query: str, limit: int = 5) -> tuple[ParsedSearchQuery, list[ProductSearchHit]]:
        """Parse one text query, run hybrid retrieval, and return product cards."""
        with psycopg.connect(self.database_url) as conn:
            categories = self._load_category_names(conn)
            parsed = self.parser.parse(query, known_categories=categories)
            query_text = parsed.remaining_query or parsed.normalized_query or parsed.raw_query
            vector = vector_literal(self.embedding_provider.embed_text(query_text))
            rows = self._search_text_rows(conn, parsed, query_text, vector, limit)
        return parsed, [ProductSearchHit(*row) for row in rows]

    def _load_category_names(self, conn: psycopg.Connection) -> set[str]:
        """Load current category names so the parser can extract hints."""
        with conn.cursor() as cur:
            cur.execute("SELECT lower(name) FROM categories")
            return {row[0] for row in cur.fetchall()}

    def _search_text_rows(
        self,
        conn: psycopg.Connection,
        parsed: ParsedSearchQuery,
        query_text: str,
        vector: str,
        limit: int,
    ) -> list[tuple]:
        """Execute the first hybrid text-search query against PostgreSQL."""
        conditions = ["p.status = 'active'"]
        params: dict[str, object] = {
            "query_text": query_text,
            "vector": vector,
            "candidate_limit": max(limit * 5, 20),
            "limit": limit,
        }

        if parsed.category_hints:
            conditions.append("lower(c.name) = ANY(%(category_hints)s)")
            params["category_hints"] = parsed.category_hints

        if parsed.min_price is not None:
            conditions.append("po.price >= %(min_price)s")
            params["min_price"] = parsed.min_price

        if parsed.max_price is not None:
            conditions.append("po.price <= %(max_price)s")
            params["max_price"] = parsed.max_price

        order_by = "f.match_score DESC, prs.average_rating DESC NULLS LAST, po.price ASC"
        if parsed.sort == "price_asc":
            order_by = "po.price ASC, f.match_score DESC"
        elif parsed.sort == "rating_desc":
            order_by = "prs.average_rating DESC NULLS LAST, f.match_score DESC"

        sql = f"""
            WITH keyword_hits AS (
                SELECT
                    psd.product_id,
                    GREATEST(
                        ts_rank(psd.search_tsv, websearch_to_tsquery('english', unaccent(%(query_text)s))),
                        similarity(psd.search_text, %(query_text)s)
                    ) AS keyword_score
                FROM product_search_documents psd
                WHERE
                    psd.search_tsv @@ websearch_to_tsquery('english', unaccent(%(query_text)s))
                    OR psd.search_text %% %(query_text)s
                ORDER BY keyword_score DESC
                LIMIT %(candidate_limit)s
            ),
            semantic_hits AS (
                SELECT
                    pe.product_id,
                    1 - (pe.embedding <=> %(vector)s::vector) AS semantic_score
                FROM product_embeddings pe
                WHERE pe.embedding_type = 'text'
                ORDER BY pe.embedding <=> %(vector)s::vector
                LIMIT %(candidate_limit)s
            ),
            fused AS (
                SELECT
                    COALESCE(k.product_id, s.product_id) AS product_id,
                    COALESCE(k.keyword_score, 0) AS keyword_score,
                    COALESCE(s.semantic_score, 0) AS semantic_score,
                    (COALESCE(k.keyword_score, 0) * 0.65) + (COALESCE(s.semantic_score, 0) * 0.35) AS match_score
                FROM keyword_hits k
                FULL OUTER JOIN semantic_hits s ON s.product_id = k.product_id
            )
            SELECT
                p.id,
                p.title,
                p.short_description,
                COALESCE(pm.url, '') AS primary_image_url,
                po.price,
                po.currency,
                s.name AS seller_name,
                COALESCE(s.rating, 0) AS seller_rating,
                COALESCE(prs.review_count, 0) AS review_count,
                po.inventory_count,
                po.product_url,
                c.name AS category_name,
                f.keyword_score,
                f.semantic_score,
                f.match_score
            FROM fused f
            JOIN products p ON p.id = f.product_id
            JOIN categories c ON c.id = p.category_id
            JOIN LATERAL (
                SELECT pm.url
                FROM product_media pm
                WHERE pm.product_id = p.id AND pm.is_primary = TRUE
                ORDER BY pm.sort_order ASC, pm.id ASC
                LIMIT 1
            ) pm ON TRUE
            JOIN LATERAL (
                SELECT po.price, po.currency, po.inventory_count, po.product_url, po.seller_id
                FROM product_offers po
                WHERE po.product_id = p.id AND po.is_active = TRUE
                ORDER BY po.price ASC, po.id ASC
                LIMIT 1
            ) po ON TRUE
            JOIN sellers s ON s.id = po.seller_id
            LEFT JOIN product_review_stats prs ON prs.product_id = p.id
            WHERE {' AND '.join(conditions)}
            ORDER BY {order_by}
            LIMIT %(limit)s
        """

        with conn.cursor() as cur:
            cur.execute(sql, params)
            return cur.fetchall()


def search_text_cli() -> None:
    """CLI wrapper for PostgreSQL-backed text search."""
    import argparse
    import json

    parser = argparse.ArgumentParser(description="Run text search directly against PostgreSQL")
    parser.add_argument("query")
    parser.add_argument("--limit", type=int, default=5)
    args = parser.parse_args()

    parsed, hits = PostgresSearchRepository().search_text(args.query, limit=args.limit)
    print(
        json.dumps(
            {
                "parsed_query": asdict(parsed),
                "hits": [asdict(hit) for hit in hits],
            },
            indent=2,
            default=str,
        )
    )
