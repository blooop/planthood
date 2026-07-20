"""LLM enrich stage: add scheduling metadata to already-grounded steps.

For marker-split recipes the extractor's step ids and texts are authoritative — the LLM
returns one enrichment object per fixed id and can neither invent nor drop steps. For
heuristically split ("paragraph") recipes the LLM may re-segment.
"""

from .enricher import ENRICH_SCHEMA, enrich_all, enrich_recipe

__all__ = ["enrich_recipe", "enrich_all", "ENRICH_SCHEMA"]
