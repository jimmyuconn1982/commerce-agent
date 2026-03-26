from __future__ import annotations

"""Tool layer for the commerce agent.

Inputs:
- typed dataclass inputs for router, search, rerank, generation, and path tools

Outputs:
- typed traces, generation results, or path-level aggregates

Role:
- expose stable tool contracts to the orchestrator
- keep business logic callable as small, composable units

Upgrade path:
- move these tools behind a planner / ReAct loop
- map them into LangGraph nodes or remote tool executors later
"""

from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

from .models import (
    GenerationTrace,
    Product,
    RetrievalTrace,
    RerankTrace,
    RouterTrace,
    ToolCallTrace,
    VisionAnalysis,
)

if TYPE_CHECKING:
    from .agent import CommerceAgent


@dataclass(slots=True)
class RouteIntentInput:
    prompt: str = ""
    has_image: bool = False


@dataclass(slots=True)
class AnalyzeImageInput:
    image_path: Path


@dataclass(slots=True)
class TextSearchInput:
    query: str
    category: str | None = None
    limit: int = 5


@dataclass(slots=True)
class ImageSearchInput:
    image_analysis: VisionAnalysis
    category: str | None = None
    limit: int = 5


@dataclass(slots=True)
class MultimodalSearchInput:
    text_query: str
    image_analysis: VisionAnalysis | None = None
    category: str | None = None
    limit: int = 5


@dataclass(slots=True)
class RerankInput:
    candidates: list
    strategy: str


@dataclass(slots=True)
class ChatGenerationInput:
    prompt: str
    analysis: VisionAnalysis | None
    products: list[Product]


@dataclass(slots=True)
class SearchSummaryInput:
    intent: str
    matches: list[Product]


@dataclass(slots=True)
class ChatPathInput:
    prompt: str
    image_analysis: VisionAnalysis | None
    steps: list[ToolCallTrace]


@dataclass(slots=True)
class SearchPathResult:
    retrieval: RetrievalTrace
    rerank: RerankTrace
    matches: list[Product]
    generation: GenerationTrace


@dataclass(slots=True)
class TextSearchPathInput:
    prompt: str
    category: str | None
    limit: int
    steps: list[ToolCallTrace]


@dataclass(slots=True)
class ImageSearchPathInput:
    image_analysis: VisionAnalysis | None
    category: str | None
    limit: int
    steps: list[ToolCallTrace]


@dataclass(slots=True)
class MultimodalSearchPathInput:
    prompt: str
    image_analysis: VisionAnalysis | None
    category: str | None
    limit: int
    steps: list[ToolCallTrace]


