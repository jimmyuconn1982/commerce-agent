from __future__ import annotations

"""Heuristic intent router for chat vs retrieval flows.

Inputs:
- prompt text
- a boolean telling whether an image is attached

Outputs:
- `RouterTrace` with intent and rationale

Role:
- keep intent classification independent from the main agent orchestrator
- make router behavior replayable with a dedicated case dataset

Upgrade path:
- replace heuristics with a classifier or LLM router
- keep `RouterCase -> RouterTrace` stable for evalbench and debugging
"""

from dataclasses import dataclass
import re

from .catalog import Catalog
from .models import RouterTrace

CHAT_PATTERNS = (
    r"\bwhat can you do\b",
    r"\bwho are you\b",
    r"\bwhat model\b",
    r"\bhow do you work\b",
    r"\bexplain\b",
    r"\btell me\b",
    r"\bhelp me understand\b",
    r"\bcan you help\b",
    r"\b你好\b",
    r"\b你是谁\b",
    r"\b你能做什么\b",
    r"\b什么模型\b",
    r"\b怎么工作\b",
)

SEARCH_PATTERNS = (
    r"\bfind\b",
    r"\bsearch\b",
    r"\bshow me\b",
    r"\blooking for\b",
    r"\brecommend me\b",
    r"\bi need\b",
    r"\bi want\b",
    r"\bbuy\b",
    r"\bshop\b",
    r"\b找\b",
    r"\b搜索\b",
    r"\b推荐\b",
    r"\b想要\b",
    r"\b需要\b",
    r"\b买\b",
)

ATTRIBUTE_TERMS = {
    "red",
    "blue",
    "green",
    "black",
    "white",
    "small",
    "large",
    "compact",
    "lightweight",
    "formal",
    "casual",
    "office",
    "outdoor",
    "travel",
    "matte",
    "metal",
    "wood",
    "leather",
    "sport",
    "红",
    "蓝",
    "绿",
    "黑",
    "白",
    "小",
    "大",
    "轻便",
    "正式",
    "休闲",
    "通勤",
    "户外",
    "旅行",
    "金属",
    "木质",
    "皮质",
}

PRODUCT_HINT_TERMS = {
    "hat",
    "bag",
    "bottle",
    "keyboard",
    "desk",
    "hoodie",
    "earbuds",
    "shoes",
    "shirt",
    "cap",
    "backpack",
    "帽子",
    "包",
    "水瓶",
    "键盘",
    "桌子",
    "卫衣",
    "耳机",
    "鞋",
    "衣服",
}


@dataclass(slots=True)
class RouterCase:
    """Minimal router input used by tests, replay, and orchestration."""

    prompt: str = ""
    has_image: bool = False


