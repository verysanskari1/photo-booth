"""
couplet.py — generate a short, artful RHYMING couplet for the photo strip.

Style: two lines that rhyme, themed around tech, building, and hiring / talent.
Evocative and a little poetic, never cheesy. The guest's name is shown
separately on the strip, so the couplet itself stays clean.

Primary path: OpenRouter (OpenAI-compatible). Fallback: hand-written rhyming
couplets, so the booth always works offline. No em dashes.
"""

from __future__ import annotations

import os
import random

OPENROUTER_API_KEY = os.environ.get("OPENROUTER_API_KEY")
OPENROUTER_MODEL = os.environ.get("OPENROUTER_MODEL", "openai/gpt-4o-mini")
OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"

# Offline fallback rhyming couplets. {name} = first name. Themed on leaders who
# shape tech, teams, and talent (recruiters, VPs of Engineering, etc).
_TEMPLATES = [
    ["{name} builds the teams that build the new,", "where talent thrives and visions break through."],
    ["With {name} steering, futures ignite,", "great people and bold code take flight."],
    ["{name} finds the spark in every hire,", "and lifts the whole team higher and higher."],
    ["Through {name}'s eye, rare talent is found,", "where minds and machines together compound."],
    ["{name} shapes the talent of the age,", "turning bright ideas to center stage."],
    ["For {name}, who grows the ones who dare,", "great teams and greater futures everywhere."],
]


def _llm_verse(name: str, company: str | None) -> list[str]:
    """Ask an LLM (via OpenRouter) for a 2-line rhyming couplet naming the guest."""
    from openai import OpenAI

    client = OpenAI(api_key=OPENROUTER_API_KEY, base_url=OPENROUTER_BASE_URL)
    where = f" at {company}" if company else ""
    prompt = (
        f"Write one artful RHYMING couplet: exactly two lines that clearly rhyme, "
        f"celebrating {name}{where}. The audience are leaders in tech and talent "
        f"(recruiters, VPs of Engineering, hiring leaders), so make it about how "
        f"they shape technology, teams, and talent. Include the first name "
        f"'{name}' in the couplet. Keep each line short (about 6 to 8 words) so it "
        f"fits a narrow strip. Evocative and classy, never cheesy or corporate. Do "
        f"NOT use em dashes. Return ONLY the two lines, each on its own line, with "
        f"no title, numbering, or quotes."
    )
    resp = client.chat.completions.create(
        model=OPENROUTER_MODEL,
        messages=[{"role": "user", "content": prompt}],
        max_tokens=70,
        temperature=0.9,
    )
    text = resp.choices[0].message.content.strip()
    lines = [ln.strip().strip('"').replace("—", ",") for ln in text.splitlines() if ln.strip()]
    if len(lines) >= 2:
        return lines[:2]
    raise ValueError("couplet too short")


def make_couplet(name: str | None, company: str | None = None) -> list[str]:
    """Return a 2-line rhyming couplet that names the guest. Never raises."""
    first = (name or "Friend").strip().split()[0] if name else "Friend"
    if OPENROUTER_API_KEY:
        try:
            print("[verse] generating via OpenRouter:", OPENROUTER_MODEL)
            return _llm_verse(first, company)
        except Exception as exc:  # noqa: BLE001 - fall back gracefully
            print("[verse] OpenRouter failed, using template:", exc)
    return [ln.format(name=first) for ln in random.choice(_TEMPLATES)]

