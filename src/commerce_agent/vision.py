from __future__ import annotations

import base64
import mimetypes
import os
from pathlib import Path
from typing import Protocol

from .models import VisionAnalysis


class VisionAnalyzer(Protocol):
    def analyze(self, image_path: Path) -> VisionAnalysis:
        ...


class OpenAIVisionAnalyzer:
    def __init__(self, model: str | None = None) -> None:
        self._client = None
        self.model = model or os.getenv("COMMERCE_AGENT_VISION_MODEL", "gpt-4.1-mini")

    def analyze(self, image_path: Path) -> VisionAnalysis:
        if not image_path.exists():
            raise ValueError(f"image file not found: {image_path}")

        media_type = mimetypes.guess_type(image_path.name)[0]
        if not media_type or not media_type.startswith("image/"):
            raise ValueError(f"unsupported image type for file: {image_path}")

        if not os.getenv("OPENAI_API_KEY"):
            if os.getenv("COMMERCE_AGENT_MOCK_VISION") == "1":
                return self._mock_analysis(image_path)
            raise ValueError("OPENAI_API_KEY is required for image understanding")

        if self._client is None:
            from openai import OpenAI

            self._client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

        base64_image = base64.b64encode(image_path.read_bytes()).decode("utf-8")
        response = self._client.responses.create(
            model=self.model,
            input=[
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "input_text",
                            "text": (
                                "Analyze this product-style image for commerce retrieval. "
                                "Return exactly two lines. "
                                "Line 1 starts with 'summary:' followed by one short visual summary. "
                                "Line 2 starts with 'tags:' followed by 5 to 8 comma-separated visual tags."
                            ),
                        },
                        {
                            "type": "input_image",
                            "image_url": f"data:{media_type};base64,{base64_image}",
                        },
                    ],
                }
            ],
        )
        return self._parse_response(image_path=image_path, text=response.output_text)

    def _mock_analysis(self, image_path: Path) -> VisionAnalysis:
        raw = os.getenv("COMMERCE_AGENT_MOCK_VISION_RESPONSE", "").strip()
        if raw:
            return self._parse_response(image_path=image_path, text=raw)

        stem = image_path.stem.replace("-", " ").replace("_", " ").strip() or "product image"
        summary = f"summary: mock analysis for {stem}"
        tags = "tags: product, mock, image, accessory, catalog"
        return self._parse_response(image_path=image_path, text=f"{summary}\n{tags}")

    def _parse_response(self, image_path: Path, text: str) -> VisionAnalysis:
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
