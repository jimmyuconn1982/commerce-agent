from __future__ import annotations

"""Centralized runtime settings for models and local server behavior.

Inputs:
- environment variables for router, embeddings, vision, and web runtime

Outputs:
- one cached `CommerceAgentSettings` object shared across modules

Role:
- keep model/provider configuration in one place
- avoid scattering env lookups across the codebase

Upgrade path:
- move more database and ingest settings here as the backend grows
- replace direct env loading with pydantic-settings later if needed
"""

from dataclasses import dataclass
import os

from .env import load_dotenv

load_dotenv()


@dataclass(slots=True)
class RouterSettings:
    """Configuration for intent routing providers and small models."""

    provider: str
    model_name: str
    base_url: str
    api_key: str


@dataclass(slots=True)
class EmbeddingSettings:
    """Configuration for semantic embedding providers and dimensions."""

    provider: str
    model_name: str
    base_url: str
    api_key: str
    dimensions: int


@dataclass(slots=True)
class VisionSettings:
    """Configuration for vision analysis and local mock behavior."""

    provider: str
    model_name: str
    api_key: str
    base_url: str
    mock_enabled: bool
    mock_response: str


@dataclass(slots=True)
class WebSettings:
    """Configuration for the local FastAPI host and port."""

    host: str
    port: int


@dataclass(slots=True)
class CommerceAgentSettings:
    """Aggregated runtime settings shared across agent modules."""

    router: RouterSettings
    embeddings: EmbeddingSettings
    vision: VisionSettings
    web: WebSettings


def get_settings() -> CommerceAgentSettings:
    """Load and cache runtime settings from environment variables."""
    return CommerceAgentSettings(
        router=RouterSettings(
            provider=(os.getenv("COMMERCE_AGENT_ROUTER_PROVIDER") or "auto").strip().lower(),
            model_name=os.getenv("COMMERCE_AGENT_ROUTER_MODEL") or "glm-4-flash",
            base_url=(os.getenv("BIGMODEL_BASE_URL") or "https://open.bigmodel.cn/api/paas/v4").rstrip("/"),
            api_key=os.getenv("BIGMODEL_API_KEY", ""),
        ),
        embeddings=EmbeddingSettings(
            provider=(os.getenv("COMMERCE_AGENT_EMBEDDING_PROVIDER") or "deterministic").strip().lower(),
            model_name=os.getenv("BIGMODEL_EMBEDDING_MODEL") or "embedding-3",
            base_url=(os.getenv("BIGMODEL_BASE_URL") or "https://open.bigmodel.cn/api/paas/v4").rstrip("/"),
            api_key=os.getenv("BIGMODEL_API_KEY", ""),
            dimensions=int(os.getenv("BIGMODEL_EMBEDDING_DIMENSIONS") or "1024"),
        ),
        vision=VisionSettings(
            provider=(os.getenv("COMMERCE_AGENT_VISION_PROVIDER") or "bigmodel").strip().lower(),
            model_name=os.getenv("COMMERCE_AGENT_VISION_MODEL") or "glm-4.5v",
            api_key=os.getenv("COMMERCE_AGENT_VISION_API_KEY") or os.getenv("BIGMODEL_API_KEY", ""),
            base_url=(os.getenv("COMMERCE_AGENT_VISION_BASE_URL") or os.getenv("BIGMODEL_BASE_URL") or "https://open.bigmodel.cn/api/paas/v4").rstrip("/"),
            mock_enabled=os.getenv("COMMERCE_AGENT_MOCK_VISION") == "1",
            mock_response=os.getenv("COMMERCE_AGENT_MOCK_VISION_RESPONSE", "").strip(),
        ),
        web=WebSettings(
            host=os.getenv("COMMERCE_AGENT_HOST", "127.0.0.1"),
            port=int(os.getenv("COMMERCE_AGENT_PORT", "8000")),
        ),
    )
