# Innovator Awards Photobooth

An event photo booth: a guest taps a button on an iPad, the app captures their
photo, turns it into a purple ASCII-halftone portrait with AI, places it on a
branded Innovator Awards backdrop, and shows/prints the result.

- **Frontend** — a single HTML page for iPad Chrome (camera + UI). Holds no secrets.
- **Backend** — a small FastAPI server that holds the fal.ai key and runs the
  image pipeline. The frontend POSTs the photo and gets back a result URL.

This is being built in phases. **Phase 1 (backend pipeline) is done** — see below.
The full setup guide lands in Phase 3.

---

## Phase 1 — Backend quickstart (test it now)

The backend runs a 3-step pipeline per photo:

1. **Stylize** → `fal-ai/nano-banana-2/edit` (purple ASCII-halftone portrait, ~$0.08)
2. **Remove background** → `fal-ai/birefnet/v2` (transparent cutout)
3. **Composite** → local Pillow paste onto `my_background.png` (no API cost)

### Setup

```bash
cd backend
python3 -m venv .venv && source .venv/bin/activate   # optional but recommended
pip install -r requirements.txt

# Your fal.ai API key (https://fal.ai/dashboard/keys)
export FAL_KEY="your-fal-key-here"

# Generate the default branded backdrop (or drop in your own my_background.png)
python generate_background.py
```

### Try the pipeline on a local image (no frontend, no iPad)

```bash
python app.py --test /path/to/a/portrait.jpg
# writes outputs/test_result.png — open it to see the composited result
```

### Run the web server (what the frontend talks to)

```bash
# PUBLIC_HOST is the URL the browser will use to fetch finished images.
# For local testing the default (http://localhost:8000) is fine.
export PUBLIC_HOST="http://localhost:8000"
uvicorn app:app --host 0.0.0.0 --port 8000
```

- Health check: open <http://localhost:8000/> → `{"status":"ok",...}`
- The endpoint: `POST /generate` with multipart form field `photo` →
  returns `{"image_url": "..."}`.

Quick curl test against a running server:

```bash
curl -F "photo=@/path/to/portrait.jpg" http://localhost:8000/generate
```

### Files

```
backend/
  app.py                  FastAPI server + CLI test mode (--test)
  pipeline.py             the 3-step image pipeline (reused by server + CLI)
  generate_background.py  builds the default branded my_background.png
  my_background.png       the fixed backdrop everyone is composited onto
  requirements.txt
```

> Cost note: each portrait makes 2 paid fal calls (~$0.08 stylize + birefnet).
> Roughly **$8 for ~50 guests** at one portrait each. Full breakdown in Phase 3.

---

## Photo strip + face recognition + couplet (Phases 4–6)

The booth can now produce a **2×6" photo strip**: two stylized poses (top +
bottom) with a personalized **couplet + name** in the middle. The name is filled
in by **face recognition** against your attendee list, and the guest confirms/edits
it on screen before the strip is built.

### Frontend flow
camera → confirm shot → **confirm name** (pre-filled if recognized) → strip result.

### Extra env vars (all optional — each piece degrades gracefully)

```bash
# Couplet via OpenRouter (OpenAI-compatible). Without it, hand-written template
# couplets are used instead.
export OPENROUTER_API_KEY="sk-or-..."
export OPENROUTER_MODEL="openai/gpt-4o-mini"   # any OpenRouter model id
```

### Face recognition (runs on the backend, not the iPad)

Uses **InsightFace** locally — no per-call cost, faces never leave your machine.
Install pulls in `insightface onnxruntime numpy` (already in requirements.txt; the
model downloads once on first run).

Attendee database lives in `backend/attendees/` — see
`backend/attendees/README.md`. It ships with 3 placeholder rows so the flow works
immediately; drop in one reference headshot per real attendee + edit
`attendees.csv` (`image,name,company`), then **restart the backend**. If
InsightFace isn't installed or no face matches, the guest just types their name.

### Custom strip artwork (optional)

By default the strip is drawn with a clean built-in design. To use your own full
artwork, drop a **`backend/strip_template.png`** (fit to 600×1800). The booth uses
it as the base and only pastes the two photos + verse into these regions, so
leave them clear in your design (coordinates in `strip.py`):

