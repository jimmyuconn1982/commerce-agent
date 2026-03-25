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
    limit: int = Field(default=5, ge=1, le=20)
