from __future__ import annotations

"""Core commerce agent orchestration.

Inputs:
- user prompt text
- optional local image path
- optional category and top-k limit

Outputs:
- direct chat text, or
- search matches plus a structured pipeline trace

Role:
- keep the public API stable for CLI and web entrypoints
- orchestrate router, vision, retrieval, rerank, and generation tools

Upgrade path:
- keep `run_pipeline()` as the stable entrypoint
- swap the current orchestrator for a deeper planner / LangGraph graph later
- move retrieval and generation to external services without changing callers
"""

from pathlib import Path
from typing import Callable

from .catalog import Catalog
from .chat_responder import ChatResponder, build_chat_responder
from .search_responder import SearchResponder, SearchResponse, build_search_responder
from .models import (
    GenerationTrace,
    PipelineResult,
    PipelineTrace,
    Product,
    ReActTrace,
    RetrievalTrace,
    RerankTrace,
    RouterTrace,
    ScoredCandidate,
    ToolCallTrace,
    VisionAnalysis,
)
from .repository import CatalogSearchRepository, SearchRepository
from .tools import (
    AnalyzeImageInput,
    ChatGenerationInput,
    ChatPathInput,
    CommerceTools,
    ImageSearchInput,
    ImageSearchPathInput,
    MultimodalSearchInput,
    MultimodalSearchPathInput,
    RerankInput,
    RouteIntentInput,
    TextSearchInput,
    TextSearchPathInput,
)
from .router import RouterCase, build_router
from .vision import VisionAnalyzer, build_vision_analyzer


