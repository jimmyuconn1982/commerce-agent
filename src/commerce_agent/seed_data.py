from __future__ import annotations

"""Seed-data generation and loading utilities.

Inputs:
- the MVP JSON catalog
- local database connection settings

Outputs:
- a normalized tiny-seed JSON bundle
- loaded rows inside the target PostgreSQL schema

Role:
- provide the first repeatable data path from local fixtures into the database
- keep seed generation separate from runtime retrieval code

Upgrade path:
- add public dataset ingestion and richer synthetic offer generation
- extend the loader to build embeddings after core product rows exist
"""

from dataclasses import asdict, dataclass
import json
import os
from pathlib import Path
from typing import Any

from .catalog import Catalog
from .models import Product

DEFAULT_DATABASE_URL = "postgresql://commerce_agent:commerce_agent@127.0.0.1:5432/commerce_agent"
DEFAULT_TINY_SEED_PATH = Path(__file__).resolve().parents[2] / "db" / "seeds" / "tiny_seed.json"

CATEGORY_ID_BASE = 723460000000000000
SELLER_ID_BASE = 723470000000000000
MEDIA_ID_BASE = 723480000000000000
OFFER_ID_BASE = 723490000000000000


@dataclass(slots=True)
class TinySeedBundle:
    """Normalized tiny-seed payload ready to serialize or load."""

    categories: list[dict[str, Any]]
    products: list[dict[str, Any]]
    product_media: list[dict[str, Any]]
    sellers: list[dict[str, Any]]
    product_offers: list[dict[str, Any]]
    product_review_stats: list[dict[str, Any]]
    product_search_documents: list[dict[str, Any]]
    product_embeddings: list[dict[str, Any]]


def build_tiny_seed(catalog: Catalog) -> TinySeedBundle:
    """Build a deterministic tiny seed from the current MVP catalog."""
    categories = _build_categories(catalog.all())
    category_ids = {item["name"]: item["id"] for item in categories}

    sellers = [
        {
            "id": SELLER_ID_BASE + 1,
            "seller_code": "urban-hub",
            "name": "Urban Hub",
            "rating": 4.7,
            "seller_url": "https://example.com/sellers/urban-hub",
            "location": "San Francisco, CA",
            "is_verified": True,
        },
        {
            "id": SELLER_ID_BASE + 2,
            "seller_code": "trail-works",
            "name": "Trail Works",
            "rating": 4.6,
            "seller_url": "https://example.com/sellers/trail-works",
            "location": "Denver, CO",
            "is_verified": True,
        },
        {
            "id": SELLER_ID_BASE + 3,
            "seller_code": "home-office-co",
            "name": "Home Office Co",
            "rating": 4.5,
            "seller_url": "https://example.com/sellers/home-office-co",
            "location": "Seattle, WA",
            "is_verified": True,
        },
    ]

    products: list[dict[str, Any]] = []
    media_rows: list[dict[str, Any]] = []
    offer_rows: list[dict[str, Any]] = []
    review_rows: list[dict[str, Any]] = []
    search_rows: list[dict[str, Any]] = []

    for index, product in enumerate(catalog.all(), start=1):
        products.append(_build_product_row(product, category_ids[product.category]))
        media_rows.append(_build_media_row(product, index))
        offer_rows.append(_build_offer_row(product, index, sellers))
        review_rows.append(_build_review_row(product))
        search_rows.append(_build_search_document_row(product))

    return TinySeedBundle(
        categories=categories,
        products=products,
        product_media=media_rows,
        sellers=sellers,
        product_offers=offer_rows,
        product_review_stats=review_rows,
        product_search_documents=search_rows,
        product_embeddings=[],
    )


def write_tiny_seed(path: Path = DEFAULT_TINY_SEED_PATH) -> Path:
    """Generate the tiny seed bundle and write it to disk."""
    bundle = build_tiny_seed(Catalog.from_json())
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(asdict(bundle), indent=2), encoding="utf-8")
    return path


def load_seed_data(seed_path: Path = DEFAULT_TINY_SEED_PATH, database_url: str | None = None) -> None:
    """Load one normalized seed bundle into PostgreSQL with upserts."""
    import psycopg
    from psycopg.types.json import Json

    data = json.loads(seed_path.read_text(encoding="utf-8"))
    database_url = database_url or os.getenv("DATABASE_URL", DEFAULT_DATABASE_URL)

    with psycopg.connect(database_url) as conn:
        with conn.cursor() as cur:
            _upsert_categories(cur, data["categories"])
            _upsert_products(cur, data["products"], Json)
            _upsert_product_media(cur, data["product_media"])
            _upsert_sellers(cur, data["sellers"])
            _upsert_product_offers(cur, data["product_offers"])
            _upsert_review_stats(cur, data["product_review_stats"])
            _upsert_search_documents(cur, data["product_search_documents"])
        conn.commit()


