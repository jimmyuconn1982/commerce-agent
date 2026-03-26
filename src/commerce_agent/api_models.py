from __future__ import annotations

"""API-facing response models.

Inputs:
- backend pipeline results converted into plain dictionaries

Outputs:
- validated response shapes returned by FastAPI

Role:
- keep the web contract separate from internal dataclasses

Upgrade path:
- add debug, trace, and tool-level response schemas without changing core models
"""

from pydantic import BaseModel, Field


class RoutedMessageResponse(BaseModel):
    """Web response schema for one routed chat or retrieval request."""

    intent: str
    content: str
    analysis: dict[str, object] | None = None
    matches: list[dict[str, object]] = Field(default_factory=list)
    trace: dict[str, object] | None = None
    limit: int = Field(default=5, ge=1, le=20)


class DebugProductResponse(BaseModel):
    """Debug response schema for one product record joined from PostgreSQL."""

    product_id: int
    sku: str
    title: str
    category_name: str
    brand: str | None = None
    short_description: str
    long_description: str
    primary_image_url: str | None = None
    thumbnail_url: str | None = None
    image_alt_text: str | None = None
    seller_name: str | None = None
    seller_rating: float | None = None
    price: float | None = None
    currency: str | None = None
    inventory_count: int | None = None
    review_count: int | None = None
    average_rating: float | None = None
    product_url: str | None = None
    search_text: str | None = None
    text_tags: list[str] = Field(default_factory=list)
    image_tags: list[str] = Field(default_factory=list)
    attributes: dict[str, object] = Field(default_factory=dict)
    has_text_embedding: bool = False
    has_image_embedding: bool = False
