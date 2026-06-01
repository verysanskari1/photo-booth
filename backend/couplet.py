"""
couplet.py — generate a short personalized 2-line couplet for the photo strip.

Primary path: OpenRouter (an OpenAI-compatible API gateway). Set OPENROUTER_API_KEY
and optionally OPENROUTER_MODEL. We use the official `openai` SDK pointed at
OpenRouter's base URL.

Fallback path: if there's no key (or the call fails), we use hand-written couplet
templates with the guest's name slotted in — so the booth always works offline.
"""

from __future__ import annotations

import os
import random

OPENROUTER_API_KEY = os.environ.get("OPENROUTER_API_KEY")
OPENROUTER_MODEL = os.environ.get("OPENROUTER_MODEL", "openai/gpt-4o-mini")
OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"

# Offline fallback couplets. {name} is filled in. Keep each to two short lines.
_TEMPLATES = [
    ["Here's to {name}, sharp and bold —", "an innovator's story told."],
    ["{name} shipped with heart and drive,", "watch the future come alive."],
    ["For {name}, who dares to build,", "with vision bright and purpose filled."],
    ["{name} codes a brighter day,", "and leads the bold, unbeaten way."],
    ["To {name} — relentless, true,", "the next big thing begins with you."],
]


def _llm_couplet(name: str, company: str | None) -> list[str]:
    """Ask an LLM (via OpenRouter) for a fresh couplet. Returns two lines."""
    from openai import OpenAI

    client = OpenAI(api_key=OPENROUTER_API_KEY, base_url=OPENROUTER_BASE_URL)
    who = name + (f" from {company}" if company else "")
    prompt = (
        f"Write a warm, classy, slightly witty 2-line rhyming couplet celebrating "
        f"{who} at a tech 'Innovator Awards' event. Mention the first name. Keep it "
        f"under 18 words total, professional and uplifting. Return ONLY the two "
        f"lines, each on its own line, no quotes or extra text."
    )
    resp = client.chat.completions.create(
        model=OPENROUTER_MODEL,
        messages=[{"role": "user", "content": prompt}],
        max_tokens=80,
        temperature=0.9,
    )
    text = resp.choices[0].message.content.strip()
    lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
    # Be defensive: make sure we end up with exactly two lines.
    if len(lines) >= 2:
        return lines[:2]
    if len(lines) == 1:
        return [lines[0], ""]
    raise ValueError("empty couplet response")


def _template_couplet(name: str) -> list[str]:
    template = random.choice(_TEMPLATES)
    return [line.format(name=name) for line in template]


def make_couplet(name: str | None, company: str | None = None) -> list[str]:
    """Return a two-line couplet for `name`. Never raises."""
    name = (name or "Friend").strip().split()[0]  # first name, keeps couplets short
    if OPENROUTER_API_KEY:
        try:
            print("[couplet] generating via OpenRouter:", OPENROUTER_MODEL)
            return _llm_couplet(name, company)
        except Exception as exc:  # noqa: BLE001 - fall back gracefully
            print("[couplet] OpenRouter failed, using template:", exc)
    return _template_couplet(name)
