from __future__ import annotations

"""Shared domain and trace models.

Inputs:
- catalog records
- vision outputs
- router / retrieval / rerank / generation traces

Outputs:
- dataclass objects used across CLI, web, tests, and dev tooling

Role:
- keep the backend schema explicit and serializable
- provide a single place to inspect pipeline I/O shapes

Upgrade path:
- migrate to Pydantic or API-facing schemas later if stricter validation is needed
- keep trace models stable so replay and eval tooling do not break
"""

from dataclasses import dataclass
from pathlib import Path


@dataclass(slots=True)
class Product:
    """Structured product record used across retrieval and UI responses."""

    id: int
    name: str
    category: str
    rating: float
    tags: list[str]
    description: str
    image_url: str
    image_tags: list[str]
    visual_description: str
    price: float | None = None
    currency: str | None = None
    seller_name: str | None = None
    seller_rating: float | None = None
    review_count: int | None = None
    inventory_count: int | None = None
    product_url: str | None = None
    sku: str | None = None


@dataclass(slots=True)
class VisionAnalysis:
    """Normalized image understanding result shared by search and chat."""

    image_path: Path
    summary: str
    tags: list[str]


@dataclass(slots=True)
class ScoredCandidate:
    """One product candidate with score breakdown for debugging and rerank."""

    product: Product
    score: float
    text_score: float
    image_score: float
    multimodal_score: float
    matched_fields: list[str]


@dataclass(slots=True)
class RouterTrace:
    """Intent routing decision plus the rationale that produced it."""

    prompt: str
    has_image: bool
    intent: str
    rationale: str


@dataclass(slots=True)
class RetrievalTrace:
    """Raw retrieval output before rerank, including tokens and candidates."""

    query_text: str
    text_tokens: list[str]
    image_tokens: list[str]
    candidates: list[ScoredCandidate]
    limit: int


@dataclass(slots=True)
class RerankTrace:
    """Candidate ordering before and after a ranking strategy is applied."""

    strategy: str
    candidates_before: list[ScoredCandidate]
    candidates_after: list[ScoredCandidate]


@dataclass(slots=True)
class GenerationTrace:
    """Final generation step with selected ids and response text."""

    mode: str
    prompt: str
    selected_product_ids: list[int]
    response: str
    prompt_context: str = ""


@dataclass(slots=True)
class ToolCallTrace:
    """One observable tool invocation inside the pipeline trace."""

    tool_name: str
    thought: str
    input_summary: str
    observation_summary: str


@dataclass(slots=True)
class ReActTrace:
    """High-level record of the routed path and tool sequence."""

    initial_intent: str
    final_intent: str
    steps: list[ToolCallTrace]


@dataclass(slots=True)
class PipelineTrace:
    """Complete backend trace for one routed request."""

    router: RouterTrace
    react: ReActTrace
    image_analysis: VisionAnalysis | None
    retrieval: RetrievalTrace | None
    rerank: RerankTrace | None
    generation: GenerationTrace


@dataclass(slots=True)
class PipelineResult:
    """Top-level pipeline output returned to CLI, web, and tests."""

    intent: str
    content: str
    analysis: VisionAnalysis | None
    matches: list[Product]
    trace: PipelineTrace


@dataclass(slots=True)
class ParsedSearchQuery:
    """Structured query object produced by the first-pass search parser."""

    raw_query: str
    normalized_query: str
    remaining_query: str
    category_hints: list[str]
    attribute_hints: list[str]
    min_price: float | None
    max_price: float | None
    sort: str | None


@dataclass(slots=True)
class ProductSearchHit:
    """Joined product card returned by the PostgreSQL text-search repository."""

    product_id: int
    sku: str
    title: str
    short_description: str
    primary_image_url: str
    price: float
    currency: str
    seller_name: str
    seller_rating: float
    review_count: int
    inventory_count: int
    product_url: str
    category_name: str
    text_score: float
    image_score: float
    multimodal_score: float
    match_score: float
