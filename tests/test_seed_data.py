import json
from pathlib import Path

from commerce_agent.catalog import Catalog
from commerce_agent.seed_data import build_public_seed, build_tiny_seed, write_public_seed, write_tiny_seed


def test_build_tiny_seed_matches_catalog_shape() -> None:
    catalog = Catalog.from_json()
    bundle = build_tiny_seed(catalog)

    assert len(bundle.products) == len(catalog.all())
    assert len(bundle.product_media) == len(catalog.all())
    assert len(bundle.product_offers) == len(catalog.all())
    assert len(bundle.product_review_stats) == len(catalog.all())
    assert len(bundle.product_search_documents) == len(catalog.all())
    assert bundle.product_embeddings == []
    assert bundle.categories
    assert bundle.sellers
    assert bundle.product_media[0]["product_id"] == bundle.products[0]["id"]


def test_write_tiny_seed_writes_json_bundle(tmp_path: Path) -> None:
    seed_path = tmp_path / "tiny_seed.json"
    write_tiny_seed(seed_path)

    payload = json.loads(seed_path.read_text(encoding="utf-8"))
    assert "products" in payload
    assert "product_search_documents" in payload
    assert payload["products"][0]["id"] > 0


def test_build_public_seed_keeps_media_and_search_docs_on_same_product() -> None:
    products = [
        {
            "id": 101,
            "title": "Camera Backpack",
            "description": "Water-resistant backpack for mirrorless camera kits.",
            "category": "bags",
            "price": 129.99,
            "rating": 4.6,
            "stock": 18,
            "tags": ["camera", "travel", "backpack"],
            "brand": "Northwind",
            "sku": "NOR-CAM-101",
            "shippingInformation": "Ships in 48 hours",
            "availabilityStatus": "In Stock",
            "images": ["https://cdn.example.com/camera-backpack.webp"],
            "thumbnail": "https://cdn.example.com/camera-backpack-thumb.webp",
            "reviews": [{"rating": 5}, {"rating": 4}],
        }
    ]

    class StubMetadataEnricher:
        def enrich(self, source_product):
            return {
                "search_terms": ["camera", "travel"],
                "cooking_uses": [],
                "audience_terms": ["bags"],
            }

    bundle = build_public_seed(products, metadata_enricher=StubMetadataEnricher())

    assert len(bundle.products) == 1
    assert len(bundle.product_media) == 1
    assert len(bundle.product_search_documents) == 1
    assert bundle.product_media[0]["product_id"] == bundle.products[0]["id"]
    assert bundle.product_search_documents[0]["product_id"] == bundle.products[0]["id"]
    assert bundle.product_media[0]["url"] == "https://cdn.example.com/camera-backpack.webp"
    assert "Camera Backpack" in bundle.product_search_documents[0]["search_text"]
    assert bundle.products[0]["attributes_jsonb"]["search_terms"] == ["camera", "travel"]
    assert bundle.products[0]["attributes_jsonb"]["cooking_uses"] == []
    assert bundle.products[0]["attributes_jsonb"]["audience_terms"] == ["bags"]
    assert bundle.products[0]["id"] == build_public_seed(products, metadata_enricher=StubMetadataEnricher()).products[0]["id"]


def test_build_public_seed_uses_metadata_enricher_output() -> None:
    class StubMetadataEnricher:
        def enrich(self, source_product):
            return {
                "search_terms": ["food", "ingredient"],
                "cooking_uses": ["stir fry"],
                "audience_terms": ["human food"],
            }

    bundle = build_public_seed(
        [
            {
                "id": 25,
                "title": "Green Bell Pepper",
                "description": "Fresh green bell pepper for salads, stir-fries, and other dishes.",
                "category": "groceries",
                "price": 1.29,
                "rating": 4.1,
                "stock": 33,
                "tags": ["vegetables"],
                "brand": "Green Bell Pepper",
                "sku": "GRO-BRD-GRE-025",
                "shippingInformation": "Ships in 48 hours",
                "availabilityStatus": "In Stock",
                "images": ["https://cdn.example.com/pepper.webp"],
                "thumbnail": "https://cdn.example.com/pepper-thumb.webp",
                "reviews": [{"rating": 4}],
            }
        ],
        metadata_enricher=StubMetadataEnricher(),
    )

    attributes = bundle.products[0]["attributes_jsonb"]
    assert "food" in attributes["search_terms"]
    assert "stir fry" in attributes["cooking_uses"]
    assert "human food" in attributes["audience_terms"]
    assert "stir fry" in bundle.product_search_documents[0]["search_text"]


def test_write_public_seed_writes_public_bundle(tmp_path: Path, monkeypatch) -> None:
    from commerce_agent import seed_data

    monkeypatch.setattr(
        seed_data,
        "fetch_dummyjson_products",
        lambda limit=50, skip=0: [
            {
                "id": 1,
                "title": "Desk Lamp",
                "description": "Adjustable LED desk lamp.",
                "category": "home-decoration",
                "price": 39.99,
                "rating": 4.4,
                "stock": 25,
                "tags": ["lamp", "led", "desk"],
                "brand": "Glow",
                "sku": "GLO-DESK-1",
                "shippingInformation": "Ships today",
                "availabilityStatus": "In Stock",
                "images": ["https://cdn.example.com/desk-lamp.webp"],
                "thumbnail": "https://cdn.example.com/desk-lamp-thumb.webp",
                "reviews": [{"rating": 5}],
            }
        ],
    )
    seed_path = tmp_path / "public_seed.json"

    write_public_seed(seed_path, limit=1)

    payload = json.loads(seed_path.read_text(encoding="utf-8"))
    assert len(payload["products"]) == 1
    assert len(payload["product_media"]) == 1
    assert payload["product_media"][0]["product_id"] == payload["products"][0]["id"]
