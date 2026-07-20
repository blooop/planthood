"""Deterministic extract stage: clean method text into grounded step fragments.

No network, no LLM — pure functions over :class:`RawRecipe`. This is the biggest
quality lever: for the ~52% of recipes with explicit ``STEP n`` markers the split is
exact, so downstream enrichment can never invent or drop steps.
"""

from .extractor import extract_all, extract_recipe

__all__ = ["extract_recipe", "extract_all"]
