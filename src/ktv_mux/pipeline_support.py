from __future__ import annotations

import fcntl
import shutil
import threading
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from typing import Any

from .checkpoints import stage_checkpoint_completed
from .errors import PipelineStateError
from .jsonio import read_json
from .library import import_source
from .media import probe_media
from .models import Song, update_report, utc_now
from .output_templates import render_output_filename
from .paths import LibraryPaths, derive_song_id_from_source, normalize_song_id
from .settings import load_settings
from .versions import record_take

_LOCKS_GUARD = threading.Lock()
_SONG_LOCKS: dict[str, threading.Lock] = {}

def _probe_duration(path: Path) -> float:
    info = probe_media(path)
    return float(info.get("duration") or 0.0)

def _preview_starts(
    media_duration: Any,
    *,
    start: float,
    count: int,
    spacing: float,
    preset: str,
) -> list[float]:
    duration = float(media_duration or 0.0)
    base = max(0.0, float(start or 0.0))
    if preset == "chorus" and duration > 0:
        base = max(0.0, duration * 0.4)
    total = max(1, int(count or 1))
    gap = max(1.0, float(spacing or 45.0))
    starts = []
    for index in range(total):
        candidate = base + index * gap
        if duration > 0:
            candidate = min(candidate, max(0.0, duration - 1.0))
        starts.append(round(candidate, 3))
    return starts

def _stage_outputs(library: LibraryPaths, song_id: str, stage: str) -> list[Path]:
    if stage == "import":
        return library.source_candidates(song_id)
    if stage == "probe":
        return [library.report_json(song_id)]
    if stage == "extract":
        return [library.mix_wav(song_id)]
    if stage == "preview-tracks":
        return sorted(library.previews_dir(song_id).glob("track-*.wav"))
    if stage == "separate":
        return [library.instrumental_wav(song_id), library.vocals_wav(song_id)]
    if stage == "separate-sample":
        return [library.instrumental_sample_wav(song_id), library.vocals_sample_wav(song_id)]
    if stage == "set-instrumental":
        return [library.instrumental_wav(song_id)]
    if stage in {"track-role", "mux-plan", "replace-audio-plan"}:
        return [library.report_json(song_id)]
    if stage == "extract-subtitles":
        return [library.lyrics_txt(song_id), library.lyrics_ass(song_id)]
    if stage in {"align", "shift-subtitles", "shift-subtitle-lines", "stretch-subtitle-lines", "edit-subtitles"}:
        return [library.alignment_json(song_id), library.lyrics_ass(song_id)]
    if stage == "mux":
        return [library.final_mkv(song_id)]
    if stage == "replace-audio":
        return [library.audio_replaced_mkv(song_id)]
    if stage == "normalize":
        return [library.normalized_instrumental_wav(song_id)]
    return []

def _ass_style(library: LibraryPaths) -> dict[str, Any]:
    settings = load_settings(library)
    return {
        "font_size": settings["subtitle_font_size"],
        "margin_v": settings["subtitle_margin_v"],
        "primary_colour": settings["subtitle_primary_colour"],
        "secondary_colour": settings["subtitle_secondary_colour"],
    }

def _checkpoint_has_outputs(library: LibraryPaths, song_id: str, stage: str) -> bool:
    return stage_checkpoint_completed(library, song_id, stage)

def _optional_int(value: Any) -> int | None:
    if value in {None, ""}:
        return None
    parsed = int(value)
    return parsed if parsed > 0 else None

def _optional_float(value: Any) -> float | None:
    if value in {None, ""}:
        return None
    parsed = float(value)
    return parsed if parsed > 0 else None

def _import_and_report(
    library: LibraryPaths,
    path_or_url: str,
    *,
    song_id: str | None,
    title: str | None,
    artist: str | None,
    cancel_file: Path | None,
) -> Song:
    clean_id = normalize_song_id(song_id) if song_id else derive_song_id_from_source(path_or_url)
    song = import_source(
        path_or_url,
        song_id=song_id,
        library=library,
        title=title,
        artist=artist,
        log_path=library.stage_log(clean_id, "import"),
        cancel_file=cancel_file,
    )
    update_report(
        library.report_json(song.song_id),
        imported_source=str(song.source_path),
        import_input=path_or_url,
        download_metadata=_download_metadata(library, song.song_id),
    )
    return song

def _download_metadata(library: LibraryPaths, song_id: str) -> dict[str, Any] | None:
    for path in sorted(library.raw_dir(song_id).glob("source*.info.json")):
        data = read_json(path, default={})
        if not isinstance(data, dict):
            continue
        return {
            key: data.get(key)
            for key in ["id", "title", "uploader", "channel", "webpage_url", "duration", "extractor"]
            if data.get(key) is not None
        }
    return None

def _validate_audio_index(source: Path, audio_index: int) -> None:
    if audio_index < 0:
        raise PipelineStateError("Audio track index must be 0 or greater.")
    info = probe_media(source)
    count = len(info["audio_streams"])
    if audio_index >= count:
        raise PipelineStateError(
            f"Audio Track {audio_index + 1} does not exist. This source has {count} audio track(s)."
        )

def _validate_probe_has_required_streams(info: dict[str, Any]) -> None:
    if not info["video_streams"]:
        raise PipelineStateError("Source media has no video stream.")
    if not info["audio_streams"]:
        raise PipelineStateError("Source media has no audio stream.")

def _archive_take(library: LibraryPaths, song_id: str, path: Path, *, label: str = "") -> Path:
    if not path.exists():
        return path
    stamp = utc_now().replace("+00:00", "Z").replace(":", "").replace("-", "")
    take = library.takes_dir(song_id) / f"{path.stem}.{stamp}{path.suffix}"
    take.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(path, take)
    record_take(library, song_id, take, label=label)
    return take

def _copy_templated_output(library: LibraryPaths, song_id: str, path: Path, *, kind: str) -> Path | None:
    settings = load_settings(library)
    filename = render_output_filename(
        str(settings.get("output_template") or "{song_id}.ktv.mkv"),
        {"song_id": song_id, "kind": kind},
        suffix=path.suffix,
    )
    target = library.output_dir(song_id) / filename
    if target == path:
        return None
    shutil.copy2(path, target)
    return target

@contextmanager
def song_lock(library: LibraryPaths, song_id: str) -> Iterator[None]:
    path = library.lock_file(song_id)
    path.parent.mkdir(parents=True, exist_ok=True)
    inprocess = _inprocess_song_lock(song_id)
    with inprocess:
        with path.open("w", encoding="utf-8") as handle:
            fcntl.flock(handle, fcntl.LOCK_EX)
            try:
                yield
            finally:
                fcntl.flock(handle, fcntl.LOCK_UN)

def _inprocess_song_lock(song_id: str) -> threading.Lock:
    clean_id = normalize_song_id(song_id)
    with _LOCKS_GUARD:
        lock = _SONG_LOCKS.get(clean_id)
        if lock is None:
            lock = threading.Lock()
            _SONG_LOCKS[clean_id] = lock
        return lock
