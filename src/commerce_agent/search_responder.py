from __future__ import annotations

"""Search responder layer for grounded final answers.

Inputs:
- routed search intent
- original user prompt
- optional image analysis
- reranked top-k products

Outputs:
- one grounded natural-language answer for the UI

Role:
- keep final search answer generation separate from retrieval
- ensure the model only speaks from retrieved products

Upgrade path:
- add structured citation-style outputs later
- split by locale or storefront policy if needed
"""

import json
from dataclasses import dataclass
from typing import Protocol
from urllib.request import Request, urlopen

from .config import get_settings
from .models import Product, VisionAnalysis


@dataclass(slots=True)
class SearchResponse:
    """Structured grounded search answer plus the LLM-selected product ids."""

    response: str
    selected_product_ids: list[int]
    prompt_context: str


class SearchResponder(Protocol):
    """Protocol for grounded search-answer generation backends."""

    def generate(
        self,
        *,
        intent: str,
        prompt: str,
        analysis: VisionAnalysis | None,
        products: list[Product],
    ) -> SearchResponse:
        """Return one grounded final answer plus the selected product ids."""
        ...


class FallbackSearchResponder:
    """Small local fallback that formats the top-k products without a model."""

    def generate(
        self,
        *,
        intent: str,
        prompt: str,
        analysis: VisionAnalysis | None,
        products: list[Product],
    ) -> SearchResponse:
        if not products:
            return SearchResponse(
                response="No matching products were found in the database.",
                selected_product_ids=[],
                prompt_context="",
            )

        lines = [f"I found {len(products)} matching products in the database:"]
        for product in products[:5]:
            price = f"{product.currency or 'USD'} {product.price:.2f}" if product.price is not None else "price unavailable"
            lines.append(f"- {product.name}: {product.description} ({price})")
        selected = [product.id for product in products[:5]]
        return SearchResponse(
            response="\n".join(lines),
            selected_product_ids=selected,
            prompt_context=json.dumps(
                {
                    "intent": intent,
                    "prompt": prompt,
                    "selected_product_ids": selected,
                },
                ensure_ascii=False,
                indent=2,
            ),
        )


class BigModelSearchResponder:
    """BigModel-backed responder that generates grounded search answers."""

    def __init__(self) -> None:
        settings = get_settings().chat
        self.api_key = settings.api_key
        self.base_url = settings.base_url
        self.model_name = settings.model_name

    def generate(
        self,
        *,
        intent: str,
        prompt: str,
        analysis: VisionAnalysis | None,
        products: list[Product],
    ) -> SearchResponse:
        if not self.api_key:
            return FallbackSearchResponder().generate(
                intent=intent,
                prompt=prompt,
                analysis=analysis,
                products=products,
            )

        product_payload = [
            {
                "id": product.id,
                "name": product.name,
                "category": product.category,
                "description": product.description,
                "price": product.price,
                "currency": product.currency,
                "seller_name": product.seller_name,
                "review_count": product.review_count,
                "inventory_count": product.inventory_count,
            }
            for product in products
        ]
        user_payload: dict[str, object] = {
            "intent": intent,
            "prompt": prompt,
            "products": product_payload,
        }
        if analysis:
            user_payload["image_summary"] = analysis.summary
            user_payload["image_tags"] = analysis.tags
        prompt_context = json.dumps(user_payload, ensure_ascii=False, indent=2)

        body = json.dumps(
            {
                "model": self.model_name,
                "temperature": 0.2,
                "messages": [
                    {
                        "role": "system",
                        "content": (
                            "You are a commerce search answer generator. "
                            "Always reply in English. "
                            "Only use the provided products. "
                            "Do not invent products or facts outside the product list. "
                            "Give a concise recommendation or search summary grounded in the products. "
                            "If the user asked for recommendations, highlight the strongest matches first. "
                            "If the result set mixes weak matches, focus on the more relevant items and avoid overclaiming. "
                            "If none of the provided products are directly relevant to the user's request, "
                            "say that no matching products were found in the database and return an empty selected_product_ids list. "
                            "Do not choose approximate substitutes that change the product type or use case. "
                            "For example, a keyboard request should not select kitchen tools, decor, fragrances, or unrelated groceries. "
                            "Return strict JSON with keys: response, selected_product_ids. "
                            "selected_product_ids must be a subset of the provided product ids. "
                            "Filter out weak or irrelevant matches instead of listing everything."
                        ),
                    },
                    {"role": "user", "content": prompt_context},
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
            parsed = _parse_search_response(content, products)
            if parsed is not None:
                parsed.prompt_context = prompt_context
                return parsed
            return FallbackSearchResponder().generate(intent=intent, prompt=prompt, analysis=analysis, products=products)
        except Exception:
            return FallbackSearchResponder().generate(intent=intent, prompt=prompt, analysis=analysis, products=products)


def _parse_search_response(content: str, products: list[Product]) -> SearchResponse | None:
    """Parse the model JSON response and keep only valid selected product ids."""
    normalized = content.strip()
    if normalized.startswith("```"):
        normalized = normalized.strip("`")
        normalized = normalized.removeprefix("json").strip()
    try:
        parsed = json.loads(normalized)
    except json.JSONDecodeError:
        return None
    if not isinstance(parsed, dict):
        return None
    response = str(parsed.get("response", "")).strip()
    selected = parsed.get("selected_product_ids", [])
    if not response or not isinstance(selected, list):
        return None
    valid_ids = {product.id for product in products}
    selected_ids: list[int] = []
    for product_id in selected:
        try:
            parsed_id = int(product_id)
        except (TypeError, ValueError):
            continue
        if parsed_id in valid_ids:
            selected_ids.append(parsed_id)
    return SearchResponse(response=response, selected_product_ids=selected_ids, prompt_context="")


def build_search_responder() -> SearchResponder:
    """Resolve the active search responder from centralized settings."""
    settings = get_settings().chat
    if settings.provider == "bigmodel":
        return BigModelSearchResponder()
    return FallbackSearchResponder()
