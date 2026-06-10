"""
delivery.py — drop each finished strip into a "drive" folder for remote printing.

The simplest, most reliable pipeline for a printer that lives somewhere else:
point DRIVE_FOLDER at a local folder that Google Drive for Desktop (or Dropbox /
OneDrive) keeps synced. We copy each finished strip there; it syncs to the cloud
automatically, and the remote print station prints from that same folder.

    DRIVE_FOLDER   absolute path to the synced folder (empty = delivery off).

No API keys, no credentials — it's just a file copy into a synced directory.
"""

from __future__ import annotations

import os
import re
import shutil
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parent
DRIVE_FOLDER = os.environ.get("DRIVE_FOLDER", "").strip()
_COUNTER_FILE = BACKEND_DIR / "delivery_counter.txt"


def enabled() -> bool:
    return bool(DRIVE_FOLDER)


def _next_seq() -> int:
    """Monotonic delivery number, persisted so it survives restarts."""
    n = 0
    try:
        n = int(_COUNTER_FILE.read_text().strip())
    except Exception:  # noqa: BLE001
        n = 0
    n += 1
    try:
        _COUNTER_FILE.write_text(str(n))
    except Exception:  # noqa: BLE001
        pass
    return n


def _clean(s: str) -> str:
    """Make a string safe for a filename while staying readable."""
    s = re.sub(r'[\\/:*?"<>|]+', " ", s or "").strip()
    return re.sub(r"\s+", " ", s)


def deliver(src_path: str | Path, name: str = "", company: str = "") -> str | None:
    """Copy the strip into the synced folder named '<N> - Name - Company.png'.

    The running number makes the files easy to sort, search, and reprint.
    Returns the destination path, or None if DRIVE_FOLDER isn't configured.
    """
    if not DRIVE_FOLDER:
        return None

    dest_dir = Path(DRIVE_FOLDER).expanduser()
    dest_dir.mkdir(parents=True, exist_ok=True)

    n = _next_seq()
    nm = _clean(name) or "Guest"
    co = _clean(company)
    label = f"{n} - {nm} - {co}" if co else f"{n} - {nm}"
    dest = dest_dir / f"{label}.png"

    shutil.copy2(src_path, dest)
    print("[delivery] copied strip to drive folder:", dest)
    return str(dest)
