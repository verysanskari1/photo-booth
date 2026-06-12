"""
faces.py — face recognition against a small attendee database (Phase 5).

Runs on the BACKEND (not the iPad). Uses InsightFace (buffalo_l) to compute a
512-d face embedding for the captured photo and matches it, by cosine
similarity, against embeddings built from the attendee reference photos.

Attendee database format (see backend/attendees/):
    backend/attendees/attendees.csv   columns: image,name,company
    backend/attendees/<image files>   one reference headshot per person

Everything degrades gracefully: if InsightFace isn't installed, or the DB is
empty, identify() just returns "no match" and the frontend falls back to the
guest typing their name on the confirm screen.
"""

from __future__ import annotations

import csv
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parent
ATTENDEES_DIR = BACKEND_DIR / "attendees"
ATTENDEES_CSV = ATTENDEES_DIR / "attendees.csv"

# Cosine-similarity threshold for treating a face as a confident match.
# buffalo_l: ~0.30 loose, ~0.45 confident. Below this we ask the guest to confirm.
MATCH_THRESHOLD = 0.42

_app = None            # lazily-initialised InsightFace model
_db: list[dict] = []   # [{name, company, embedding(np.ndarray)}]
_loaded = False


def ensure_loaded():
    """Public warm-up: build the model + attendee index now (e.g. at startup)."""
    _try_init()


def _try_init():
    """Load the model + attendee embeddings once. Safe to call repeatedly."""
    global _app, _db, _loaded
    if _loaded:
        return
    _loaded = True
    try:
        import numpy as np  # noqa: F401
        from insightface.app import FaceAnalysis
    except Exception as exc:  # noqa: BLE001
        print("[faces] InsightFace not available — recognition disabled:", exc)
        return

    try:
        app = FaceAnalysis(name="buffalo_l", providers=["CPUExecutionProvider"])
        app.prepare(ctx_id=-1, det_size=(640, 640))
        _app = app
    except Exception as exc:  # noqa: BLE001
        print("[faces] could not start InsightFace model:", exc)
        return

    _load_db()


def _embed(image_path_or_pil):
    """Return the normalized embedding of the largest face, or None."""
    import numpy as np
    from PIL import Image

    if isinstance(image_path_or_pil, (str, Path)):
        img = Image.open(image_path_or_pil)
    else:
        img = image_path_or_pil
    img = img.convert("RGB")
    bgr = np.array(img)[:, :, ::-1]  # RGB -> BGR for InsightFace
    faces = _app.get(bgr)
    if not faces:
        return None
    # Pick the largest detected face.
    faces.sort(key=lambda f: (f.bbox[2] - f.bbox[0]) * (f.bbox[3] - f.bbox[1]), reverse=True)
    return faces[0].normed_embedding


def _load_db():
    global _db
    _db = []
    if not ATTENDEES_CSV.exists():
        print("[faces] no attendees.csv found; recognition will return no match.")
        return
    with open(ATTENDEES_CSV, newline="") as fh:
        for row in csv.DictReader(fh):
            img = ATTENDEES_DIR / row["image"].strip()
            if not img.exists():
                print(f"[faces] skipping missing reference image: {img}")
                continue
            emb = _embed(img)
            if emb is None:
                print(f"[faces] no face found in reference image: {img}")
                continue
            _db.append({
                "name": row.get("name", "").strip(),
                "company": row.get("company", "").strip(),
                "embedding": emb,
            })
    print(f"[faces] loaded {len(_db)} attendee reference face(s).")


def identify(image_path_or_pil) -> dict:
    """Identify the face in the captured photo.

    Returns {"name", "company", "confidence", "matched"}. `matched` is True only
    when confidence >= MATCH_THRESHOLD. Always safe to call.
    """
    _try_init()
    result = {"name": "", "company": "", "confidence": 0.0, "matched": False}
    if _app is None or not _db:
        return result

    import numpy as np

    emb = _embed(image_path_or_pil)
    if emb is None:
        return result

    best, best_score = None, -1.0
    for entry in _db:
        score = float(np.dot(emb, entry["embedding"]))  # cosine (both normalized)
        if score > best_score:
            best, best_score = entry, score

    result["confidence"] = round(best_score, 3)
    if best and best_score >= MATCH_THRESHOLD:
        result.update(name=best["name"], company=best["company"], matched=True)
    return result
