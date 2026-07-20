"""Golden regression for the deterministic extract stage.

Locks the extraction of a curated, diverse set of real recipes so that changes to the
extractor which alter step counts / classification are caught. Regenerate the snapshot
with scripts if the extractor is intentionally changed.
"""

import json
from pathlib import Path

import pytest

from planthood import io
from planthood.extract import extract_recipe
from planthood.models import RawRecipe

GOLDEN = json.loads((Path(__file__).parent / "golden" / "extraction.json").read_text())
RAWS = {r.id: r for r in io.load_recipes(io.RAW_PATH, RawRecipe)}


@pytest.mark.parametrize("entry", GOLDEN, ids=[g["id"] for g in GOLDEN])
def test_extraction_matches_golden(entry):
    raw = RAWS.get(entry["id"])
    if raw is None:
        pytest.skip(f"raw recipe {entry['id']} not present")
    ex = extract_recipe(raw)
    assert ex.cookable == entry["cookable"]
    assert ex.extraction_method == entry["extraction_method"]
    assert len(ex.steps) == entry["step_count"]
    if ex.steps:
        assert ex.steps[0].text.startswith(entry["first_step_prefix"])