class CommerceAgent:
    """High-level backend facade for chat and commerce retrieval."""

    def __init__(
        self,
        catalog: Catalog | None = None,
        vision_analyzer: VisionAnalyzer | None = None,
        search_repository: SearchRepository | None = None,
        chat_responder: ChatResponder | None = None,
        search_responder: SearchResponder | None = None,
    ) -> None:
        self.catalog = catalog or Catalog.from_json()
        self.vision_analyzer = vision_analyzer
        self.search_repository = search_repository or CatalogSearchRepository(self.catalog)
        self.chat_responder = chat_responder
        self.search_responder = search_responder
        self.router = build_router(self.catalog)
        self.tools = CommerceTools(self)

    def text_search(
        self,
        query: str = "",
        *,
        category: str | None = None,
        limit: int = 5,
    ) -> list[Product]:
        """Run text retrieval and return the top ranked products."""
        retrieval = self.tools.text_search(TextSearchInput(query=query, category=category, limit=limit))
        return [candidate.product for candidate in retrieval.candidates[:limit]]

    def image_search(self, image_path: str | Path, limit: int = 5) -> tuple[VisionAnalysis, list[Product]]:
        """Analyze one image and return visually matched products."""
        analysis = self.tools.analyze_image(AnalyzeImageInput(image_path=Path(image_path)))
        retrieval = self.tools.image_search(ImageSearchInput(image_analysis=analysis, limit=limit))
        return analysis, [candidate.product for candidate in retrieval.candidates[:limit]]

    def multimodal_search(
        self,
        *,
        text_query: str = "",
        image_path: str | Path | None = None,
        category: str | None = None,
        limit: int = 5,
    ) -> tuple[VisionAnalysis | None, list[Product]]:
        """Blend text and image signals and return ranked matches."""
        analysis = self.tools.analyze_image(AnalyzeImageInput(image_path=Path(image_path))) if image_path else None
        retrieval = self.tools.multimodal_search(
            MultimodalSearchInput(
                text_query=text_query,
                image_analysis=analysis,
                category=category,
                limit=limit,
            )
        )
        return analysis, [candidate.product for candidate in retrieval.candidates[:limit]]

    def chat(self, prompt: str, image_path: str | Path | None = None) -> str:
        """Return a conversational reply without querying the product catalog."""
        analysis = self.tools.analyze_image(AnalyzeImageInput(image_path=Path(image_path))) if image_path else None
        return self.tools.generate_chat(
            ChatGenerationInput(prompt=prompt, analysis=analysis, products=[])
        )

    def classify_intent(self, prompt: str = "", has_image: bool = False) -> str:
        """Return only the routed intent label."""
        return self.tools.route_intent(RouteIntentInput(prompt=prompt, has_image=has_image)).intent

    def route_intent(self, prompt: str = "", has_image: bool = False) -> RouterTrace:
        """Route one request and keep the rationale for debugging."""
        return self.router.route(RouterCase(prompt=prompt, has_image=has_image))

    def get_tools(self) -> dict[str, Callable[..., object]]:
        """Expose the registered tool callables for orchestration and tests."""
        return self.tools.registry()

    def retrieve_candidates(
        self,
        *,
        text_query: str = "",
        image_analysis: VisionAnalysis | None = None,
        category: str | None = None,
        limit: int = 5,
    ) -> RetrievalTrace:
        """Score catalog items against text and optional image signals."""
        text_tokens = self._tokenize(text_query)
        image_tokens = self._tokenize(f"{image_analysis.summary} {' '.join(image_analysis.tags)}") if image_analysis else set()
        candidates: list[ScoredCandidate] = []
        for product in self.catalog.all():
            if category and product.category != category:
                continue
            text_score, text_fields = self._score_text(product, text_tokens)
            image_score, image_fields = self._score_image(product, image_tokens)
            score = round((text_score * 0.6) + (image_score * 0.4), 2) if image_tokens else text_score
            if text_tokens or image_tokens:
                if score == 0:
                    continue
            else:
                score = product.rating
            candidates.append(
                ScoredCandidate(
                    product=product,
                    score=round(score, 2),
                    text_score=round(text_score, 2),
                    image_score=round(image_score, 2),
                    matched_fields=sorted(set(text_fields + image_fields)),
                )
            )
        ranked = sorted(candidates, key=lambda item: (item.score, item.product.rating), reverse=True)
        return RetrievalTrace(
            query_text=text_query,
            text_tokens=sorted(text_tokens),
            image_tokens=sorted(image_tokens),
            candidates=ranked[: max(limit, len(ranked))],
            limit=limit,
        )

    def retrieve_text_candidates(
        self,
        *,
        text_query: str = "",
        category: str | None = None,
        limit: int = 5,
    ) -> RetrievalTrace:
        """Retrieve text-search candidates from the configured search repository."""
        parsed, hits = self.search_repository.search_text(text_query, limit=limit)
        candidates = [self._candidate_from_search_hit(hit) for hit in hits]
        if category:
            candidates = [candidate for candidate in candidates if candidate.product.category == category]
        return RetrievalTrace(
            query_text=parsed.remaining_query or parsed.normalized_query or text_query,
            text_tokens=sorted((parsed.remaining_query or parsed.normalized_query).split()),
            image_tokens=[],
            candidates=candidates,
            limit=limit,
        )

    def retrieve_image_candidates(
        self,
        *,
        image_analysis: VisionAnalysis,
        category: str | None = None,
        limit: int = 5,
    ) -> RetrievalTrace:
        """Retrieve image-search candidates from the configured search repository."""
        hits = self.search_repository.search_image(image_analysis, limit=limit)
        candidates = [self._candidate_from_search_hit(hit) for hit in hits]
        if category:
            candidates = [candidate for candidate in candidates if candidate.product.category == category]
        return RetrievalTrace(
            query_text="",
            text_tokens=[],
            image_tokens=sorted((f"{image_analysis.summary} {' '.join(image_analysis.tags)}").split()),
            candidates=candidates,
            limit=limit,
        )

    def retrieve_multimodal_candidates(
        self,
        *,
        text_query: str,
        image_analysis: VisionAnalysis,
        category: str | None = None,
        limit: int = 5,
    ) -> RetrievalTrace:
        """Retrieve multimodal candidates from the configured search repository."""
        parsed, hits = self.search_repository.search_multimodal(text_query, image_analysis, limit=limit)
        candidates = [self._candidate_from_search_hit(hit) for hit in hits]
        if category:
            candidates = [candidate for candidate in candidates if candidate.product.category == category]
        return RetrievalTrace(
            query_text=parsed.remaining_query or parsed.normalized_query or text_query,
            text_tokens=sorted((parsed.remaining_query or parsed.normalized_query).split()),
            image_tokens=sorted((f"{image_analysis.summary} {' '.join(image_analysis.tags)}").split()),
            candidates=candidates,
            limit=limit,
        )

    def rerank_candidates(self, candidates: list[ScoredCandidate], strategy: str) -> RerankTrace:
        """Reorder candidates according to the selected ranking strategy."""
        before = list(candidates)
        if strategy == "text-score":
            after = sorted(before, key=lambda item: (item.text_score, item.product.rating), reverse=True)
        elif strategy == "image-score":
            after = sorted(before, key=lambda item: (item.image_score, item.product.rating), reverse=True)
        elif strategy == "multimodal-score":
            after = sorted(before, key=lambda item: (item.multimodal_score, item.product.rating), reverse=True)
        else:
            after = sorted(
                before,
                key=lambda item: (item.score, item.multimodal_score, item.text_score, item.image_score, item.product.rating),
                reverse=True,
            )
        return RerankTrace(strategy=strategy, candidates_before=before, candidates_after=after)

    def run_pipeline(
        self,
        *,
        prompt: str = "",
        image_path: str | Path | None = None,
        category: str | None = None,
        limit: int = 5,
    ) -> PipelineResult:
        """Execute the routed backend path and return the final trace."""
        image_analysis: VisionAnalysis | None = None
        retrieval: RetrievalTrace | None = None
        rerank: RerankTrace | None = None
        matches: list[Product] = []
        steps: list[ToolCallTrace] = []

        # The router is the first boundary: it decides whether this request
        # stays in chat mode or enters one of the retrieval paths.
        router = self.tools.route_intent(RouteIntentInput(prompt=prompt, has_image=image_path is not None))
        steps.append(
            ToolCallTrace(
                tool_name="route_intent",
                thought="Decide whether the request is conversational or retrieval-oriented.",
                input_summary=f"prompt={prompt!r}, has_image={image_path is not None}",
                observation_summary=f"intent={router.intent}; rationale={router.rationale}",
            )
        )

        if image_path:
            image_analysis = self.tools.analyze_image(AnalyzeImageInput(image_path=Path(image_path)))
            steps.append(
                ToolCallTrace(
                    tool_name="analyze_image",
                    thought="Extract visual summary and tags before retrieval.",
                    input_summary=str(image_path),
                    observation_summary=f"summary={image_analysis.summary}; tags={', '.join(image_analysis.tags)}",
                )
            )

        # Each intent maps to a dedicated path tool so the control flow stays
        # explicit and can later be upgraded to a graph-style executor.
        current_intent = router.intent
        if current_intent == "chat":
            return self._finalize_pipeline(
                router=router,
                image_analysis=image_analysis,
                retrieval=None,
                rerank=None,
                generation=self.tools.run_chat_path(
                    ChatPathInput(prompt=prompt, image_analysis=image_analysis, steps=steps)
                ),
                matches=[],
                steps=steps,
            )

        if current_intent == "text-search":
            path_result = self.tools.run_text_search_path(
                TextSearchPathInput(prompt=prompt, category=category, limit=limit, steps=steps)
            )
            retrieval, rerank, matches, generation = (
                path_result.retrieval,
                path_result.rerank,
                path_result.matches,
                path_result.generation,
            )
            return self._finalize_pipeline(
                router=router,
                image_analysis=image_analysis,
                retrieval=retrieval,
                rerank=rerank,
                generation=generation,
                matches=matches,
                steps=steps,
            )

        if current_intent == "image-search":
            path_result = self.tools.run_image_search_path(
                ImageSearchPathInput(
                    image_analysis=image_analysis,
                    category=category,
                    limit=limit,
                    steps=steps,
                )
            )
            retrieval, rerank, matches, generation = (
                path_result.retrieval,
                path_result.rerank,
                path_result.matches,
                path_result.generation,
            )
            return self._finalize_pipeline(
                router=router,
                image_analysis=image_analysis,
                retrieval=retrieval,
                rerank=rerank,
                generation=generation,
                matches=matches,
                steps=steps,
            )

        path_result = self.tools.run_multimodal_search_path(
            MultimodalSearchPathInput(
                prompt=prompt,
                image_analysis=image_analysis,
                category=category,
                limit=limit,
                steps=steps,
            )
        )
        retrieval, rerank, matches, generation = (
            path_result.retrieval,
            path_result.rerank,
            path_result.matches,
            path_result.generation,
        )
        return self._finalize_pipeline(
            router=router,
            image_analysis=image_analysis,
            retrieval=retrieval,
            rerank=rerank,
            generation=generation,
            matches=matches,
            steps=steps,
        )

    def _finalize_pipeline(
        self,
        *,
        router: RouterTrace,
        image_analysis: VisionAnalysis | None,
        retrieval: RetrievalTrace | None,
        rerank: RerankTrace | None,
        generation: GenerationTrace,
        matches: list[Product],
        steps: list[ToolCallTrace],
    ) -> PipelineResult:
        """Assemble the final result object shared by all pipeline paths."""
        trace = PipelineTrace(
            router=router,
            react=ReActTrace(
                initial_intent=router.intent,
                final_intent=generation.mode,
                steps=steps,
            ),
            image_analysis=image_analysis,
            retrieval=retrieval,
            rerank=rerank,
            generation=generation,
        )
        return PipelineResult(
            intent=generation.mode,
            content=generation.response,
            analysis=image_analysis,
            matches=matches,
            trace=trace,
        )

    def _tokenize(self, text: str) -> set[str]:
        """Normalize whitespace tokenization for lightweight scoring."""
        return {token.lower() for token in text.split() if token.strip()}

    def _get_vision_analyzer(self) -> VisionAnalyzer:
        """Lazily create the vision adapter when image analysis is needed."""
        if self.vision_analyzer is None:
            self.vision_analyzer = build_vision_analyzer()
        return self.vision_analyzer

    def _score_text(self, product: Product, tokens: set[str]) -> tuple[float, list[str]]:
        """Score one product against text tokens and record matched fields."""
        if not tokens:
            return product.rating, ["rating"]
        haystacks = [
            product.name.lower(),
            product.category.lower(),
            product.description.lower(),
            " ".join(tag.lower() for tag in product.tags),
        ]
        score = 0.0
        matched_fields: list[str] = []
        for token in tokens:
            if token in haystacks[0]:
                score += 3.0
                matched_fields.append("name")
            if token in haystacks[1]:
                score += 2.0
                matched_fields.append("category")
            if token in haystacks[2]:
                score += 1.5
                matched_fields.append("description")
            if token in haystacks[3]:
                score += 1.0
                matched_fields.append("tags")
        return round(score + product.rating / 10, 2), matched_fields

    def _score_image(self, product: Product, tokens: set[str]) -> tuple[float, list[str]]:
        """Score one product against vision-derived tokens."""
        if not tokens:
            return product.rating, ["rating"]
        haystacks = [
            product.visual_description.lower(),
            " ".join(tag.lower() for tag in product.image_tags),
            product.name.lower(),
        ]
        score = 0.0
        matched_fields: list[str] = []
        for token in tokens:
            if token in haystacks[0]:
                score += 3.0
                matched_fields.append("visual_description")
            if token in haystacks[1]:
                score += 2.0
                matched_fields.append("image_tags")
            if token in haystacks[2]:
                score += 1.0
                matched_fields.append("name")
        return round(score + product.rating / 10, 2), matched_fields

    def _candidate_from_search_hit(self, hit) -> ScoredCandidate:
        """Convert one repository hit into the shared retrieval candidate shape."""
        product = Product(
            id=hit.product_id,
            sku=hit.sku,
            name=hit.title,
            category=hit.category_name,
            rating=round(float(hit.seller_rating or 0), 2),
            tags=[],
            description=hit.short_description,
            image_url=hit.primary_image_url,
            image_tags=[],
            visual_description=hit.short_description,
            price=float(hit.price) if hit.price is not None else None,
            currency=hit.currency,
            seller_name=hit.seller_name,
            seller_rating=float(hit.seller_rating or 0),
            review_count=int(hit.review_count or 0),
            inventory_count=int(hit.inventory_count or 0),
            product_url=hit.product_url,
        )
        return ScoredCandidate(
            product=product,
            score=round(float(hit.match_score), 6),
            text_score=round(float(hit.text_score), 6),
            image_score=round(float(hit.image_score), 6),
            multimodal_score=round(float(hit.multimodal_score), 6),
            matched_fields=["repository"],
        )

    def _generate_chat_response(
        self,
        *,
        prompt: str,
        analysis: VisionAnalysis | None,
        products: list[Product],
    ) -> str:
        """Generate a scoped chat reply through the configured responder."""
        return self._get_chat_responder().generate(prompt=prompt, analysis=analysis)

    def _generate_search_response(
        self,
        *,
        intent: str,
        prompt: str,
        analysis: VisionAnalysis | None,
        products: list[Product],
    ) -> SearchResponse:
        """Generate a grounded search answer plus selected product ids."""
        return self._get_search_responder().generate(
            intent=intent,
            prompt=prompt,
            analysis=analysis,
            products=products,
        )

    def _get_chat_responder(self) -> ChatResponder:
        """Lazily create the configured chat responder."""
        if self.chat_responder is None:
            self.chat_responder = build_chat_responder()
        return self.chat_responder

    def _get_search_responder(self) -> SearchResponder:
        """Lazily create the configured search responder."""
        if self.search_responder is None:
            self.search_responder = build_search_responder()
        return self.search_responder
