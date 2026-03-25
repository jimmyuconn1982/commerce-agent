import json
from pathlib import Path

from commerce_agent.catalog import Catalog
from commerce_agent.seed_data import build_tiny_seed, write_tiny_seed


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


def test_write_tiny_seed_writes_json_bundle(tmp_path: Path) -> None:
    seed_path = tmp_path / "tiny_seed.json"
    write_tiny_seed(seed_path)

    payload = json.loads(seed_path.read_text(encoding="utf-8"))
    assert "products" in payload
    assert "product_search_documents" in payload
    assert payload["products"][0]["id"] > 0
