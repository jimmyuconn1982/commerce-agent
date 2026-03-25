from __future__ import annotations

import json
from pathlib import Path

from .models import Product


DEFAULT_CATALOG_PATH = Path(__file__).resolve().parents[2] / "data" / "catalog.json"


class Catalog:
    def __init__(self, products: list[Product]) -> None:
        self._products = products
        self._by_id = {product.id: product for product in products}

    @classmethod
    def from_json(cls, path: Path | None = None) -> "Catalog":
        raw = json.loads((path or DEFAULT_CATALOG_PATH).read_text())
        return cls(products=[Product(**item) for item in raw])

    def all(self) -> list[Product]:
        return list(self._products)

    def get(self, product_id: str) -> Product:
        try:
            return self._by_id[product_id]
        except KeyError as exc:
            raise KeyError(f"unknown product id: {product_id}") from exc
