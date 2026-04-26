from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from .paths import LibraryPaths

_PERCENT_RE = re.compile(r"(\d{1,3})%\|")


def estimate_stage_progress(library: LibraryPaths, song_id: str, stage: str, state: str) -> int:
    if state == "completed":
        return 100
    if state in {"failed", "canceled"}:
        return 0
    if state == "queued":
        return 0
    if stage == "separate":
        return demucs_log_progress(library.stage_log(song_id, "separate"))
    return 50 if state == "running" else 0


def demucs_log_progress(log_path: Path) -> int:
    if not log_path.exists():
        return 5
    text = log_path.read_text(encoding="utf-8", errors="replace")[-20000:]
    matches = _PERCENT_RE.findall(text)
    if not matches:
        return 5
    return max(0, min(99, int(matches[-1])))


def annotate_jobs_with_progress(library: LibraryPaths, jobs: list[dict[str, Any]]) -> list[dict[str, Any]]:
    annotated: list[dict[str, Any]] = []
    for job in jobs:
        clone = dict(job)
        state = str(clone.get("state") or "")
        stage = str(clone.get("stage") or "")
        song_id = str(clone.get("song_id") or "")
        clone["progress"] = estimate_stage_progress(library, song_id, stage, state)
        annotated.append(clone)
    return annotated
