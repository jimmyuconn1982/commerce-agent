from __future__ import annotations

"""Catalog loader and in-memory product store.

Inputs:
- JSON catalog files shaped like `Product`

Outputs:
- a simple in-memory `Catalog` object with lookup helpers

Role:
- act as the current product database abstraction
- keep storage concerns away from router and retrieval code

Upgrade path:
- replace JSON loading with SQLite, Postgres, or a vector store later
- preserve the `Catalog` interface so retrieval logic stays unchanged
"""

import json
from pathlib import Path

from .models import Product


DEFAULT_CATALOG_PATH = Path(__file__).resolve().parents[2] / "data" / "catalog.json"


class Catalog:
    """In-memory catalog facade backed by structured product records."""

    def __init__(self, products: list[Product]) -> None:
        self._products = products
        self._by_id = {product.id: product for product in products}

    @classmethod
    def from_json(cls, path: Path | None = None) -> "Catalog":
        """Load catalog data from JSON into `Product` objects."""
        raw = json.loads((path or DEFAULT_CATALOG_PATH).read_text())
        return cls(products=[Product(**item) for item in raw])

    def all(self) -> list[Product]:
        """Return a copy of all products for retrieval and debugging."""
        return list(self._products)

    def get(self, product_id: int) -> Product:
        """Look up one product by id and fail loudly if it is unknown."""
        try:
            return self._by_id[product_id]
        except KeyError as exc:
            raise KeyError(f"unknown product id: {product_id}") from exc
