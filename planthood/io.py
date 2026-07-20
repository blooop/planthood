"""Artifact IO for the pipeline: typed load, and **merge-safe** save.

The single most damaging bug in the old pipeline was that a failed re-parse (which
returns an empty step list) overwrote a previously-good parse, destroying data. Every
save here goes through :func:`merge_recipes`, which refuses to replace a recipe that
already has content with one that has none.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Callable, Dict, List, Optional, Sequence, Type, TypeVar

from pydantic import BaseModel, ValidationError

DATA_DIR = Path(__file__).resolve().parent.parent / "data"

# Canonical artifact paths.
RAW_PATH = DATA_DIR / "raw_recipes.json"
EXTRACTED_PATH = DATA_DIR / "recipes_extracted.json"
PARSED_PATH = DATA_DIR / "recipes_parsed.json"
SCHEDULED_PATH = DATA_DIR / "recipes_with_schedule.json"

M = TypeVar("M", bound=BaseModel)


# --------------------------------------------------------------------------- #
# JSON primitives
# --------------------------------------------------------------------------- #
def read_json(path: Path):
    """Load raw JSON, or return None if the file is missing."""
    if not Path(path).exists():
        return None
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def write_json(path: Path, obj) -> None:
    """Write pretty JSON with a trailing newline (matches repo convention)."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(obj, f, indent=2, ensure_ascii=False)
        f.write("\n")


# --------------------------------------------------------------------------- #
# Typed recipe list load / dump
# --------------------------------------------------------------------------- #
def load_recipes(path: Path, model: Type[M]) -> List[M]:
    """Load a JSON array and validate each item against ``model``.

    Invalid rows are skipped with a warning rather than aborting the whole load, so one
    corrupt record never blocks the pipeline.
    """
    data = read_json(path)
    if data is None:
        return []
    if not isinstance(data, list):
        raise ValueError(f"{path} does not contain a JSON array")

    out: List[M] = []
    for i, item in enumerate(data):
        try:
            out.append(model.model_validate(item))
        except ValidationError as e:
            rid = item.get("id", f"#{i}") if isinstance(item, dict) else f"#{i}"
            print(f"Warning: skipping invalid {model.__name__} '{rid}': {e.error_count()} error(s)")
    return out


def dump_recipes(path: Path, recipes: Sequence[BaseModel]) -> None:
    """Serialize a list of recipe models to JSON (json mode handles nested/optional)."""
    write_json(path, [r.model_dump(mode="json") for r in recipes])


# --------------------------------------------------------------------------- #
# Merge-safe save
# --------------------------------------------------------------------------- #
def has_steps(recipe: BaseModel) -> bool:
    """Default content predicate: a recipe 'has content' if it has steps, or is
    intentionally empty (``cookable=False`` — e.g. a product bundle with no method)."""
    if getattr(recipe, "cookable", True) is False:
        return True
    steps = getattr(recipe, "steps", None)
    return bool(steps)


def merge_recipes(
    existing: Sequence[M],
    incoming: Sequence[M],
    has_content: Callable[[M], bool] = has_steps,
    force: bool = False,
) -> List[M]:
    """Merge ``incoming`` into ``existing`` keyed by ``id``.

    An incoming recipe replaces the existing one unless doing so would drop content:
    if the existing record has content and the incoming one does not, the existing
    record is kept (the incoming empty result is treated as a failed parse). Pass
    ``force=True`` to overwrite unconditionally.
    """
    by_id: Dict[str, M] = {r.id: r for r in existing}
    for rec in incoming:
        prior = by_id.get(rec.id)
        if not force and prior is not None and has_content(prior) and not has_content(rec):
            print(f"Keeping existing '{rec.id}': incoming result is empty (treated as failure)")
            continue
        by_id[rec.id] = rec
    return list(by_id.values())


def save_recipes(
    path: Path,
    incoming: Sequence[M],
    model: Type[M],
    *,
    merge: bool = True,
    has_content: Callable[[M], bool] = has_steps,
    force: bool = False,
) -> List[M]:
    """Merge-save recipes to ``path`` and return the final list.

    With ``merge=True`` (default) the incoming recipes are merged into whatever is
    already on disk using :func:`merge_recipes`. With ``merge=False`` the file is
    replaced wholesale (used for full clean-slate rebuilds).
    """
    if merge:
        existing = load_recipes(path, model)
        final = merge_recipes(existing, incoming, has_content=has_content, force=force)
    else:
        final = list(incoming)
    dump_recipes(path, final)
    return final


# --------------------------------------------------------------------------- #
# Content-addressed cache key (stage + input + prompt/model version)
# --------------------------------------------------------------------------- #
def content_hash(*parts: str) -> str:
    """Stable hash over the given parts, for cache keys keyed on inputs and versions."""
    joined = "\x00".join(parts)
    return hashlib.sha256(joined.encode("utf-8")).hexdigest()


class Cache:
    """Minimal file cache: values are JSON, keyed by a content hash under ``cache_dir``."""

    def __init__(self, cache_dir: Path, enabled: bool = True):
        self.cache_dir = Path(cache_dir)
        self.enabled = enabled
        if enabled:
            self.cache_dir.mkdir(parents=True, exist_ok=True)

    def get(self, key: str) -> Optional[object]:
        if not self.enabled:
            return None
        f = self.cache_dir / f"{key}.json"
        if f.exists():
            try:
                return json.loads(f.read_text(encoding="utf-8"))
            except (json.JSONDecodeError, OSError) as e:
                print(f"Cache read error for {key}: {e}")
        return None

    def set(self, key: str, value) -> None:
        if not self.enabled:
            return
        f = self.cache_dir / f"{key}.json"
        try:
            f.write_text(json.dumps(value, indent=2, ensure_ascii=False), encoding="utf-8")
        except OSError as e:
            print(f"Cache write error for {key}: {e}")
