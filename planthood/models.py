"""Typed data contracts for the recipe pipeline.

Every pipeline stage reads and writes one of these artifacts. Each model carries a
``schema_version`` so artifacts are self-describing and future migrations are explicit.

Stage flow::

    RawRecipe        (scrape)   -> data/raw_recipes.json
    ExtractedRecipe  (extract)  -> data/recipes_extracted.json   [deterministic, no LLM]
    ParsedRecipe     (enrich)   -> data/recipes_parsed.json      [LLM enrichment]
    ScheduledRecipe  (schedule) -> data/recipes_with_schedule.json

The ``ScheduledRecipe``/``ScheduledStep`` field names are the contract consumed by the
Next.js site (see ``site/lib/types.ts``); keep them in sync.
"""

from __future__ import annotations

from typing import List, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field

SCHEMA_VERSION = 1

StepType = Literal["prep", "cook", "finish"]

# How an extracted recipe's steps were obtained.
#   step_markers      -> split deterministically on "STEP n" markers (exact, grounded)
#   paragraph         -> split on sentence/paragraph heuristics (needs LLM refinement)
#   none              -> no cookable instructions found (e.g. product bundle)
ExtractionMethod = Literal["step_markers", "paragraph", "none"]


class Nutrition(BaseModel):
    """Per-person nutrition facts. All fields optional; absent values stay None."""

    model_config = ConfigDict(extra="ignore")

    calories: Optional[float] = None
    protein_g: Optional[float] = None
    fat_g: Optional[float] = None
    carbs_g: Optional[float] = None
    fibre_g: Optional[float] = None
    salt_g: Optional[float] = None


class RecipeMeta(BaseModel):
    """Fields shared by every recipe artifact, carried forward unchanged through stages."""

    model_config = ConfigDict(extra="ignore")

    id: str
    title: str
    source_url: str = ""
    week_label: Optional[str] = None
    weeks: List[str] = Field(default_factory=list)
    category: Optional[str] = None
    ingredients: List[str] = Field(default_factory=list)
    nutrition: Optional[Nutrition] = None


# --------------------------------------------------------------------------- #
# Stage 1: scrape
# --------------------------------------------------------------------------- #
class RawRecipe(RecipeMeta):
    """Raw recipe as scraped from the source site. ``method`` is uncleaned page text."""

    schema_version: int = SCHEMA_VERSION
    method: str = ""


# --------------------------------------------------------------------------- #
# Stage 2: extract (deterministic — no LLM)
# --------------------------------------------------------------------------- #
class ExtractedStep(BaseModel):
    """A single grounded instruction, split from the cleaned method text.

    ``text`` is a verbatim (whitespace-normalised) fragment of the source method — it is
    never paraphrased, so downstream enrichment cannot silently invent or drop content.
    """

    model_config = ConfigDict(extra="ignore")

    id: str  # "step-1", "step-2", ... sequential and stable
    text: str
    marker: Optional[int] = None  # the STEP number from the source, when present


class ExtractedRecipe(RecipeMeta):
    """Deterministically cleaned recipe with grounded step texts (pre-enrichment)."""

    schema_version: int = SCHEMA_VERSION
    method_clean: str = ""  # method text after stripping template/marketing regions
    steps: List[ExtractedStep] = Field(default_factory=list)
    cookable: bool = True  # False => product bundle / no instructions (legitimately empty)
    extraction_method: ExtractionMethod = "none"
    needs_llm_segmentation: bool = False  # paragraph split that the LLM should refine
    notes: str = ""  # human-readable reason, e.g. why classified non-cookable


# --------------------------------------------------------------------------- #
# Stage 3: enrich (LLM)
# --------------------------------------------------------------------------- #
class RecipeStep(BaseModel):
    """A step enriched with scheduling metadata by the LLM stage."""

    model_config = ConfigDict(extra="ignore")

    id: str
    raw_text: str  # grounded source fragment (from ExtractedStep.text)
    label: str  # 3-8 word action summary
    type: StepType
    estimated_duration_minutes: int = Field(ge=1)
    requires: List[str] = Field(default_factory=list)
    can_overlap_with: List[str] = Field(default_factory=list)
    equipment: List[str] = Field(default_factory=list)
    temperature_c: Optional[int] = None
    notes: str = ""


class ParsedRecipe(RecipeMeta):
    """Recipe with enriched, dependency-aware steps (pre-scheduling).

    ``provenance`` records how the steps were produced so daily runs can resume:
      * ``llm``      — genuine model enrichment (skip on future runs unless the text changed)
      * ``fallback`` — deterministic enrichment (a candidate for LLM enrichment next run)
      * ``none``     — non-cookable / no steps
    ``source_hash`` fingerprints the extracted steps the enrichment was based on, so a
    re-scraped recipe whose text changed is re-enriched rather than kept stale.
    """

    schema_version: int = SCHEMA_VERSION
    steps: List[RecipeStep] = Field(default_factory=list)
    cookable: bool = True
    provenance: str = "none"
    source_hash: str = ""


# --------------------------------------------------------------------------- #
# Stage 4: schedule
# --------------------------------------------------------------------------- #
class ScheduledStep(BaseModel):
    """A step with a computed timeline. Field names are the site rendering contract."""

    model_config = ConfigDict(extra="ignore")

    id: str
    raw_text: str
    label: str
    type: str
    duration_min: int
    start_min: int
    end_min: int
    requires: List[str] = Field(default_factory=list)
    can_overlap_with: List[str] = Field(default_factory=list)
    equipment: List[str] = Field(default_factory=list)
    temperature_c: Optional[int] = None
    notes: str = ""
    is_critical: bool = False
    slack_min: int = 0
    latest_start_min: int = 0
    latest_end_min: int = 0


class ScheduledRecipe(RecipeMeta):
    """Final artifact consumed by the site: recipe + scheduled steps + timing totals."""

    schema_version: int = SCHEMA_VERSION
    steps: List[ScheduledStep] = Field(default_factory=list)
    total_time_min: int = 0
    active_time_min: int = 0