class HeuristicRouter:
    """Rule-based router that separates chat from retrieval intents."""

    def __init__(self, catalog: Catalog) -> None:
        self.catalog_lexicon = self._build_catalog_lexicon(catalog)

    def route(self, case: RouterCase) -> RouterTrace:
        """Route one request into chat, text, image, or multimodal search."""
        text = case.prompt.strip().lower()
        if case.has_image and text:
            return RouterTrace(
                prompt=case.prompt,
                has_image=case.has_image,
                intent="multimodal-search",
                rationale="image and text are both present",
            )
        if case.has_image:
            return RouterTrace(
                prompt=case.prompt,
                has_image=case.has_image,
                intent="image-search",
                rationale="image is present without text",
            )
        if not text:
            return RouterTrace(
                prompt=case.prompt,
                has_image=case.has_image,
                intent="chat",
                rationale="empty text defaults to chat",
            )
        return self._route_text_only_intent(case.prompt)

    def _route_text_only_intent(self, prompt: str) -> RouterTrace:
        """Score a text-only prompt using chat and search heuristics."""
        normalized = self._normalize_text(prompt)
        tokens = self._tokenize(normalized)

        # The router uses a small scorecard instead of a single keyword hit so
        # it can combine product hints, attribute hints, and chat-like signals.
        chat_score = 0
        search_score = 0
        reasons: list[str] = []

        if "?" in prompt or "？" in prompt:
            chat_score += 2
            reasons.append("question punctuation")

        matched_chat_patterns = [pattern for pattern in CHAT_PATTERNS if re.search(pattern, normalized)]
        if matched_chat_patterns:
            chat_score += 4
            reasons.append("conversational pattern")

        matched_search_patterns = [pattern for pattern in SEARCH_PATTERNS if re.search(pattern, normalized)]
        if matched_search_patterns:
            search_score += 3
            reasons.append("shopping/search verb")

        catalog_hits = sorted(tokens & self.catalog_lexicon)
        if catalog_hits:
            search_score += min(4, len(catalog_hits))
            reasons.append(f"catalog terms={', '.join(catalog_hits[:4])}")

        attribute_hits = sorted(tokens & ATTRIBUTE_TERMS)
        if attribute_hits:
            search_score += min(3, len(attribute_hits))
            reasons.append(f"attribute terms={', '.join(attribute_hits[:4])}")

        product_hint_hits = sorted(tokens & PRODUCT_HINT_TERMS)
        if product_hint_hits:
            search_score += min(3, len(product_hint_hits))
            reasons.append(f"product hints={', '.join(product_hint_hits[:4])}")

        attribute_substring_hits = self._substring_hits(normalized, ATTRIBUTE_TERMS)
        if attribute_substring_hits:
            search_score += min(2, len(attribute_substring_hits))
            reasons.append(f"attribute substrings={', '.join(attribute_substring_hits[:4])}")

        product_substring_hits = self._substring_hits(normalized, PRODUCT_HINT_TERMS)
        if product_substring_hits:
            search_score += min(3, len(product_substring_hits))
            reasons.append(f"product substrings={', '.join(product_substring_hits[:4])}")

        if len(tokens) <= 4 and (catalog_hits or attribute_hits or product_hint_hits):
            search_score += 2
            reasons.append("short keyword query")

        if not catalog_hits and not attribute_hits and not product_hint_hits and len(tokens) > 8:
            chat_score += 2
            reasons.append("long non-product prompt")

        if self._looks_like_capability_question(normalized):
            chat_score += 4
            reasons.append("capability/model question")

        if search_score > chat_score:
            rationale = "; ".join(reasons) or "search-oriented lexical evidence"
            return RouterTrace(prompt=prompt, has_image=False, intent="text-search", rationale=rationale)

        rationale = "; ".join(reasons) or "conversation-oriented prompt"
        return RouterTrace(prompt=prompt, has_image=False, intent="chat", rationale=rationale)

    def _build_catalog_lexicon(self, catalog: Catalog) -> set[str]:
        """Extract reusable lexical hints from the current catalog."""
        lexicon: set[str] = set()
        for product in catalog.all():
            fields = [
                product.name,
                product.category,
                product.description,
                " ".join(product.tags),
                " ".join(product.image_tags),
                product.visual_description,
            ]
            for field in fields:
                normalized = self._normalize_text(field)
                for token in normalized.split():
                    if len(token) >= 3 or re.search(r"[\u4e00-\u9fff]", token):
                        lexicon.add(token)
        return lexicon

    def _normalize_text(self, prompt: str) -> str:
        """Lowercase and simplify text for rule matching."""
        lowered = prompt.strip().lower()
        lowered = re.sub(r"[^\w\s\u4e00-\u9fff-]", " ", lowered)
        return re.sub(r"\s+", " ", lowered).strip()

    def _tokenize(self, text: str) -> set[str]:
        """Split normalized text into lightweight tokens."""
        return {token.lower() for token in text.split() if token.strip()}

    def _looks_like_capability_question(self, normalized: str) -> bool:
        """Detect prompts that ask about the assistant itself."""
        capability_clues = (
            "what can you do",
            "who are you",
            "what model",
            "how do you work",
            "你的能力",
            "你能做什么",
            "你是谁",
            "什么模型",
        )
        return any(clue in normalized for clue in capability_clues)

    def _substring_hits(self, normalized: str, terms: set[str]) -> list[str]:
        """Match non-space-separated terms such as short Chinese phrases."""
        hits = []
        for term in sorted(terms):
            if re.search(r"[\u4e00-\u9fff]", term) and term in normalized:
                hits.append(term)
        return hits
