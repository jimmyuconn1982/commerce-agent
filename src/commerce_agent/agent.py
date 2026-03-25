from __future__ import annotations

from pathlib import Path
import re
from typing import Callable

from .catalog import Catalog
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
from .vision import OpenAIVisionAnalyzer, VisionAnalyzer


class CommerceAgent:
    def __init__(
        self,
        catalog: Catalog | None = None,
        vision_analyzer: VisionAnalyzer | None = None,
    ) -> None:
        self.catalog = catalog or Catalog.from_json()
        self.vision_analyzer = vision_analyzer

    def text_search(
        self,
        query: str = "",
        *,
        category: str | None = None,
        limit: int = 5,
    ) -> list[Product]:
        retrieval = self.tool_text_search(query=query, category=category, limit=limit)
        rerank = self.tool_rerank(retrieval.candidates, strategy="text-score")
        return [candidate.product for candidate in rerank.candidates_after[:limit]]

    def image_search(self, image_path: str | Path, limit: int = 5) -> tuple[VisionAnalysis, list[Product]]:
        analysis = self.tool_analyze_image(Path(image_path))
        retrieval = self.tool_image_search(image_analysis=analysis, limit=limit)
        rerank = self.tool_rerank(retrieval.candidates, strategy="image-score")
        return analysis, [candidate.product for candidate in rerank.candidates_after[:limit]]

    def multimodal_search(
        self,
        *,
        text_query: str = "",
        image_path: str | Path | None = None,
        category: str | None = None,
        limit: int = 5,
    ) -> tuple[VisionAnalysis | None, list[Product]]:
        analysis = self.tool_analyze_image(Path(image_path)) if image_path else None
        retrieval = self.tool_multimodal_search(
            text_query=text_query,
            image_analysis=analysis,
            category=category,
            limit=limit,
        )
        rerank = self.tool_rerank(retrieval.candidates, strategy="blended-score")
        return analysis, [candidate.product for candidate in rerank.candidates_after[:limit]]

    def chat(self, prompt: str, image_path: str | Path | None = None) -> str:
        analysis = self.tool_analyze_image(Path(image_path)) if image_path else None
        retrieval = self.tool_multimodal_search(text_query=prompt, image_analysis=analysis, limit=3)
        rerank = self.tool_rerank(retrieval.candidates, strategy="blended-score")
        products = [candidate.product for candidate in rerank.candidates_after[:3]]
        return self.tool_generate_chat(prompt=prompt, analysis=analysis, products=products)

    def classify_intent(self, prompt: str = "", has_image: bool = False) -> str:
        return self.route_intent(prompt=prompt, has_image=has_image).intent

    def route_intent(self, prompt: str = "", has_image: bool = False) -> RouterTrace:
        text = prompt.strip().lower()
        if has_image and text:
            return RouterTrace(prompt=prompt, has_image=has_image, intent="multimodal-search", rationale="image and text are both present")
        if has_image:
            return RouterTrace(prompt=prompt, has_image=has_image, intent="image-search", rationale="image is present without text")
        if not text:
            return RouterTrace(prompt=prompt, has_image=has_image, intent="chat", rationale="empty text defaults to chat")

        question_words = {
            "what",
            "which",
            "how",
            "why",
            "can",
            "could",
            "should",
            "help",
            "recommend",
            "suggest",
            "compare",
            "need",
            "want",
            "looking",
            "find me",
        }
        search_words = {
            "search",
            "find",
            "show",
            "red",
            "blue",
            "hat",
            "shoes",
            "keyboard",
            "desk",
            "bottle",
            "hoodie",
            "earbuds",
        }

        if "?" in text:
            return RouterTrace(prompt=prompt, has_image=has_image, intent="chat", rationale="question mark indicates conversational intent")
        if any(phrase in text for phrase in question_words):
            return RouterTrace(prompt=prompt, has_image=has_image, intent="chat", rationale="question or recommendation phrasing detected")

        tokens = self._tokenize(re.sub(r"[^\w\s-]", " ", text))
        if len(tokens) <= 6 and any(token in search_words for token in tokens):
            return RouterTrace(prompt=prompt, has_image=has_image, intent="text-search", rationale="short query with search-oriented product terms")
        if len(tokens) <= 5:
            return RouterTrace(prompt=prompt, has_image=has_image, intent="text-search", rationale="short keyword-like query")
        return RouterTrace(prompt=prompt, has_image=has_image, intent="chat", rationale="longer prompt defaults to chat")

    def get_tools(self) -> dict[str, Callable[..., object]]:
        return {
            "route_intent": self.route_intent,
            "analyze_image": self.tool_analyze_image,
            "text_search": self.tool_text_search,
            "image_search": self.tool_image_search,
            "multimodal_search": self.tool_multimodal_search,
            "rerank": self.tool_rerank,
            "generate_chat": self.tool_generate_chat,
            "generate_search_summary": self.tool_generate_search_summary,
        }

    def tool_analyze_image(self, image_path: Path) -> VisionAnalysis:
        return self._get_vision_analyzer().analyze(Path(image_path))

    def tool_text_search(
        self,
        *,
        query: str,
        category: str | None = None,
        limit: int = 5,
    ) -> RetrievalTrace:
        return self.retrieve_candidates(text_query=query, category=category, limit=limit)

    def tool_image_search(
        self,
        *,
        image_analysis: VisionAnalysis,
        category: str | None = None,
        limit: int = 5,
    ) -> RetrievalTrace:
        return self.retrieve_candidates(image_analysis=image_analysis, category=category, limit=limit)

    def tool_multimodal_search(
        self,
        *,
        text_query: str,
        image_analysis: VisionAnalysis | None = None,
        category: str | None = None,
        limit: int = 5,
    ) -> RetrievalTrace:
        return self.retrieve_candidates(
            text_query=text_query,
            image_analysis=image_analysis,
            category=category,
            limit=limit,
        )

    def tool_rerank(self, candidates: list[ScoredCandidate], strategy: str) -> RerankTrace:
        return self.rerank_candidates(candidates, strategy)

    def tool_generate_chat(
        self,
        *,
        prompt: str,
        analysis: VisionAnalysis | None,
        products: list[Product],
    ) -> str:
        return self._generate_chat_response(prompt=prompt, analysis=analysis, products=products)

    def tool_generate_search_summary(self, *, intent: str, matches: list[Product]) -> str:
        label = {
            "text-search": "text",
            "image-search": "visual",
            "multimodal-search": "multimodal",
        }.get(intent, "search")
        return f"Found {len(matches)} {label} matches."

    def retrieve_candidates(
        self,
        *,
        text_query: str = "",
        image_analysis: VisionAnalysis | None = None,
        category: str | None = None,
        limit: int = 5,
    ) -> RetrievalTrace:
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

    def rerank_candidates(self, candidates: list[ScoredCandidate], strategy: str) -> RerankTrace:
        before = list(candidates)
        if strategy == "text-score":
            after = sorted(before, key=lambda item: (item.text_score, item.product.rating), reverse=True)
        elif strategy == "image-score":
            after = sorted(before, key=lambda item: (item.image_score, item.product.rating), reverse=True)
        else:
            after = sorted(before, key=lambda item: (item.score, item.product.rating), reverse=True)
        return RerankTrace(strategy=strategy, candidates_before=before, candidates_after=after)

    def run_pipeline(
        self,
        *,
        prompt: str = "",
        image_path: str | Path | None = None,
        category: str | None = None,
        limit: int = 5,
    ) -> PipelineResult:
        image_analysis: VisionAnalysis | None = None
        retrieval: RetrievalTrace | None = None
        rerank: RerankTrace | None = None
        matches: list[Product] = []
        steps: list[ToolCallTrace] = []

        router = self.route_intent(prompt=prompt, has_image=image_path is not None)
        steps.append(
            ToolCallTrace(
                tool_name="route_intent",
                thought="Decide whether the request is conversational or retrieval-oriented.",
                input_summary=f"prompt={prompt!r}, has_image={image_path is not None}",
                observation_summary=f"intent={router.intent}; rationale={router.rationale}",
            )
        )

        if image_path:
            image_analysis = self.tool_analyze_image(Path(image_path))
            steps.append(
                ToolCallTrace(
                    tool_name="analyze_image",
                    thought="Extract visual summary and tags before retrieval.",
                    input_summary=str(image_path),
                    observation_summary=f"summary={image_analysis.summary}; tags={', '.join(image_analysis.tags)}",
                )
            )

        current_intent = router.intent
        if current_intent == "text-search":
            retrieval = self.tool_text_search(query=prompt, category=category, limit=limit)
            steps.append(
                ToolCallTrace(
                    tool_name="text_search",
                    thought="Use text retrieval for keyword-heavy queries.",
                    input_summary=f"query={prompt!r}",
                    observation_summary=f"candidates={len(retrieval.candidates)}",
                )
            )
            rerank = self.tool_rerank(retrieval.candidates, strategy="text-score")
        elif current_intent == "image-search":
            retrieval = self.tool_image_search(image_analysis=image_analysis, category=category, limit=limit)
            steps.append(
                ToolCallTrace(
                    tool_name="image_search",
                    thought="Use visual features for image-only search.",
                    input_summary=f"summary={image_analysis.summary if image_analysis else ''}",
                    observation_summary=f"candidates={len(retrieval.candidates)}",
                )
            )
            rerank = self.tool_rerank(retrieval.candidates, strategy="image-score")
        else:
            retrieval = self.tool_multimodal_search(
                text_query=prompt,
                image_analysis=image_analysis,
                category=category,
                limit=limit,
            )
            steps.append(
                ToolCallTrace(
                    tool_name="multimodal_search" if image_analysis else "text_search",
                    thought="Gather candidates before deciding how to answer.",
                    input_summary=f"text={prompt!r}; has_image={image_analysis is not None}",
                    observation_summary=f"candidates={len(retrieval.candidates)}",
                )
            )
            rerank = self.tool_rerank(
                retrieval.candidates,
                strategy="blended-score" if image_analysis or current_intent == "chat" else "text-score",
            )

        steps.append(
            ToolCallTrace(
                tool_name="rerank",
                thought="Promote the strongest candidates for the chosen intent.",
                input_summary=f"strategy={rerank.strategy}; before={len(rerank.candidates_before)}",
                observation_summary=f"after={len(rerank.candidates_after)}",
            )
        )
        matches = [candidate.product for candidate in rerank.candidates_after[:limit]]

        if current_intent == "chat":
            content = self.tool_generate_chat(prompt=prompt, analysis=image_analysis, products=matches)
            generator_tool = "generate_chat"
            generator_thought = "Compose a conversational answer grounded in the top retrieved products."
        else:
            content = self.tool_generate_search_summary(intent=current_intent, matches=matches)
            generator_tool = "generate_search_summary"
            generator_thought = "Return a concise retrieval summary for the UI."

        steps.append(
            ToolCallTrace(
                tool_name=generator_tool,
                thought=generator_thought,
                input_summary=f"matches={len(matches)}",
                observation_summary=content,
            )
        )
        generation = GenerationTrace(
            mode=current_intent,
            prompt=prompt,
            selected_product_ids=[product.id for product in matches],
            response=content,
        )
        trace = PipelineTrace(
            router=router,
            react=ReActTrace(
                initial_intent=router.intent,
                final_intent=current_intent,
                steps=steps,
            ),
            image_analysis=image_analysis,
            retrieval=retrieval,
            rerank=rerank,
            generation=generation,
        )
        return PipelineResult(
            intent=current_intent,
            content=content,
            analysis=image_analysis,
            matches=matches,
            trace=trace,
        )

    def _tokenize(self, text: str) -> set[str]:
        return {token.lower() for token in text.split() if token.strip()}

    def _get_vision_analyzer(self) -> VisionAnalyzer:
        if self.vision_analyzer is None:
            self.vision_analyzer = OpenAIVisionAnalyzer()
        return self.vision_analyzer

    def _score_text(self, product: Product, tokens: set[str]) -> tuple[float, list[str]]:
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

    def _generate_chat_response(
        self,
        *,
        prompt: str,
        analysis: VisionAnalysis | None,
        products: list[Product],
    ) -> str:
        lower_prompt = prompt.lower()
        if not products:
            return (
                "I could not find a strong catalog match. Try giving me a product type, "
                "style cue, or visual description."
            )
        if any(word in lower_prompt for word in {"image", "photo", "picture", "look"}):
            lead = "Based on your visual intent, these are the closest matches:"
        elif any(word in lower_prompt for word in {"find", "search", "looking"}):
            lead = "Here are the strongest matches from the catalog:"
        else:
            lead = "Here is a concise recommendation set:"
        lines = [lead]
        if analysis:
            lines.append(f"Image summary: {analysis.summary}")
            if analysis.tags:
                lines.append(f"Image tags: {', '.join(analysis.tags)}")
        for product in products:
            lines.append(
                f"- {product.name}: {product.description} Visual cue: {product.visual_description}"
            )
        return "\n".join(lines)
