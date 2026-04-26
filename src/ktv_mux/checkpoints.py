from __future__ import annotations

from pathlib import Path
from typing import Any

from .jsonio import read_json, write_json
from .models import utc_now
from .paths import LibraryPaths, normalize_song_id


def record_stage_checkpoint(
    library: LibraryPaths,
    song_id: str,
    stage: str,
    *,
    state: str,
    outputs: list[Path] | None = None,
    message: str = "",
) -> None:
    clean_id = normalize_song_id(song_id)
    data = read_json(library.checkpoints_json(clean_id), default={}) or {}
    data[stage] = {
        "state": state,
        "outputs": [str(path) for path in outputs or []],
        "message": message,
        "updated_at": utc_now(),
    }
    write_json(library.checkpoints_json(clean_id), data)


def stage_checkpoint(library: LibraryPaths, song_id: str, stage: str) -> dict[str, Any]:
    data = read_json(library.checkpoints_json(song_id), default={}) or {}
    checkpoint = data.get(stage) or {}
    return checkpoint if isinstance(checkpoint, dict) else {}


def stage_checkpoint_completed(library: LibraryPaths, song_id: str, stage: str) -> bool:
    checkpoint = stage_checkpoint(library, song_id, stage)
    if checkpoint.get("state") != "completed":
        return False
    outputs = checkpoint.get("outputs") or []
    return all(Path(path).exists() for path in outputs)
