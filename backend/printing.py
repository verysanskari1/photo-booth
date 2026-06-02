"""
printing.py — send the finished strip to a printer via CUPS (macOS / Linux).

On the booth Mac the DS620A shows up as a normal print queue, so we shell out to
`lp`. Everything is configurable via env so you don't touch code at the venue:

    PRINTER_NAME    the CUPS queue name (from `lpstat -p`). Empty = default printer.
    PRINT_MEDIA     media/PageSize for the queue (from `lpoptions -p NAME -l`),
                    e.g. a DS620A "2x6" / "(6x4) 2 strips" PageSize. Empty = queue default.
    PRINT_OPTIONS   any extra raw `-o key=value` options, space separated.
    PRINT_COPIES    number of copies (default 1).
    PRINT_ENABLED   set to 0 to disable real printing (frontend falls back to the
                    browser print dialog).

Discover your setup once at the booth:
    lpstat -p                      # list queue names
    lpoptions -p <NAME> -l         # list media / PageSize choices for the DS620A
"""

from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path

PRINTER_NAME = os.environ.get("PRINTER_NAME", "").strip()
PRINT_MEDIA = os.environ.get("PRINT_MEDIA", "").strip()
PRINT_OPTIONS = os.environ.get("PRINT_OPTIONS", "").strip()
PRINT_COPIES = os.environ.get("PRINT_COPIES", "1").strip()
PRINT_ENABLED = os.environ.get("PRINT_ENABLED", "1").lower() not in ("0", "false", "no")


def lp_available() -> bool:
    return shutil.which("lp") is not None


def list_printers() -> dict:
    """Return {default, printers, lp_available, enabled} for diagnostics."""
    info = {
        "lp_available": lp_available(),
        "enabled": PRINT_ENABLED,
        "configured": PRINTER_NAME or "(system default)",
        "printers": [],
        "default": "",
    }
    if shutil.which("lpstat"):
        out = subprocess.run(["lpstat", "-p"], capture_output=True, text=True)
        for line in out.stdout.splitlines():
            if line.startswith("printer "):
                info["printers"].append(line.split()[1])
        d = subprocess.run(["lpstat", "-d"], capture_output=True, text=True)
        # "system default destination: NAME"
        if ":" in d.stdout:
            info["default"] = d.stdout.split(":", 1)[1].strip()
    return info


def print_image(path: str | Path) -> str:
    """Send `path` to the printer via lp. Returns the lp job id string, or raises."""
    path = Path(path)
    if not PRINT_ENABLED:
        raise RuntimeError("Printing is disabled (PRINT_ENABLED=0).")
    if not lp_available():
        raise RuntimeError("`lp` not found. CUPS is built in on macOS; install cups on Linux.")
    if not path.exists():
        raise RuntimeError(f"file not found: {path}")

    cmd = ["lp"]
    if PRINTER_NAME:
        cmd += ["-d", PRINTER_NAME]
    if PRINT_COPIES and PRINT_COPIES != "1":
        cmd += ["-n", PRINT_COPIES]
    if PRINT_MEDIA:
        cmd += ["-o", f"media={PRINT_MEDIA}"]
    cmd += ["-o", "fit-to-page"]
    if PRINT_OPTIONS:
        cmd += PRINT_OPTIONS.split()
    cmd += [str(path)]

    print("[print] running:", " ".join(cmd))
    res = subprocess.run(cmd, capture_output=True, text=True)
    if res.returncode != 0:
        raise RuntimeError(res.stderr.strip() or "lp failed")
    return res.stdout.strip()  # e.g. "request id is DS620A-42 (1 file(s))"
