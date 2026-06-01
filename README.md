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

## Roadmap

- **Phase 1 — Backend pipeline** ✅
- Phase 2 — Frontend HTML page (5 screens), wired to `/generate`
- Phase 3 — Full README (https/ngrok setup, costs)
- Phase 4 — Print-ready 2×6" strip (two variations + poem block)
- Phase 5 — Face recognition against a ~50-person attendee DB
- Phase 6 — Personalized poem via LLM
- Phase 7 — DNP DS620A dye-sub strip printing