def build_tiny_seed_cli() -> None:
    """CLI wrapper that writes the local tiny seed JSON bundle."""
    import argparse

    parser = argparse.ArgumentParser(description="Build tiny seed data from the local MVP catalog")
    parser.add_argument("--output", type=Path, default=DEFAULT_TINY_SEED_PATH)
    args = parser.parse_args()
    path = write_tiny_seed(args.output)
    print(path)


def load_seed_data_cli() -> None:
    """CLI wrapper that loads a normalized seed bundle into PostgreSQL."""
    import argparse

    parser = argparse.ArgumentParser(description="Load seed data into the local PostgreSQL database")
    parser.add_argument("--seed-path", type=Path, default=DEFAULT_TINY_SEED_PATH)
    parser.add_argument("--database-url", default=os.getenv("DATABASE_URL", DEFAULT_DATABASE_URL))
    args = parser.parse_args()
    load_seed_data(seed_path=args.seed_path, database_url=args.database_url)
    print(f"loaded seed data from {args.seed_path}")


def _build_categories(products: list[Product]) -> list[dict[str, Any]]:
    category_names = sorted({product.category for product in products})
    return [
        {
            "id": CATEGORY_ID_BASE + index,
            "name": name,
            "parent_id": None,
        }
        for index, name in enumerate(category_names, start=1)
    ]


def _build_product_row(product: Product, category_id: int) -> dict[str, Any]:
    return {
        "id": product.id,
        "sku": f"sku-{product.id}",
        "title": product.name,
        "short_description": product.description,
        "long_description": f"{product.description} {product.visual_description}",
        "brand": _infer_brand(product),
        "category_id": category_id,
        "status": "active",
        "attributes_jsonb": {
            "tags": product.tags,
            "image_tags": product.image_tags,
        },
    }


def _build_media_row(product: Product, index: int) -> dict[str, Any]:
    return {
        "id": MEDIA_ID_BASE + index,
        "product_id": product.id,
        "media_type": "image",
        "url": product.image_url,
        "thumbnail_url": product.image_url,
        "sort_order": 0,
        "alt_text": product.name,
        "width": None,
        "height": None,
        "is_primary": True,
    }


def _build_offer_row(product: Product, index: int, sellers: list[dict[str, Any]]) -> dict[str, Any]:
    seller = sellers[(index - 1) % len(sellers)]
    return {
        "id": OFFER_ID_BASE + index,
        "product_id": product.id,
        "seller_id": seller["id"],
        "price": _price_for_product(product, index),
        "currency": "USD",
        "inventory_count": 20 + (index * 7),
        "product_url": f"https://example.com/products/{product.id}",
        "shipping_info": "Standard shipping in 3-5 business days",
        "is_active": True,
    }


def _build_review_row(product: Product) -> dict[str, Any]:
    return {
        "product_id": product.id,
        "average_rating": product.rating,
        "review_count": max(12, int(product.rating * 42)),
    }


def _build_search_document_row(product: Product) -> dict[str, Any]:
    parts = [
        product.name,
        product.category,
        product.description,
        " ".join(product.tags),
        " ".join(product.image_tags),
        product.visual_description,
    ]
    return {
        "product_id": product.id,
        "search_text": " ".join(part.strip() for part in parts if part.strip()),
    }


def _infer_brand(product: Product) -> str:
    words = product.name.split()
    if len(words) >= 2:
        return " ".join(words[:2])
    return words[0]


def _price_for_product(product: Product, index: int) -> float:
    category_prices = {
        "electronics": 129.0,
        "furniture": 399.0,
        "footwear": 89.0,
        "apparel": 59.0,
        "outdoors": 39.0,
    }
    base = category_prices.get(product.category, 49.0)
    return round(base + (index * 3.5), 2)


def _upsert_categories(cur, rows: list[dict[str, Any]]) -> None:
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


def _upsert_products(cur, rows: list[dict[str, Any]], json_adapter) -> None:
    payload = []
    for row in rows:
        payload.append({**row, "attributes_jsonb": json_adapter(row["attributes_jsonb"])})
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


def _upsert_product_media(cur, rows: list[dict[str, Any]]) -> None:
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


def _upsert_sellers(cur, rows: list[dict[str, Any]]) -> None:
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


def _upsert_product_offers(cur, rows: list[dict[str, Any]]) -> None:
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


def _upsert_review_stats(cur, rows: list[dict[str, Any]]) -> None:
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


def _upsert_search_documents(cur, rows: list[dict[str, Any]]) -> None:
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
