"""
couplet.py — generate a short, artful verse for the photo strip.

Style: a haiku-ish 3-line micro-poem themed around tech, building, and hiring /
talent. Evocative, a little poetic, not cheesy. The guest's name is shown
separately on the strip as an attribution, so the poem itself stays clean.

Primary path: OpenRouter (OpenAI-compatible). Set OPENROUTER_API_KEY and
optionally OPENROUTER_MODEL. Fallback: hand-written haikus, so the booth always
works offline.

No em dashes anywhere (by request).
"""

from __future__ import annotations

import os
import random

OPENROUTER_API_KEY = os.environ.get("OPENROUTER_API_KEY")
OPENROUTER_MODEL = os.environ.get("OPENROUTER_MODEL", "openai/gpt-4o-mini")
OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"

# Offline fallback haikus — tech / hiring / building themed, no names needed.
_TEMPLATES = [
    ["Lines of code take flight,", "a quiet spark becomes flame,", "futures rewritten."],
    ["Talent finds its place,", "ideas bloom in the night air,", "the build never ends."],
    ["Hands that shape the new,", "between the zeros and ones,", "humans, still the spark."],
    ["Hire for the fire,", "the curious change the world,", "ship, learn, rise again."],
    ["Bold minds in the loop,", "every commit a promise,", "tomorrow compiles."],
    ["Between scale and soul,", "the best teams are quietly", "building what comes next."],
]


def _llm_verse(name: str, company: str | None) -> list[str]:
    """Ask an LLM (via OpenRouter) for a 3-line haiku. Returns three lines."""
    from openai import OpenAI

    client = OpenAI(api_key=OPENROUTER_API_KEY, base_url=OPENROUTER_BASE_URL)
    who = name + (f", who works at {company}" if company else "")
    prompt = (
        "Write one artful haiku (three short lines, roughly 5-7-5 syllables) about "
        "innovation, building great products, and brilliant people in tech and "
        "hiring. Make it evocative and a little poetic, never cheesy or corporate. "
        f"You may subtly nod to {who}, but keep it tasteful and optional. "
        "Do NOT use em dashes or hyphens as dashes. Return ONLY the three lines, "
        "each on its own line, with no title, numbering, or quotes."
    )
    resp = client.chat.completions.create(
        model=OPENROUTER_MODEL,
        messages=[{"role": "user", "content": prompt}],
        max_tokens=80,
        temperature=0.95,
    )
    text = resp.choices[0].message.content.strip()
    lines = [ln.strip().strip('"').replace(" — ", ", ").replace("—", ",") for ln in text.splitlines() if ln.strip()]
    if len(lines) >= 3:
        return lines[:3]
    if len(lines) == 2:
        return lines + [""]
    raise ValueError("verse too short")


def make_couplet(name: str | None, company: str | None = None) -> list[str]:
    """Return a 3-line verse. Never raises. (Name kept for API compatibility.)"""
    first = (name or "Friend").strip().split()[0] if name else "Friend"
    if OPENROUTER_API_KEY:
        try:
            print("[verse] generating via OpenRouter:", OPENROUTER_MODEL)
            return _llm_verse(first, company)
        except Exception as exc:  # noqa: BLE001 - fall back gracefully
            print("[verse] OpenRouter failed, using template:", exc)
    return random.choice(_TEMPLATES)
