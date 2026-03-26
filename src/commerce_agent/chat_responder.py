from __future__ import annotations

"""Chat responder layer for scoped non-search conversation.

Inputs:
- user prompt
- optional image analysis

Outputs:
- one chat response constrained to the commerce-agent scope

Role:
- keep chat generation separate from the main orchestrator
- avoid hardcoding many prompt-specific branches in `agent.py`

Upgrade path:
- swap providers without changing the agent entrypoints
- add richer structured chat policies later if needed
"""

import json
from typing import Protocol
from urllib.request import Request, urlopen

from .config import get_settings
from .models import VisionAnalysis


class ChatResponder(Protocol):
    """Protocol for scoped chat generation backends."""

    def generate(self, prompt: str, analysis: VisionAnalysis | None = None) -> str:
        """Return one scoped chat reply."""
        ...


class FallbackChatResponder:
    """Small local fallback when model-backed chat is unavailable."""

    def generate(self, prompt: str, analysis: VisionAnalysis | None = None) -> str:
        """Return a stable scoped fallback reply in English."""
        lines = [
            "I am a commerce agent with a limited chat scope.",
            "I can explain my capabilities, how to use text, image, or multimodal product search, and how to search products stored in the database.",
            "If you want products, tell me the product constraints or upload an image so I can search the database.",
        ]
        if analysis:
            lines.append(f"Image summary: {analysis.summary}")
            if analysis.tags:
                lines.append(f"Image tags: {', '.join(analysis.tags)}")
        return "\n".join(lines)


class BigModelChatResponder:
    """BigModel-backed chat responder constrained by a fixed system prompt."""

    def __init__(
        self,
        *,
        api_key: str | None = None,
        base_url: str | None = None,
        model_name: str | None = None,
    ) -> None:
        settings = get_settings().chat
        self.api_key = api_key or settings.api_key
        self.base_url = (base_url or settings.base_url).rstrip("/")
        self.model_name = model_name or settings.model_name

    def generate(self, prompt: str, analysis: VisionAnalysis | None = None) -> str:
        """Generate one scoped English chat reply through BigModel."""
        if not self.api_key:
            return FallbackChatResponder().generate(prompt, analysis)

        user_payload: dict[str, object] = {"prompt": prompt}
        if analysis:
            user_payload["image_summary"] = analysis.summary
            user_payload["image_tags"] = analysis.tags

        body = json.dumps(
            {
                "model": self.model_name,
                "temperature": 0.2,
                "messages": [
                    {
                        "role": "system",
                        "content": (
                            "You are a commerce agent. "
                            "Always reply in English. "
                            "You support only 4 capabilities: chat, text product search, image product search, and multimodal product search. "
                            "You can search only products that exist in the database. "
                            "If the user is not explicitly asking to search products, stay in scoped chat. "
                            "Scoped chat is limited to: greetings, capability explanations, how to use the search modes, "
                            "clarifying product search requests, and explaining how image-based search works. "
                            "Do not answer unrelated open-domain questions. "
                            "Do not claim you can search outside the database. "
                            "Keep the answer concise and practical."
                        ),
                    },
                    {
                        "role": "user",
                        "content": json.dumps(user_payload, ensure_ascii=False),
                    },
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
        try:
            with urlopen(request, timeout=20) as response:
                payload = json.loads(response.read().decode("utf-8"))
            content = payload["choices"][0]["message"]["content"].strip()
            return content or FallbackChatResponder().generate(prompt, analysis)
        except Exception:
            return FallbackChatResponder().generate(prompt, analysis)


def build_chat_responder() -> ChatResponder:
    """Resolve the active chat responder from centralized settings."""
    settings = get_settings().chat
    if settings.provider == "bigmodel":
        return BigModelChatResponder()
    return FallbackChatResponder()
