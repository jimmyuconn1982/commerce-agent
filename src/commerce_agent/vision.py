from __future__ import annotations

"""Vision analysis adapters.

Inputs:
- a local image path
- provider settings for BigModel, OpenAI, or mock mode

Outputs:
- `VisionAnalysis` with a short summary and visual tags

Role:
- isolate image understanding from the rest of the agent
- support provider switching without changing retrieval callers

Upgrade path:
- add richer structured extraction, embeddings, or multi-image support
- split provider implementations into separate modules if the layer grows
"""

import base64
import json
import mimetypes
from pathlib import Path
from typing import Protocol
from urllib.request import Request, urlopen

from .config import get_settings
from .models import VisionAnalysis


class VisionAnalyzer(Protocol):
    """Protocol for pluggable image analyzers."""

    def analyze(self, image_path: Path) -> VisionAnalysis:
        """Return a structured visual summary for one image path."""
        ...


class MockVisionAnalyzer:
    """Deterministic local image analyzer for development and tests."""

    def analyze(self, image_path: Path) -> VisionAnalysis:
        """Return a stable mock summary and tags for one local image."""
        raw = get_settings().vision.mock_response
        if raw:
            return _parse_response(image_path=image_path, text=raw)

        stem = image_path.stem.replace("-", " ").replace("_", " ").strip() or "product image"
        summary = f"summary: mock analysis for {stem}"
        tags = "tags: product, mock, image, accessory, catalog"
        return _parse_response(image_path=image_path, text=f"{summary}\n{tags}")


class OpenAIVisionAnalyzer:
    """OpenAI-backed vision adapter with optional local mock behavior."""

    def __init__(self, model: str | None = None) -> None:
        self._client = None
        self.model = model or "gpt-4.1-mini"

    def analyze(self, image_path: Path) -> VisionAnalysis:
        """Analyze one local image and return summary plus visual tags."""
        _validate_image_path(image_path)
        settings = get_settings().vision
        if not settings.api_key:
            if settings.mock_enabled:
                return MockVisionAnalyzer().analyze(image_path)
            raise ValueError("COMMERCE_AGENT_VISION_API_KEY or OPENAI_API_KEY is required for image understanding")

        if self._client is None:
            from openai import OpenAI

            self._client = OpenAI(api_key=settings.api_key)

        media_type = mimetypes.guess_type(image_path.name)[0] or "image/jpeg"
        base64_image = base64.b64encode(image_path.read_bytes()).decode("utf-8")
        response = self._client.responses.create(
            model=self.model,
            input=[
                {
                    "role": "user",
                    "content": [
                        {"type": "input_text", "text": _vision_prompt()},
                        {
                            "type": "input_image",
                            "image_url": f"data:{media_type};base64,{base64_image}",
                        },
                    ],
                }
            ],
        )
        return _parse_response(image_path=image_path, text=response.output_text)


class BigModelVisionAnalyzer:
    """BigModel-backed vision adapter using chat/completions image understanding."""

    def __init__(self, model: str | None = None) -> None:
        settings = get_settings().vision
        self.api_key = settings.api_key
        self.base_url = settings.base_url
        self.model = model or settings.model_name or "glm-4.5v"

    def analyze(self, image_path: Path) -> VisionAnalysis:
        """Analyze one local image with BigModel and return summary plus tags."""
        _validate_image_path(image_path)
        settings = get_settings().vision
        if not self.api_key:
            if settings.mock_enabled:
                return MockVisionAnalyzer().analyze(image_path)
            raise ValueError("COMMERCE_AGENT_VISION_API_KEY or BIGMODEL_API_KEY is required for image understanding")

        image_base64 = base64.b64encode(image_path.read_bytes()).decode("utf-8")
        body = json.dumps(
            {
                "model": self.model,
                "messages": [
                    {
                        "role": "user",
                        "content": [
                            {
                                "type": "image_url",
                                "image_url": {
                                    "url": image_base64,
                                },
                            },
                            {
                                "type": "text",
                                "text": _vision_prompt(),
                            },
                        ],
                    }
                ],
            }
        ).encode("utf-8")
        request = Request(
            f"{self.base_url}/chat/completions",
            data=body,
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
                "User-Agent": "commerce-agent/0.1",
            },
            method="POST",
        )
        with urlopen(request) as response:
            payload = json.loads(response.read().decode("utf-8"))
        text = payload["choices"][0]["message"]["content"]
        return _parse_response(image_path=image_path, text=text)


def build_vision_analyzer() -> VisionAnalyzer:
    """Resolve the active vision provider from centralized settings."""
    settings = get_settings().vision
    if settings.mock_enabled and not settings.api_key:
        return MockVisionAnalyzer()
    if settings.provider == "mock":
        return MockVisionAnalyzer()
    if settings.provider == "openai":
        return OpenAIVisionAnalyzer(model=settings.model_name)
    return BigModelVisionAnalyzer(model=settings.model_name)


def _validate_image_path(image_path: Path) -> None:
    """Validate that the given path exists and looks like an image."""
    if not image_path.exists():
        raise ValueError(f"image file not found: {image_path}")

    media_type = mimetypes.guess_type(image_path.name)[0]
    if not media_type or not media_type.startswith("image/"):
        raise ValueError(f"unsupported image type for file: {image_path}")


def _vision_prompt() -> str:
    """Return the shared vision extraction prompt."""
    return (
        "Analyze this product-style image for commerce retrieval. "
        "Return exactly two lines. "
        "Line 1 starts with 'summary:' followed by one short visual summary. "
        "Line 2 starts with 'tags:' followed by 5 to 8 comma-separated visual tags."
    )


def _parse_response(image_path: Path, text: str) -> VisionAnalysis:
    """Parse provider output into the shared analysis schema."""
    summary = ""
    tags: list[str] = []
    for line in text.splitlines():
        normalized = line.strip()
        if normalized.lower().startswith("summary:"):
            summary = normalized.split(":", 1)[1].strip()
        if normalized.lower().startswith("tags:"):
            tags = [tag.strip().lower() for tag in normalized.split(":", 1)[1].split(",") if tag.strip()]
    if not summary:
        summary = text.strip()
    return VisionAnalysis(image_path=image_path, summary=summary, tags=tags)
