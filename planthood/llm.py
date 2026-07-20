"""LLM provider abstraction with schema-enforced structured output.

The enrich stage needs the model to return a JSON object matching a fixed schema. Rather
than parse free text (the old pipeline's fragile ``strip code fences`` approach, which
returned empty on any hiccup), every provider here returns a validated Python object via
its native structured-output mechanism (Anthropic tool-use, OpenAI/Gemini JSON mode).

A :class:`MockProvider` implements the same contract deterministically so the whole
pipeline runs — and is unit-tested — with no API key or network.
"""

from __future__ import annotations

import json
import os
import re
from abc import ABC, abstractmethod
from typing import List, Optional

from dotenv import load_dotenv

load_dotenv()

# Sentinel the enrich stage appends to the user prompt, followed by the steps as JSON.
# Real models read it as context; the mock parses the JSON that follows it.
STEPS_MARKER = "STEPS_JSON:"


class LLMProvider(ABC):
    """Return a structured object matching ``schema`` for the given prompt."""

    @abstractmethod
    def complete_json(self, system: str, user: str, schema: dict) -> object: ...

    @property
    @abstractmethod
    def name(self) -> str: ...


class AnthropicProvider(LLMProvider):
    """Anthropic Claude via tool-use forced structured output."""

    def __init__(self, api_key: Optional[str] = None, model: Optional[str] = None):
        from anthropic import Anthropic

        key = api_key or os.getenv("ANTHROPIC_API_KEY")
        if not key:
            raise ValueError("ANTHROPIC_API_KEY not set")
        self.model = model or os.getenv("ANTHROPIC_MODEL", "claude-haiku-4-5-20251001")
        self.client = Anthropic(api_key=key)

    def complete_json(self, system: str, user: str, schema: dict) -> object:
        resp = self.client.messages.create(
            model=self.model,
            max_tokens=4096,
            temperature=0,
            system=system,
            tools=[
                {
                    "name": "emit_result",
                    "description": "Return the structured result.",
                    "input_schema": schema,
                }
            ],
            tool_choice={"type": "tool", "name": "emit_result"},
            messages=[{"role": "user", "content": user}],
        )
        for block in resp.content:
            if getattr(block, "type", None) == "tool_use":
                return block.input
        raise RuntimeError("Anthropic response contained no tool_use block")

    @property
    def name(self) -> str:
        return f"anthropic:{self.model}"


class OpenAIProvider(LLMProvider):
    """OpenAI via JSON-schema structured output."""

    def __init__(self, api_key: Optional[str] = None, model: Optional[str] = None):
        from openai import OpenAI

        key = api_key or os.getenv("OPENAI_API_KEY")
        if not key:
            raise ValueError("OPENAI_API_KEY not set")
        self.model = model or os.getenv("OPENAI_MODEL", "gpt-4o-mini")
        self.client = OpenAI(api_key=key)

    def complete_json(self, system: str, user: str, schema: dict) -> object:
        resp = self.client.chat.completions.create(
            model=self.model,
            temperature=0,
            response_format={
                "type": "json_schema",
                "json_schema": {"name": "result", "schema": schema, "strict": False},
            },
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
        )
        return json.loads(resp.choices[0].message.content)

    @property
    def name(self) -> str:
        return f"openai:{self.model}"


class GeminiProvider(LLMProvider):
    """Google Gemini via JSON response mime type."""

    def __init__(self, api_key: Optional[str] = None, model: Optional[str] = None):
        import google.generativeai as genai

        key = api_key or os.getenv("GEMINI_API_KEY")
        if not key:
            raise ValueError("GEMINI_API_KEY not set")
        self.model_name = model or os.getenv("GEMINI_MODEL", "gemini-2.5-pro")
        genai.configure(api_key=key)
        self._genai = genai
        self.model = genai.GenerativeModel(self.model_name)

    def complete_json(self, system: str, user: str, schema: dict) -> object:
        resp = self.model.generate_content(
            f"{system}\n\n{user}",
            generation_config={"temperature": 0, "response_mime_type": "application/json"},
        )
        return json.loads(resp.text)

    @property
    def name(self) -> str:
        return f"gemini:{self.model_name}"


