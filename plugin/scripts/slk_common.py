"""Shared helpers for the kit's scripts: numbers, JSON output, argument errors and safe text cells."""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
import tempfile
from pathlib import Path

DE_TAUSEND = re.compile(r"-?[1-9]\d{0,2}(\.\d{3})+(,\d+)?")
DE_KOMMA = re.compile(r"-?\d+,\d+")
PLAIN = re.compile(r"-?\d+(\.\d+)?")
CSV_FORMEL = ("=", "+", "-", "@")


def zahl(v) -> float:
    """German (1.234,56) or plain (1234.56) number; a trailing minus (SAP credit notes) makes it negative."""
    if isinstance(v, bool) or v is None:
        raise ValueError(v)
    if isinstance(v, (int, float)):
        return float(v)
    s = str(v)
    for junk in ("€", "EUR", " ", " ", " "):
        s = s.replace(junk, "")
    if len(s) > 1 and s.endswith("-"):
        s = "-" + s[:-1]
    if DE_TAUSEND.fullmatch(s) or DE_KOMMA.fullmatch(s):
        return float(s.replace(".", "").replace(",", "."))
    if PLAIN.fullmatch(s):
        return float(s)
    raise ValueError(v)


def ausgabe(obj: dict) -> None:
    """Prints exactly one JSON object as UTF-8, whatever the console code page is (Windows: cp1252)."""
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except (AttributeError, ValueError):
        pass
    print(json.dumps(obj, ensure_ascii=False, default=str))


class JsonParser(argparse.ArgumentParser):
    """Argument errors become a JSON object with exit code 1 instead of usage text on stderr."""

    def error(self, message: str):
        ausgabe({"ok": False, "fehler": [f"Aufruf fehlerhaft: {message}"], "meldungen": [f"Aufruf fehlerhaft: {message}"]})
        raise SystemExit(1)


def run(fn, argv) -> int:
    """Runs fn(argv) -> (exit_code, dict); any unexpected exception still yields one German JSON object."""
    try:
        code, out = fn(argv)
    except SystemExit as exc:
        return int(exc.code or 0)
    except Exception as exc:  # last line of defence: the calling skill must always get JSON
        text = f"Unerwarteter Fehler ({type(exc).__name__}): {exc}"
        code, out = 1, {"ok": False, "fehler": [text], "meldungen": [text]}
    ausgabe(out)
    return code


def write_atomic(path: Path, text: str, encoding: str = "utf-8") -> None:
    """Whole-file write through a unique temp file in the same folder, then os.replace."""
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=path.parent, prefix=f".{path.name}.", suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding=encoding, newline="\n") as fh:
            fh.write(text)
        os.replace(tmp, path)
    except BaseException:
        Path(tmp).unlink(missing_ok=True)
        raise


def csv_sicher(v):
    """Text that Excel would evaluate as a formula gets a leading apostrophe (CSV injection)."""
    if isinstance(v, str) and v.startswith(CSV_FORMEL):
        return "'" + v
    return v