- top photo:    x0 y170, 600×600
- verse block:  x40 y770, 520×300  (light text + neon name drawn here)
- bottom photo: x0 y1070, 600×600

### Fonts (Kalice + Satoshi)

Drop `Kalice.ttf` and `Satoshi.ttf` (and `Satoshi-Bold.ttf`) into
**`frontend/fonts/`**. The web page loads them via `@font-face`, and the strip
generator picks them up from the same folder. Without them, system serif/sans
fallbacks are used.

### The verse

A short artful **haiku** (3 lines) themed around tech / building / hiring, with
the guest's name shown as an attribution beneath it. Tune the wording in
`couplet.py` (LLM prompt + offline templates).

### New endpoints
- `POST /identify` (photo) → `{name, company, confidence, matched}`
- `POST /generate_strip` (photo, name, company) → `{image_url, name, couplet}`

### Cost note (updated)
The strip runs stylize **twice** per guest (two poses) + two background removals,
so ~**$0.16+/guest** in fal calls → roughly **$8–10 for ~50 guests**. The couplet
LLM call is fractions of a cent (or free with templates).

---

## Running it the easy way (no re-typing env vars)

1. Copy `backend/.env.example` to `backend/.env` and fill in your keys once.
2. Then just:

```bash
cd backend
./start.sh
```

`start.sh` creates the venv (first run), installs deps, loads `.env`, and starts
the server on http://localhost:8000. No `export` or `source` needed each time.

## Hosting it for the event (and "do I need a laptop?")

**Recommendation: yes, run it on one laptop at the venue (connected to the
printer), exposed via ngrok.** The deciding factor is the **DS620A dye-sub
printer** — it's USB and must be physically attached to a computer at the event,
so a computer has to be there regardless. Since that machine is already present,
run everything on it; cloud hosting would only add a second moving part for no
benefit at this scale.

```
[iPad: Chrome] --https via ngrok--> [Laptop at booth: ./start.sh]
                                      ├─ fal.ai          (needs internet)
                                      ├─ face recognition (local, InsightFace)
                                      ├─ strip generation (local)
                                      └─ DS620A printer   (USB, local)
```

Event-day runbook:
1. Use a **Mac** at the booth if possible (best DS620A drivers + clean printing).
2. `cd backend && ./start.sh` (keys already in `.env`).
3. `ngrok http 8000` → copy the https URL.
4. Put that URL in `.env` as `PUBLIC_HOST`, restart `start.sh`.
5. Open the ngrok https URL in **iPad Chrome**. Camera works because it's https.
6. **Internet is the only hard dependency** (fal + couplet). Bring a **phone
   hotspot** as backup; venue wifi is the usual point of failure.
7. Pre-warm before doors open: take one test photo so the InsightFace model is
   already downloaded/loaded and the first guest isn't slow.

> Prefer no laptop at all? You can cloud-host the backend (a `Dockerfile` is
> included; use a box with ≥2 GB RAM), but you'd still need a local machine for
> the printer, so it's not worth it for a single event.

### Exposing over https (camera needs https or localhost)

For a quick tunnel during testing or a laptop-at-venue setup:

```bash
# install ngrok, then:
ngrok http 8000
```

Set `PUBLIC_HOST` in `.env` to the https URL ngrok prints, and set
`BACKEND_URL` in `frontend/index.html` to the same URL **if** the frontend is
served from somewhere else. (When the backend serves the page — the default —
they're same-origin and you can leave `BACKEND_URL` empty.)

---

## Roadmap

- **Phase 1 — Backend pipeline** ✅
- **Phase 2 — Frontend (camera + screens)** ✅
- **Phase 4 — Print-ready 2×6" strip (two poses + couplet block)** ✅
- **Phase 5 — Face recognition against attendee DB** ✅
- **Phase 6 — Personalized couplet via LLM (OpenRouter)** ✅
- **Phase 3 — Easy-run (.env + start.sh), https/ngrok + hosting notes** ✅
- Phase 7 — DNP DS620A dye-sub strip printing (send the strip to the printer)