# --------------------------------------------------------------------------- #
# Mock provider — deterministic, offline, same contract
# --------------------------------------------------------------------------- #
_PREP = (
    "chop",
    "slice",
    "dice",
    "peel",
    "prepare",
    "preheat",
    "take out",
    "mix",
    "blend",
    "whisk",
    "measure",
    "rinse",
    "wash",
    "grate",
    "cut",
    "marinate",
    "drain",
    "combine",
)
_FINISH = ("serve", "plate", "garnish", "finish", "divide", "top with", "sprinkle", "drizzle over")
_COOK = (
    "heat",
    "cook",
    "fry",
    "bake",
    "roast",
    "boil",
    "simmer",
    "saute",
    "sauté",
    "grill",
    "steam",
    "toast",
    "warm",
    "sear",
    "stir",
)
_EQUIPMENT = (
    "oven",
    "pan",
    "frying pan",
    "saucepan",
    "casserole dish",
    "roasting tray",
    "tray",
    "blender",
    "bowl",
    "pot",
    "baking sheet",
    "grill",
    "hob",
    "mixing bowl",
    "sieve",
)


def _infer_type(text: str) -> str:
    low = text.lower()
    if "preheat" in low:  # "preheat" contains "heat"; it is prep, not cook
        return "prep"
    if any(w in low for w in _FINISH):
        return "finish"
    if any(w in low for w in _COOK):
        return "cook"
    if any(w in low for w in _PREP):
        return "prep"
    return "cook"


def _infer_duration(text: str, step_type: str) -> int:
    m = re.search(r"(\d+)\s*(?:-|–|to)\s*(\d+)\s*min", text, re.I)
    if m:
        return max(1, (int(m.group(1)) + int(m.group(2))) // 2)
    m = re.search(r"(\d+)\s*min", text, re.I)
    if m:
        return max(1, int(m.group(1)))
    return {"prep": 3, "cook": 8, "finish": 2}[step_type]


def _infer_temp(text: str) -> Optional[int]:
    m = re.search(r"(\d{2,3})\s*°?\s*C", text)
    return int(m.group(1)) if m else None


def _infer_equipment(text: str) -> List[str]:
    low = text.lower()
    return sorted({e for e in _EQUIPMENT if e in low})


def mock_enrich_steps(steps: List[dict]) -> List[dict]:
    """Deterministically enrich a list of ``{id, text}`` steps (mirrors the real schema)."""
    out = []
    for i, s in enumerate(steps):
        text = s.get("text", "")
        stype = _infer_type(text)
        label = " ".join(text.split()[:6]) or f"Step {i + 1}"
        out.append(
            {
                "id": s.get("id", f"step-{i + 1}"),
                "label": label.rstrip(".,"),
                "type": stype,
                "estimated_duration_minutes": _infer_duration(text, stype),
                "equipment": _infer_equipment(text),
                "temperature_c": _infer_temp(text),
                # Linear dependency chain: a simple, valid graph for offline runs/tests.
                "requires": [f"step-{i}"] if i > 0 else [],
                "can_overlap_with": [],
                "notes": "",
            }
        )
    return out


class MockProvider(LLMProvider):
    """Offline provider: parses the steps appended after ``STEPS_MARKER`` and enriches them."""

    def complete_json(self, system: str, user: str, schema: dict) -> object:
        _, _, tail = user.partition(STEPS_MARKER)
        try:
            steps = json.loads(tail.strip()) if tail.strip() else []
        except json.JSONDecodeError:
            steps = []
        return {"steps": mock_enrich_steps(steps)}

    @property
    def name(self) -> str:
        return "mock"


_PROVIDERS = {
    "anthropic": AnthropicProvider,
    "openai": OpenAIProvider,
    "gemini": GeminiProvider,
    "mock": MockProvider,
}


def get_provider(name: Optional[str] = None, **kwargs) -> LLMProvider:
    """Factory. Defaults to ``$LLM_PROVIDER`` or ``anthropic``. Use ``mock`` offline."""
    name = (name or os.getenv("LLM_PROVIDER", "anthropic")).lower()
    if name not in _PROVIDERS:
        raise ValueError(f"Unknown provider '{name}'. Choose from: {', '.join(_PROVIDERS)}")
    if name == "mock":
        return MockProvider()
    return _PROVIDERS[name](**kwargs)
