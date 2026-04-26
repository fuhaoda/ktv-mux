from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from .paths import normalize_song_id

_TOKEN_RE = re.compile(r"\{([a-zA-Z_][a-zA-Z0-9_]*)\}")


def render_output_filename(template: str, song: dict[str, Any] | None = None, *, suffix: str = ".mkv") -> str:
    song = song or {}
    values = {
        "song_id": normalize_song_id(str(song.get("song_id") or "song")),
        "title": _safe_part(str(song.get("title") or song.get("song_id") or "song")),
        "artist": _safe_part(str(song.get("artist") or "unknown")),
        "kind": _safe_part(str(song.get("kind") or "ktv")),
    }
    pattern = template.strip() or "{song_id}.ktv.mkv"

    def replace(match: re.Match[str]) -> str:
        return values.get(match.group(1), match.group(0))

    filename = _TOKEN_RE.sub(replace, pattern)
    filename = Path(filename).name
    if not filename.lower().endswith(suffix.lower()):
        filename += suffix
    return filename


def _safe_part(value: str) -> str:
    return normalize_song_id(value) if value.strip() else "unknown"
