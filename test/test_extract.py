"""Unit tests for the deterministic extract stage."""

from planthood.extract import extract_recipe
from planthood.extract.extractor import _accept_markers, _instruction_region
from planthood.models import RawRecipe


def _raw(method: str, **kw) -> RawRecipe:
    return RawRecipe(id=kw.get("id", "r1"), title=kw.get("title", "Test Recipe"), method=method)


def test_step_markers_split_exactly():
    method = (
        "Some Title Marketing blurb about the dish. Prep time 2 Total time 20 "
        "Cooking Mode: Cooking instructions "
        "STEP 1 Preheat the oven to 200C. "
        "STEP 2 Chop the onions finely. "
        "STEP 3 Fry the onions for 5 minutes. "
        "What's in your box Onions Oil Nutritional info Calories 500kcal"
    )
    ex = extract_recipe(_raw(method))
    assert ex.cookable is True
    assert ex.extraction_method == "step_markers"
    assert [s.id for s in ex.steps] == ["step-1", "step-2", "step-3"]
    assert [s.marker for s in ex.steps] == [1, 2, 3]
    assert ex.steps[0].text == "Preheat the oven to 200C."
    assert ex.steps[1].text == "Chop the onions finely."


def test_terminator_strips_trailing_template():
    method = (
        "Cooking instructions STEP 1 Boil the pasta. "
        "What's in your box Pasta Nutritional info Calories 700kcal Protein 20g "
        "Ingredients / Allergens Wheat"
    )
    ex = extract_recipe(_raw(method))
    assert len(ex.steps) == 1
    # No nutrition/box/allergen text should leak into the step.
    assert "Nutritional" not in ex.steps[0].text
    assert "box" not in ex.steps[0].text
    assert "kcal" not in ex.steps[0].text


def test_curly_apostrophe_terminator():
    method = "STEP 1 Roast the squash. What’s in your box Squash Nutritional info 400kcal"
    ex = extract_recipe(_raw(method))
    assert ex.steps[0].text == "Roast the squash."


def test_inline_cross_reference_marker_is_ignored():
    # An inline "(STEP 3)" reference must not create a spurious step boundary.
    method = (
        "STEP 1 Preheat oven. "
        "STEP 2 Roast for 20 minutes (STEP 3). "
        "STEP 3 Plate and serve. "
        "What's in your box Stuff"
    )
    ex = extract_recipe(_raw(method))
    assert [s.marker for s in ex.steps] == [1, 2, 3]
    assert ex.steps[1].text.startswith("Roast for 20 minutes")
    assert ex.steps[2].text == "Plate and serve."


def test_out_of_sequence_marker_is_ignored():
    # A stray "STEP 5" while expecting 3 is treated as a reference, not a boundary.
    region = "STEP 1 a. STEP 2 b (see STEP 5). STEP 3 c. STEP 4 d. STEP 5 e."
    accepted = _accept_markers(region)
    assert [int(m.group(1)) for m in accepted] == [1, 2, 3, 4, 5]


def test_non_cookable_product_bundle():
    method = (
        "3 x Chocolate Hazelnut Snack Bar Bundle A bundle of raw whole food bars. "
        "Cooking Mode: Cooking instructions What's in your box 3 bars "
        "Nutritional info Calories 490kcal Ingredients / Allergens Cashews"
    )
    ex = extract_recipe(_raw(method))
    assert ex.cookable is False
    assert ex.steps == []
    assert ex.extraction_method == "none"


def test_paragraph_fallback_flags_llm_segmentation():
    method = (
        "Cooking instructions Heat the oil in a pan. Add the garlic and cook gently. "
        "Stir in the tomatoes and simmer. What's in your box Oil Garlic Tomatoes"
    )
    ex = extract_recipe(_raw(method))
    assert ex.cookable is True
    assert ex.extraction_method == "paragraph"
    assert ex.needs_llm_segmentation is True
    assert len(ex.steps) >= 2


def test_preamble_boilerplate_excluded_from_step_markers():
    # The "Before you start" / "Thoroughly wash" boilerplate precedes STEP 1 and is
    # naturally excluded by starting the region at the first marker.
    method = (
        "Cooking instructions Before you start, take out all the ingredients for this "
        "recipe (see 'what's in your box' section below). Thoroughly wash all fresh "
        "vegetables, leaves, salad ingredients and raw grains before cooking or serving. "
        "STEP 1 Preheat the oven. What's in your box Veg"
    )
    ex = extract_recipe(_raw(method))
    assert ex.steps[0].text == "Preheat the oven."
    assert "Before you start" not in ex.steps[0].text


def test_empty_method():
    ex = extract_recipe(_raw(""))
    assert ex.cookable is False
    assert ex.steps == []


def test_instruction_region_bounds():
    method = "junk before STEP 1 do a thing STEP 2 do another What's in your box items"
    region, first = _instruction_region(method)
    assert first == 1
    assert region.startswith("STEP 1")
    assert "What's in your box" not in region
    assert "junk before" not in region
