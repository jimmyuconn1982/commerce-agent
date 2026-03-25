from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(slots=True)
class Product:
    id: str
    name: str
    category: str
    rating: float
    tags: list[str]
    description: str
    image_url: str
    image_tags: list[str]
    visual_description: str


@dataclass(slots=True)
class VisionAnalysis:
    image_path: Path
    summary: str
    tags: list[str]


@dataclass(slots=True)
class ScoredCandidate:
    product: Product
    score: float
    text_score: float
    image_score: float
    matched_fields: list[str]


@dataclass(slots=True)
class RouterTrace:
    prompt: str
    has_image: bool
    intent: str
    rationale: str


@dataclass(slots=True)
class RetrievalTrace:
    query_text: str
    text_tokens: list[str]
    image_tokens: list[str]
    candidates: list[ScoredCandidate]
    limit: int


@dataclass(slots=True)
class RerankTrace:
    strategy: str
    candidates_before: list[ScoredCandidate]
    candidates_after: list[ScoredCandidate]


@dataclass(slots=True)
class GenerationTrace:
    mode: str
    prompt: str
    selected_product_ids: list[str]
    response: str


@dataclass(slots=True)
class ToolCallTrace:
    tool_name: str
    thought: str
    input_summary: str
    observation_summary: str


@dataclass(slots=True)
class ReActTrace:
    initial_intent: str
    final_intent: str
    steps: list[ToolCallTrace]


@dataclass(slots=True)
class PipelineTrace:
    router: RouterTrace
    react: ReActTrace
    image_analysis: VisionAnalysis | None
    retrieval: RetrievalTrace | None
    rerank: RerankTrace | None
    generation: GenerationTrace


@dataclass(slots=True)
class PipelineResult:
    intent: str
    content: str
    analysis: VisionAnalysis | None
    matches: list[Product]
    trace: PipelineTrace
