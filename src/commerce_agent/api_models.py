from __future__ import annotations

from pydantic import BaseModel, Field


class RoutedMessageResponse(BaseModel):
    intent: str
    content: str
    analysis: dict[str, object] | None = None
    matches: list[dict[str, object]] = Field(default_factory=list)
    limit: int = Field(default=5, ge=1, le=20)
