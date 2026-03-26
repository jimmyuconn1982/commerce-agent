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
import re
from urllib.parse import quote_plus
from urllib.request import Request, urlopen
from typing import Any

from .catalog import Catalog
from .db_write import DatabaseWriter
from .ids import SnowflakeLikeIdGenerator
from .models import Product

DEFAULT_DATABASE_URL = "postgresql://commerce_agent:commerce_agent@127.0.0.1:5432/commerce_agent"
DEFAULT_TINY_SEED_PATH = Path(__file__).resolve().parents[2] / "db" / "seeds" / "tiny_seed.json"
DEFAULT_PUBLIC_SEED_PATH = Path(__file__).resolve().parents[2] / "db" / "seeds" / "public_seed_50.json"


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
    generator = SnowflakeLikeIdGenerator()
    categories = _build_categories(catalog.all(), generator=generator)
    category_ids = {item["name"]: item["id"] for item in categories}

    sellers = [
        {
            "id": generator.stable("tiny_seller", "urban-hub"),
            "seller_code": "urban-hub",
            "name": "Urban Hub",
            "rating": 4.7,
            "seller_url": "https://example.com/sellers/urban-hub",
            "location": "San Francisco, CA",
            "is_verified": True,
        },
        {
            "id": generator.stable("tiny_seller", "trail-works"),
            "seller_code": "trail-works",
            "name": "Trail Works",
            "rating": 4.6,
            "seller_url": "https://example.com/sellers/trail-works",
            "location": "Denver, CO",
            "is_verified": True,
        },
        {
            "id": generator.stable("tiny_seller", "home-office-co"),
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

    for product in catalog.all():
        products.append(_build_product_row(product, category_ids[product.category]))
        media_rows.append(_build_media_row(product, generator=generator))
        offer_rows.append(_build_offer_row(product, sellers, generator=generator))
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


def fetch_dummyjson_products(limit: int = 50, skip: int = 0) -> list[dict[str, Any]]:
    """Fetch public product rows from DummyJSON for local testing."""
    url = (
        "https://dummyjson.com/products"
        f"?limit={limit}&skip={skip}"
        "&select=id,title,description,category,price,rating,stock,tags,brand,sku,shippingInformation,"
        "availabilityStatus,images,thumbnail,reviews"
    )
    request = Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urlopen(request) as response:
        payload = json.loads(response.read().decode("utf-8"))
    return payload["products"]


def build_public_seed(products: list[dict[str, Any]]) -> TinySeedBundle:
    """Build one normalized seed bundle from public product rows."""
    generator = SnowflakeLikeIdGenerator()
    categories = _build_named_categories(
        sorted({_normalize_category_name(str(item.get("category", "misc"))) for item in products}),
        entity="public_category",
        generator=generator,
    )
    category_ids = {item["name"]: item["id"] for item in categories}
    sellers = _build_public_sellers(products, generator=generator)
    seller_ids = {item["seller_code"]: item["id"] for item in sellers}

    product_rows: list[dict[str, Any]] = []
    media_rows: list[dict[str, Any]] = []
    offer_rows: list[dict[str, Any]] = []
    review_rows: list[dict[str, Any]] = []
    search_rows: list[dict[str, Any]] = []

    for source_product in products:
        product_id = generator.stable("public_product", f"dummyjson:{source_product['id']}")
        category_name = _normalize_category_name(str(source_product.get("category", "misc")))
        image_tags = _public_image_tags(source_product)
        seller_code = _public_seller_code(source_product)
        brand = str(source_product.get("brand") or source_product.get("title") or "Unknown Brand").strip()
        image_url = _primary_image_url(source_product)
        description = str(source_product.get("description") or "").strip()
        title = str(source_product.get("title") or "").strip()
        tags = [str(tag).strip().lower() for tag in source_product.get("tags", []) if str(tag).strip()]
        review_count = len(source_product.get("reviews", []))
        rating = float(source_product.get("rating") or 0.0)

        product_rows.append(
            {
                "id": product_id,
                "sku": str(source_product.get("sku") or f"dummyjson-{source_product['id']}"),
                "title": title,
                "short_description": description,
                "long_description": f"{description} {_image_summary_from_product(source_product)}".strip(),
                "brand": brand,
                "category_id": category_ids[category_name],
                "status": "active",
                "attributes_jsonb": {
                    "tags": tags,
                    "image_tags": image_tags,
                    "source": "dummyjson",
                    "source_product_id": int(source_product["id"]),
                },
            }
        )
        media_rows.append(
            {
                "id": generator.stable("public_media", product_id),
                "product_id": product_id,
                "media_type": "image",
                "url": image_url,
                "thumbnail_url": str(source_product.get("thumbnail") or image_url),
                "sort_order": 0,
                "alt_text": title,
                "width": None,
                "height": None,
                "is_primary": True,
            }
        )
        offer_rows.append(
            {
                "id": generator.stable("public_offer", f"{product_id}:{seller_ids[seller_code]}"),
                "product_id": product_id,
                "seller_id": seller_ids[seller_code],
                "price": float(source_product.get("price") or 0.0),
                "currency": "USD",
                "inventory_count": max(0, int(source_product.get("stock") or 0)),
                "product_url": f"https://dummyjson.com/products/{source_product['id']}",
                "shipping_info": str(source_product.get("shippingInformation") or "Ships in 3-5 business days"),
                "is_active": True,
            }
        )
        review_rows.append(
            {
                "product_id": product_id,
                "average_rating": rating,
                "review_count": review_count,
            }
        )
        search_rows.append(
            {
                "product_id": product_id,
                "search_text": " ".join(
                    part.strip()
                    for part in [
                        title,
                        category_name,
                        brand,
                        description,
                        " ".join(tags),
                        " ".join(image_tags),
                    ]
                    if part.strip()
                ),
            }
        )

    return TinySeedBundle(
        categories=categories,
        products=product_rows,
        product_media=media_rows,
        sellers=sellers,
        product_offers=offer_rows,
        product_review_stats=review_rows,
        product_search_documents=search_rows,
        product_embeddings=[],
    )


def write_public_seed(
    path: Path = DEFAULT_PUBLIC_SEED_PATH,
    *,
    limit: int = 50,
    skip: int = 0,
) -> Path:
    """Fetch one public product sample and write it as a normalized seed bundle."""
    bundle = build_public_seed(fetch_dummyjson_products(limit=limit, skip=skip))
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(asdict(bundle), indent=2), encoding="utf-8")
    return path


def load_seed_data(
    seed_path: Path = DEFAULT_TINY_SEED_PATH,
    database_url: str | None = None,
    *,
    truncate_first: bool = False,
) -> None:
    """Load one normalized seed bundle into PostgreSQL with upserts."""
    import psycopg

    data = json.loads(seed_path.read_text(encoding="utf-8"))
    database_url = database_url or os.getenv("DATABASE_URL", DEFAULT_DATABASE_URL)

    with psycopg.connect(database_url) as conn:
        writer = DatabaseWriter(conn)
        if truncate_first:
            writer.truncate_seed_tables()
        writer.load_seed_bundle(data)
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
    parser.add_argument("--truncate-first", action="store_true")
    args = parser.parse_args()
    load_seed_data(
        seed_path=args.seed_path,
        database_url=args.database_url,
        truncate_first=args.truncate_first,
    )
    print(f"loaded seed data from {args.seed_path}")


def build_public_seed_cli() -> None:
    """CLI wrapper that fetches and writes one public 50-product seed bundle."""
    import argparse

    parser = argparse.ArgumentParser(description="Build a public product seed bundle from DummyJSON")
    parser.add_argument("--output", type=Path, default=DEFAULT_PUBLIC_SEED_PATH)
    parser.add_argument("--limit", type=int, default=50)
    parser.add_argument("--skip", type=int, default=0)
    args = parser.parse_args()
    path = write_public_seed(args.output, limit=args.limit, skip=args.skip)
    print(path)


def _build_categories(products: list[Product], *, generator: SnowflakeLikeIdGenerator) -> list[dict[str, Any]]:
    category_names = sorted({product.category for product in products})
    return _build_named_categories(category_names, entity="tiny_category", generator=generator)


def _build_named_categories(
    names: list[str],
    *,
    entity: str,
    generator: SnowflakeLikeIdGenerator,
) -> list[dict[str, Any]]:
    return [{"id": generator.stable(entity, name), "name": name, "parent_id": None} for name in names]


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


def _build_media_row(product: Product, *, generator: SnowflakeLikeIdGenerator) -> dict[str, Any]:
    return {
        "id": generator.stable("tiny_media", product.id),
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


def _build_offer_row(
    product: Product,
    sellers: list[dict[str, Any]],
    *,
    generator: SnowflakeLikeIdGenerator,
) -> dict[str, Any]:
    seller = sellers[product.id % len(sellers)]
    return {
        "id": generator.stable("tiny_offer", f"{product.id}:{seller['id']}"),
        "product_id": product.id,
        "seller_id": seller["id"],
        "price": _price_for_product(product),
        "currency": "USD",
        "inventory_count": 20 + ((product.id % 9) * 7),
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


def _build_public_sellers(products: list[dict[str, Any]], *, generator: SnowflakeLikeIdGenerator) -> list[dict[str, Any]]:
    sellers: list[dict[str, Any]] = []
    seen: set[str] = set()
    for source_product in products:
        seller_code = _public_seller_code(source_product)
        if seller_code in seen:
            continue
        seen.add(seller_code)
        brand = str(source_product.get("brand") or source_product.get("title") or "Marketplace Seller").strip()
        sellers.append(
            {
                "id": generator.stable("public_seller", seller_code),
                "seller_code": seller_code,
                "name": f"{brand} Store",
                "rating": round(max(3.8, min(5.0, float(source_product.get('rating') or 4.2))), 2),
                "seller_url": f"https://example.com/sellers/{quote_plus(seller_code)}",
                "location": "Online",
                "is_verified": True,
            }
        )
    return sellers


def _public_seller_code(source_product: dict[str, Any]) -> str:
    brand = str(source_product.get("brand") or source_product.get("title") or "marketplace").strip().lower()
    slug = re.sub(r"[^a-z0-9]+", "-", brand).strip("-")
    return slug or f"seller-{source_product['id']}"


def _normalize_category_name(raw_category: str) -> str:
    return raw_category.strip().lower().replace("-", " ")


def _primary_image_url(source_product: dict[str, Any]) -> str:
    images = source_product.get("images") or []
    if images:
        return str(images[0])
    return str(source_product.get("thumbnail") or "")


def _public_image_tags(source_product: dict[str, Any]) -> list[str]:
    raw_tags = [str(tag).strip().lower() for tag in source_product.get("tags", []) if str(tag).strip()]
    title_tokens = [
        token
        for token in re.findall(r"[a-z0-9]+", str(source_product.get("title") or "").lower())
        if len(token) > 2
    ]
    category_tokens = [
        token
        for token in re.findall(r"[a-z0-9]+", str(source_product.get("category") or "").lower())
        if len(token) > 2
    ]
    seen: set[str] = set()
    result: list[str] = []
    for token in raw_tags + category_tokens + title_tokens[:4]:
        if token not in seen:
            seen.add(token)
            result.append(token)
    return result[:8]


def _image_summary_from_product(source_product: dict[str, Any]) -> str:
    title = str(source_product.get("title") or "").strip()
    category = _normalize_category_name(str(source_product.get("category") or "product"))
    tags = ", ".join(_public_image_tags(source_product)[:4])
    return f"{title} product image for {category}. Visual hints: {tags}."


def _infer_brand(product: Product) -> str:
    words = product.name.split()
    if len(words) >= 2:
        return " ".join(words[:2])
    return words[0]


def _price_for_product(product: Product) -> float:
    category_prices = {
        "electronics": 129.0,
        "furniture": 399.0,
        "footwear": 89.0,
        "apparel": 59.0,
        "outdoors": 39.0,
    }
    base = category_prices.get(product.category, 49.0)
    return round(base + ((product.id % 11) * 3.5), 2)

