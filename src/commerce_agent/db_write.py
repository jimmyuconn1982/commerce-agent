from __future__ import annotations

"""Centralized database write path for commerce-agent.

Inputs:
- normalized seed rows
- prepared embedding rows
- an open psycopg connection

Outputs:
- upserted relational rows in PostgreSQL

Role:
- keep all application-side writes behind one shared write module
- enforce one database write path for seed loading and indexing jobs

Upgrade path:
- expand this module for future product ingest and admin write flows
- add transaction policies and auditing here instead of duplicating SQL
"""

from typing import Any

from psycopg.types.json import Json


class DatabaseWriter:
    """Shared write gateway for application-owned database mutations."""

    def __init__(self, conn: Any) -> None:
        self.conn = conn

    def truncate_seed_tables(self) -> None:
        """Clear seed-owned tables before a full reload."""
        with self.conn.cursor() as cur:
            cur.execute(
                """
                TRUNCATE TABLE
                    product_embeddings,
                    product_search_documents,
                    product_review_stats,
                    product_offers,
                    product_media,
                    products,
                    sellers,
                    categories
                CASCADE
                """
            )

    def load_seed_bundle(self, bundle: dict[str, list[dict[str, Any]]]) -> None:
        """Upsert one normalized seed bundle into PostgreSQL."""
        with self.conn.cursor() as cur:
            self._upsert_categories(cur, bundle["categories"])
            self._upsert_products(cur, bundle["products"])
            self._upsert_product_media(cur, bundle["product_media"])
            self._upsert_sellers(cur, bundle["sellers"])
            self._upsert_product_offers(cur, bundle["product_offers"])
            self._upsert_review_stats(cur, bundle["product_review_stats"])
            self._upsert_search_documents(cur, bundle["product_search_documents"])

    def replace_embeddings(self, embedding_type: str, rows: list[dict[str, Any]]) -> None:
        """Replace one embedding namespace with a freshly built payload."""
        with self.conn.cursor() as cur:
            cur.execute("DELETE FROM product_embeddings WHERE embedding_type = %(embedding_type)s", {"embedding_type": embedding_type})
            cur.executemany(
                """
                INSERT INTO product_embeddings (
                    id, product_id, embedding_type, model_name, model_version,
                    embedding, source_text, source_image_url
                )
                VALUES (
                    %(id)s, %(product_id)s, %(embedding_type)s, %(model_name)s, %(model_version)s,
                    %(embedding)s::vector, %(source_text)s, %(source_image_url)s
                )
                """,
                rows,
            )

    def _upsert_categories(self, cur: Any, rows: list[dict[str, Any]]) -> None:
        cur.executemany(
            """
            INSERT INTO categories (id, name, parent_id)
            VALUES (%(id)s, %(name)s, %(parent_id)s)
            ON CONFLICT (id) DO UPDATE
            SET name = EXCLUDED.name,
                parent_id = EXCLUDED.parent_id
            """,
            rows,
        )

    def _upsert_products(self, cur: Any, rows: list[dict[str, Any]]) -> None:
        payload = [{**row, "attributes_jsonb": Json(row["attributes_jsonb"])} for row in rows]
        cur.executemany(
            """
            INSERT INTO products (
                id, sku, title, short_description, long_description, brand,
                category_id, status, attributes_jsonb
            )
            VALUES (
                %(id)s, %(sku)s, %(title)s, %(short_description)s, %(long_description)s, %(brand)s,
                %(category_id)s, %(status)s, %(attributes_jsonb)s
            )
            ON CONFLICT (id) DO UPDATE
            SET sku = EXCLUDED.sku,
                title = EXCLUDED.title,
                short_description = EXCLUDED.short_description,
                long_description = EXCLUDED.long_description,
                brand = EXCLUDED.brand,
                category_id = EXCLUDED.category_id,
                status = EXCLUDED.status,
                attributes_jsonb = EXCLUDED.attributes_jsonb
            """,
            payload,
        )

    def _upsert_product_media(self, cur: Any, rows: list[dict[str, Any]]) -> None:
        cur.executemany(
            """
            INSERT INTO product_media (
                id, product_id, media_type, url, thumbnail_url, sort_order,
                alt_text, width, height, is_primary
            )
            VALUES (
                %(id)s, %(product_id)s, %(media_type)s, %(url)s, %(thumbnail_url)s, %(sort_order)s,
                %(alt_text)s, %(width)s, %(height)s, %(is_primary)s
            )
            ON CONFLICT (id) DO UPDATE
            SET product_id = EXCLUDED.product_id,
                media_type = EXCLUDED.media_type,
                url = EXCLUDED.url,
                thumbnail_url = EXCLUDED.thumbnail_url,
                sort_order = EXCLUDED.sort_order,
                alt_text = EXCLUDED.alt_text,
                width = EXCLUDED.width,
                height = EXCLUDED.height,
                is_primary = EXCLUDED.is_primary
            """,
            rows,
        )

    def _upsert_sellers(self, cur: Any, rows: list[dict[str, Any]]) -> None:
        cur.executemany(
            """
            INSERT INTO sellers (
                id, seller_code, name, rating, seller_url, location, is_verified
            )
            VALUES (
                %(id)s, %(seller_code)s, %(name)s, %(rating)s, %(seller_url)s, %(location)s, %(is_verified)s
            )
            ON CONFLICT (id) DO UPDATE
            SET seller_code = EXCLUDED.seller_code,
                name = EXCLUDED.name,
                rating = EXCLUDED.rating,
                seller_url = EXCLUDED.seller_url,
                location = EXCLUDED.location,
                is_verified = EXCLUDED.is_verified
            """,
            rows,
        )

    def _upsert_product_offers(self, cur: Any, rows: list[dict[str, Any]]) -> None:
        cur.executemany(
            """
            INSERT INTO product_offers (
                id, product_id, seller_id, price, currency, inventory_count,
                product_url, shipping_info, is_active
            )
            VALUES (
                %(id)s, %(product_id)s, %(seller_id)s, %(price)s, %(currency)s, %(inventory_count)s,
                %(product_url)s, %(shipping_info)s, %(is_active)s
            )
            ON CONFLICT (id) DO UPDATE
            SET product_id = EXCLUDED.product_id,
                seller_id = EXCLUDED.seller_id,
                price = EXCLUDED.price,
                currency = EXCLUDED.currency,
                inventory_count = EXCLUDED.inventory_count,
                product_url = EXCLUDED.product_url,
                shipping_info = EXCLUDED.shipping_info,
                is_active = EXCLUDED.is_active
            """,
            rows,
        )

    def _upsert_review_stats(self, cur: Any, rows: list[dict[str, Any]]) -> None:
        cur.executemany(
            """
            INSERT INTO product_review_stats (
                product_id, average_rating, review_count
            )
            VALUES (
                %(product_id)s, %(average_rating)s, %(review_count)s
            )
            ON CONFLICT (product_id) DO UPDATE
            SET average_rating = EXCLUDED.average_rating,
                review_count = EXCLUDED.review_count
            """,
            rows,
        )

    def _upsert_search_documents(self, cur: Any, rows: list[dict[str, Any]]) -> None:
        for row in rows:
            cur.execute(
                """
                INSERT INTO product_search_documents (
                    product_id, search_text, search_tsv
                )
                VALUES (
                    %(product_id)s,
                    %(search_text)s,
                    to_tsvector('english', unaccent(%(search_text)s))
                )
                ON CONFLICT (product_id) DO UPDATE
                SET search_text = EXCLUDED.search_text,
                    search_tsv = to_tsvector('english', unaccent(EXCLUDED.search_text))
                """,
                row,
            )