class CommerceTools:
    """Typed tool adapter around the agent's router, retrieval, and generation."""

    def __init__(self, agent: "CommerceAgent") -> None:
        self.agent = agent

    def registry(self) -> dict[str, object]:
        """Return the tool registry used by the orchestrator and dev tooling."""
        return {
            "route_intent": self.route_intent,
            "analyze_image": self.analyze_image,
            "text_search": self.text_search,
            "image_search": self.image_search,
            "multimodal_search": self.multimodal_search,
            "rerank": self.rerank,
            "generate_chat": self.generate_chat,
            "generate_search_summary": self.generate_search_summary,
            "chat_path": self.run_chat_path,
            "text_search_path": self.run_text_search_path,
            "image_search_path": self.run_image_search_path,
            "multimodal_search_path": self.run_multimodal_search_path,
        }

    def route_intent(self, data: RouteIntentInput) -> RouterTrace:
        """Run the router tool and return a structured route decision."""
        return self.agent.route_intent(prompt=data.prompt, has_image=data.has_image)

    def analyze_image(self, data: AnalyzeImageInput) -> VisionAnalysis:
        """Run the vision tool for one local image."""
        return self.agent._get_vision_analyzer().analyze(Path(data.image_path))

    def text_search(self, data: TextSearchInput) -> RetrievalTrace:
        """Retrieve candidates from text signals only."""
        return self.agent.retrieve_text_candidates(
            text_query=data.query,
            category=data.category,
            limit=data.limit,
        )

    def image_search(self, data: ImageSearchInput) -> RetrievalTrace:
        """Retrieve candidates from image-derived signals only."""
        return self.agent.retrieve_image_candidates(
            image_analysis=data.image_analysis,
            category=data.category,
            limit=data.limit,
        )

    def multimodal_search(self, data: MultimodalSearchInput) -> RetrievalTrace:
        """Retrieve candidates from blended text and image signals."""
        return self.agent.retrieve_multimodal_candidates(
            text_query=data.text_query,
            image_analysis=data.image_analysis,
            category=data.category,
            limit=data.limit,
        )

    def rerank(self, data: RerankInput) -> RerankTrace:
        """Reorder candidates according to a named scoring strategy."""
        return self.agent.rerank_candidates(data.candidates, data.strategy)

    def generate_chat(self, data: ChatGenerationInput) -> str:
        """Generate a chat reply for non-retrieval conversations."""
        return self.agent._generate_chat_response(
            prompt=data.prompt,
            analysis=data.analysis,
            products=data.products,
        )

    def generate_search_summary(self, data: SearchSummaryInput) -> str:
        """Return a short UI-friendly summary for retrieval paths."""
        if not data.matches:
            empty_messages = {
                "text-search": "No matching products were found in the database for this text query.",
                "image-search": "No matching products were found in the database for this image.",
                "multimodal-search": "No matching products were found in the database for this text + image request.",
            }
            return empty_messages.get(data.intent, "No matching products were found in the database.")
        label = {
            "text-search": "text",
            "image-search": "visual",
            "multimodal-search": "multimodal",
        }.get(data.intent, "search")
        return f"Found {len(data.matches)} {label} matches."

    def run_chat_path(self, data: ChatPathInput) -> GenerationTrace:
        """Execute the dedicated chat path without touching the catalog."""
        content = self.generate_chat(
            ChatGenerationInput(
                prompt=data.prompt,
                analysis=data.image_analysis,
                products=[],
            )
        )
        data.steps.append(
            ToolCallTrace(
                tool_name="generate_chat",
                thought="Handle conversational requests without touching the product catalog.",
                input_summary=f"prompt={data.prompt!r}; has_image={data.image_analysis is not None}",
                observation_summary=content,
            )
        )
        return GenerationTrace(mode="chat", prompt=data.prompt, selected_product_ids=[], response=content)

    def run_text_search_path(self, data: TextSearchPathInput) -> SearchPathResult:
        """Execute the text-search path end to end."""
        # Path tools keep multi-step flows reusable without forcing callers to
        # know the retrieval + rerank + summarize sequence.
        retrieval = self.text_search(
            TextSearchInput(query=data.prompt, category=data.category, limit=data.limit)
        )
        data.steps.append(
            ToolCallTrace(
                tool_name="text_search",
                thought="Use the configured text-search repository for retrieval.",
                input_summary=f"query={data.prompt!r}",
                observation_summary=f"candidates={len(retrieval.candidates)}",
            )
        )
        return self._complete_search_path(
            intent="text-search",
            prompt=data.prompt,
            retrieval=retrieval,
            rerank=RerankTrace(
                strategy="repository-order",
                candidates_before=list(retrieval.candidates),
                candidates_after=list(retrieval.candidates),
            ),
            steps=data.steps,
            limit=data.limit,
        )

    def run_image_search_path(self, data: ImageSearchPathInput) -> SearchPathResult:
        """Execute the image-search path end to end."""
        retrieval = self.image_search(
            ImageSearchInput(image_analysis=data.image_analysis, category=data.category, limit=data.limit)
        )
        data.steps.append(
            ToolCallTrace(
                tool_name="image_search",
                thought="Use the configured image-search repository for retrieval.",
                input_summary=f"summary={data.image_analysis.summary if data.image_analysis else ''}",
                observation_summary=f"candidates={len(retrieval.candidates)}",
            )
        )
        return self._complete_search_path(
            intent="image-search",
            prompt="",
            retrieval=retrieval,
            rerank=RerankTrace(
                strategy="repository-order",
                candidates_before=list(retrieval.candidates),
                candidates_after=list(retrieval.candidates),
            ),
            steps=data.steps,
            limit=data.limit,
        )

    def run_multimodal_search_path(self, data: MultimodalSearchPathInput) -> SearchPathResult:
        """Execute the multimodal-search path end to end."""
        retrieval = self.multimodal_search(
            MultimodalSearchInput(
                text_query=data.prompt,
                image_analysis=data.image_analysis,
                category=data.category,
                limit=data.limit,
            )
        )
        data.steps.append(
            ToolCallTrace(
                tool_name="multimodal_search",
                thought="Use the configured multimodal repository for retrieval.",
                input_summary=f"text={data.prompt!r}; has_image={data.image_analysis is not None}",
                observation_summary=f"candidates={len(retrieval.candidates)}",
            )
        )
        return self._complete_search_path(
            intent="multimodal-search",
            prompt=data.prompt,
            retrieval=retrieval,
            rerank=RerankTrace(
                strategy="repository-order",
                candidates_before=list(retrieval.candidates),
                candidates_after=list(retrieval.candidates),
            ),
            steps=data.steps,
            limit=data.limit,
        )

    def _complete_search_path(
        self,
        *,
        intent: str,
        prompt: str,
        retrieval: RetrievalTrace,
        rerank: RerankTrace,
        steps: list[ToolCallTrace],
        limit: int,
    ) -> SearchPathResult:
        """Finalize one retrieval path with rerank, summary, and match ids."""
        steps.append(
            ToolCallTrace(
                tool_name="rerank",
                thought="Promote the strongest candidates for the chosen intent.",
                input_summary=f"strategy={rerank.strategy}; before={len(rerank.candidates_before)}",
                observation_summary=f"after={len(rerank.candidates_after)}",
            )
        )
        matches = [candidate.product for candidate in rerank.candidates_after[:limit]]
        content = self.generate_search_summary(SearchSummaryInput(intent=intent, matches=matches))
        steps.append(
            ToolCallTrace(
                tool_name="generate_search_summary",
                thought="Return a concise retrieval summary for the UI.",
                input_summary=f"matches={len(matches)}",
                observation_summary=content,
            )
        )
        generation = GenerationTrace(
            mode=intent,
            prompt=prompt,
            selected_product_ids=[product.id for product in matches],
            response=content,
        )
        return SearchPathResult(
            retrieval=retrieval,
            rerank=rerank,
            matches=matches,
            generation=generation,
        )
