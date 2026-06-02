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

# Offline fallback rhyming couplets, tech / hiring / building themed.
_TEMPLATES = [
    ["We build in light, we ship through fire,", "each line of code lifts dreams up higher."],
    ["Through restless nights the bold ones came,", "to turn a spark of thought to flame."],
    ["The future hires the curious heart,", "where logic ends, the dreamers start."],
    ["In data's hum a quiet grace,", "where minds and machines keep pace."],
    ["From idle thought to shipping fast,", "the ones who dare are built to last."],
    ["Bright minds compose the world anew,", "and every bold idea breaks through."],
]


def _llm_verse(name: str, company: str | None) -> list[str]:
    """Ask an LLM (via OpenRouter) for a 2-line rhyming couplet."""
    from openai import OpenAI

    client = OpenAI(api_key=OPENROUTER_API_KEY, base_url=OPENROUTER_BASE_URL)
    who = name + (f", who works at {company}" if company else "")
    prompt = (
        "Write one artful RHYMING couplet: exactly two lines that clearly rhyme, "
        "about innovation, building great products, and brilliant people in tech "
        "and hiring. Make it evocative and a little poetic, never cheesy or "
        f"corporate. You may subtly nod to {who}, but keep it tasteful and "
        "optional. Do NOT use em dashes. Return ONLY the two lines, each on its "
        "own line, with no title, numbering, or quotes."
    )
    resp = client.chat.completions.create(
        model=OPENROUTER_MODEL,
        messages=[{"role": "user", "content": prompt}],
        max_tokens=70,
        temperature=0.95,
    )
    text = resp.choices[0].message.content.strip()
    lines = [ln.strip().strip('"').replace("—", ",") for ln in text.splitlines() if ln.strip()]
    if len(lines) >= 2:
        return lines[:2]
    raise ValueError("couplet too short")


def make_couplet(name: str | None, company: str | None = None) -> list[str]:
    """Return a 2-line rhyming couplet. Never raises."""
    first = (name or "Friend").strip().split()[0] if name else "Friend"
    if OPENROUTER_API_KEY:
        try:
            print("[verse] generating via OpenRouter:", OPENROUTER_MODEL)
            return _llm_verse(first, company)
        except Exception as exc:  # noqa: BLE001 - fall back gracefully
            print("[verse] OpenRouter failed, using template:", exc)
    return random.choice(_TEMPLATES)

