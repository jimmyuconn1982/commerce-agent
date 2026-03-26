from __future__ import annotations

"""Snowflake-like bigint id helpers for local data generation.

Inputs:
- entity names such as `public_product` or `text_embedding`
- either sequential allocation or a stable natural key

Outputs:
- positive bigint ids that are unique per entity namespace

Role:
- replace scattered `*_ID_BASE` constants with one shared generator
- keep seed and embedding builders on the same id strategy

Upgrade path:
- swap the local generator for a real distributed snowflake service later
- preserve entity namespaces so downstream tables do not need to change
"""

from dataclasses import dataclass, field
import hashlib


ENTITY_CODES: dict[str, int] = {
    "tiny_category": 1,
    "tiny_seller": 2,
    "tiny_media": 3,
    "tiny_offer": 4,
    "public_product": 5,
    "public_category": 6,
    "public_seller": 7,
    "public_media": 8,
    "public_offer": 9,
    "text_embedding": 20,
    "image_embedding": 21,
    "multimodal_embedding": 22,
}

PAYLOAD_BITS = 55
PAYLOAD_MASK = (1 << PAYLOAD_BITS) - 1


@dataclass(slots=True)
class SnowflakeLikeIdGenerator:
    """Generate bigint ids with explicit entity namespaces."""

    counters: dict[str, int] = field(default_factory=dict)

    def next(self, entity: str) -> int:
        """Allocate the next sequential id for one entity namespace."""
        sequence = self.counters.get(entity, 0) + 1
        self.counters[entity] = sequence
        return self._compose(entity, sequence)

    def stable(self, entity: str, natural_key: str | int) -> int:
        """Map one natural key into a stable bigint id within one entity namespace."""
        digest = hashlib.blake2b(f"{entity}:{natural_key}".encode("utf-8"), digest_size=8).digest()
        payload = int.from_bytes(digest, "big") & PAYLOAD_MASK
        if payload == 0:
            payload = 1
        return self._compose(entity, payload)

    def _compose(self, entity: str, payload: int) -> int:
        code = ENTITY_CODES[entity]
        return (code << PAYLOAD_BITS) | (payload & PAYLOAD_MASK)
