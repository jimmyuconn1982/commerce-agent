from __future__ import annotations

"""Lightweight search parser for text-search requests.

Inputs:
- raw user search text
- optional known category names

Outputs:
- normalized query text
- extracted filters and category hints

Role:
- provide a small parser before retrieval and RAG
- keep text-search behavior explicit and upgradeable

Upgrade path:
- add richer query rewrite, synonym expansion, and LLM parsing later
"""

import re

from .models import ParsedSearchQuery

ATTRIBUTE_TERMS = {
    "black",
    "blue",
    "casual",
    "compact",
    "formal",
    "green",
    "large",
    "leather",
    "lightweight",
    "metal",
    "office",
    "outdoor",
    "red",
    "small",
    "travel",
    "white",
    "wood",
}


class SearchParser:
    """Lightweight parser for text-search normalization and filters."""

    def parse(self, query: str, known_categories: set[str] | None = None) -> ParsedSearchQuery:
        """Parse one raw text query into normalized search hints."""
        normalized = self._normalize(query)
        working = normalized

        min_price = None
        max_price = None
        sort = None

        max_match = re.search(r"\b(?:under|below|less than|max)\s+\$?(\d+(?:\.\d+)?)\b", working)
        if max_match:
            max_price = float(max_match.group(1))
            working = working.replace(max_match.group(0), " ")

        min_match = re.search(r"\b(?:over|above|more than|min)\s+\$?(\d+(?:\.\d+)?)\b", working)
        if min_match:
            min_price = float(min_match.group(1))
            working = working.replace(min_match.group(0), " ")

        if re.search(r"\b(?:cheapest|lowest price|low price|budget)\b", working):
            sort = "price_asc"
        elif re.search(r"\b(?:top rated|best rated|highest rated|best review)\b", working):
            sort = "rating_desc"

        category_hints: list[str] = []
        for category in sorted(known_categories or set()):
            if self._contains_term(working, category):
                category_hints.append(category)

        attribute_hints = [term for term in sorted(ATTRIBUTE_TERMS) if term in working]
        remaining = self._collapse_spaces(working)
        return ParsedSearchQuery(
            raw_query=query,
            normalized_query=normalized,
            remaining_query=remaining,
            category_hints=category_hints,
            attribute_hints=attribute_hints,
            min_price=min_price,
            max_price=max_price,
            sort=sort,
        )

    def _normalize(self, query: str) -> str:
        """Lowercase and simplify text before filter extraction."""
        lowered = query.strip().lower()
        lowered = re.sub(r"[^\w\s.-]", " ", lowered)
        return self._collapse_spaces(lowered)

    def _collapse_spaces(self, text: str) -> str:
        """Remove duplicate whitespace from the intermediate query text."""
        return re.sub(r"\s+", " ", text).strip()

    def _contains_term(self, text: str, term: str) -> bool:
        """Match ASCII terms by word boundary and CJK terms by substring."""
        if re.search(r"[\u4e00-\u9fff]", term):
            return term in text
        return re.search(rf"\b{re.escape(term)}\b", text) is not None
