from __future__ import annotations

import fcntl
import shutil
import threading
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from pathlib import Path
from time import perf_counter
from typing import Any

from .alignment import align_lyrics, shift_alignment, shift_alignment_lines, update_alignment_lines
from .ass import build_ass
from .checkpoints import record_stage_checkpoint
from .errors import PipelineStateError
from .jsonio import read_json, write_json
from .library import import_source, load_song, save_lyrics_file
from .media import (
    extract_mix,
    extract_preview,
    mux_ktv,
    normalize_wav,
    probe_media,
    replace_audio_track,
    run_demucs_two_stems,
)
from .models import Song, append_stage_status, update_report, utc_now
from .paths import LibraryPaths, derive_song_id_from_source, normalize_song_id
from .quality import separation_quality_report
from .versions import record_take

StageFunc = Callable[[], Any]
_LOCKS_GUARD = threading.Lock()
_SONG_LOCKS: dict[str, threading.Lock] = {}


class Pipeline:
    def __init__(self, library: LibraryPaths | None = None) -> None:
        self.library = library or LibraryPaths()

    def import_source(
        self,
        path_or_url: str,
        *,
        song_id: str | None = None,
        title: str | None = None,
        artist: str | None = None,
        cancel_file: Path | None = None,
    ) -> Song:
        stage_id = song_id or derive_song_id_from_source(path_or_url)
        return self._run_stage(
            stage_id,
            "import",
            lambda: _import_and_report(
                self.library,
                path_or_url,
                song_id=song_id,
                title=title,
                artist=artist,
                cancel_file=cancel_file,
            ),
        )

    def set_lyrics(self, song_id: str, lyrics_path: Path) -> Path:
        return self._run_stage(
            song_id,
            "lyrics",
            lambda: save_lyrics_file(self.library, song_id, lyrics_path),
        )

    def probe(self, song_id: str) -> dict[str, Any]:
        clean_id = normalize_song_id(song_id)
        source = self.library.source_path(clean_id)

        def stage() -> dict[str, Any]:
            info = probe_media(source)
            _validate_probe_has_required_streams(info)
            update_report(
                self.library.report_json(clean_id),
                source=str(source),
                probe={
                    "duration": info["duration"],
                    "video_streams": len(info["video_streams"]),
                    "audio_streams": len(info["audio_streams"]),
                    "subtitle_streams": len(info["subtitle_streams"]),
                    "format": info["format"],
                    "streams": info["streams"],
                },
            )
            return info

        return self._run_stage(clean_id, "probe", stage)

    def extract(self, song_id: str, *, audio_index: int = 0, cancel_file: Path | None = None) -> Path:
        clean_id = normalize_song_id(song_id)
        source = self.library.source_path(clean_id)
        mix = self.library.mix_wav(clean_id)

        def stage() -> Path:
            _validate_audio_index(source, audio_index)
            result = extract_mix(source, mix, audio_index=audio_index, cancel_file=cancel_file)
            update_report(
                self.library.report_json(clean_id),
                mix_wav=str(result),
                selected_audio_index=audio_index,
                selected_audio_track=audio_index + 1,
            )
            return result

        return self._run_stage(clean_id, "extract", stage)

    def preview_tracks(
        self,
        song_id: str,
        *,
        duration: float = 20.0,
        start: float = 0.0,
        count: int = 1,
        spacing: float = 45.0,
        preset: str = "manual",
        cancel_file: Path | None = None,
    ) -> dict[str, Any]:
        clean_id = normalize_song_id(song_id)
        source = self.library.source_path(clean_id)

        def stage() -> dict[str, Any]:
            info = probe_media(source)
            _validate_probe_has_required_streams(info)
            previews = []
            starts = _preview_starts(info.get("duration"), start=start, count=count, spacing=spacing, preset=preset)
            for audio_index, stream in enumerate(info["audio_streams"]):
                for segment_index, segment_start in enumerate(starts):
                    out = self.library.track_preview_wav(clean_id, audio_index, segment_index)
                    extract_preview(
                        source,
                        out,
                        audio_index=audio_index,
                        duration=duration,
                        start=segment_start,
                        cancel_file=cancel_file,
                    )
                    previews.append(
                        {
                            "audio_index": audio_index,
                            "track": audio_index + 1,
                            "segment": segment_index + 1,
                            "path": str(out),
                            "start": segment_start,
                            "duration": duration,
                            "codec": stream.get("codec_name"),
                            "language": (stream.get("tags") or {}).get("language"),
                        }
                    )
            update_report(
                self.library.report_json(clean_id),
                probe={
                    "duration": info["duration"],
                    "video_streams": len(info["video_streams"]),
                    "audio_streams": len(info["audio_streams"]),
                    "subtitle_streams": len(info["subtitle_streams"]),
                    "format": info["format"],
                    "streams": info["streams"],
                },
                track_previews=previews,
            )
            return {"track_previews": previews}

        return self._run_stage(clean_id, "preview-tracks", stage)

    def separate(
        self,
        song_id: str,
        *,
        model: str = "htdemucs",
        device: str | None = None,
        cancel_file: Path | None = None,
    ) -> dict[str, Any]:
        clean_id = normalize_song_id(song_id)
        mix = self._require_file(self.library.mix_wav(clean_id), "Run extract before separate.")

        def stage() -> dict[str, Any]:
            result = run_demucs_two_stems(
                mix,
                self.library.work_dir(clean_id),
                self.library.instrumental_wav(clean_id),
                self.library.vocals_wav(clean_id),
                model=model,
                device=device,
                log_path=self.library.stage_log(clean_id, "separate"),
                cancel_file=cancel_file,
            )
            update_report(
                self.library.report_json(clean_id),
                separation=result,
                quality=separation_quality_report(
                    mix_wav=mix,
                    instrumental_wav=self.library.instrumental_wav(clean_id),
                    vocals_wav=self.library.vocals_wav(clean_id),
                ),
                instrumental_take=str(
                    _archive_take(
                        self.library,
                        clean_id,
                        self.library.instrumental_wav(clean_id),
                        label=f"{result.get('model')} / {result.get('requested_device')}",
                    )
                ),
            )
            return result

        return self._run_stage(clean_id, "separate", stage)

    def align(self, song_id: str, *, backend: str = "auto") -> dict[str, Any]:
        clean_id = normalize_song_id(song_id)
        lyrics = self._require_file(self.library.lyrics_txt(clean_id), "Add lyrics.txt before align.")
        source = self.library.source_path(clean_id)
        audio = self.library.vocals_wav(clean_id)
        if not audio.exists():
            audio = self.library.mix_wav(clean_id)
        audio = self._require_file(audio, "Run extract before align.")

        def stage() -> dict[str, Any]:
            duration = _probe_duration(source)
            alignment = align_lyrics(audio, lyrics, duration=duration, backend=backend)
            write_json(self.library.alignment_json(clean_id), alignment)
            ass_text = build_ass(alignment, title=clean_id)
            self.library.lyrics_ass(clean_id).parent.mkdir(parents=True, exist_ok=True)
            self.library.lyrics_ass(clean_id).write_text(ass_text, encoding="utf-8")
            update_report(
                self.library.report_json(clean_id),
                alignment={
                    "backend": alignment.get("backend"),
                    "warning": alignment.get("warning"),
                    "alignment_json": str(self.library.alignment_json(clean_id)),
                    "lyrics_ass": str(self.library.lyrics_ass(clean_id)),
                },
            )
            return alignment

        return self._run_stage(clean_id, "align", stage)

    def shift_subtitles(self, song_id: str, *, seconds: float) -> dict[str, Any]:
        clean_id = normalize_song_id(song_id)
        alignment_path = self._require_file(
            self.library.alignment_json(clean_id),
            "Run align before shifting subtitles.",
        )

        def stage() -> dict[str, Any]:
            alignment = read_json(alignment_path, default={}) or {}
            shifted = shift_alignment(alignment, seconds)
            write_json(alignment_path, shifted)
            ass_text = build_ass(shifted, title=clean_id)
            self.library.lyrics_ass(clean_id).parent.mkdir(parents=True, exist_ok=True)
            self.library.lyrics_ass(clean_id).write_text(ass_text, encoding="utf-8")
            update_report(
                self.library.report_json(clean_id),
                subtitle_shift_seconds=seconds,
                alignment={
                    **((read_json(self.library.report_json(clean_id), default={}) or {}).get("alignment") or {}),
                    "alignment_json": str(alignment_path),
                    "lyrics_ass": str(self.library.lyrics_ass(clean_id)),
                    "manual_offset_seconds": seconds,
                },
            )
            return shifted

        return self._run_stage(clean_id, "shift-subtitles", stage)

    def shift_subtitle_lines(
        self,
        song_id: str,
        *,
        start_line: int,
        end_line: int,
        seconds: float,
    ) -> dict[str, Any]:
        clean_id = normalize_song_id(song_id)
        alignment_path = self._require_file(
            self.library.alignment_json(clean_id),
            "Run align before shifting subtitle lines.",
        )

        def stage() -> dict[str, Any]:
            alignment = read_json(alignment_path, default={}) or {}
            shifted = shift_alignment_lines(
                alignment,
                start_index=start_line,
                end_index=end_line,
                offset_seconds=seconds,
            )
            write_json(alignment_path, shifted)
            ass_text = build_ass(shifted, title=clean_id)
            self.library.lyrics_ass(clean_id).parent.mkdir(parents=True, exist_ok=True)
            self.library.lyrics_ass(clean_id).write_text(ass_text, encoding="utf-8")
            update_report(
                self.library.report_json(clean_id),
                subtitle_line_shift_seconds=seconds,
                subtitle_line_shift_range=[start_line, end_line],
            )
            return shifted

        return self._run_stage(clean_id, "shift-subtitle-lines", stage)

    def edit_subtitles(self, song_id: str, updates: list[dict[str, Any]]) -> dict[str, Any]:
        clean_id = normalize_song_id(song_id)
        alignment_path = self._require_file(
            self.library.alignment_json(clean_id),
            "Run align before editing subtitles.",
        )

        def stage() -> dict[str, Any]:
            alignment = read_json(alignment_path, default={}) or {}
            edited = update_alignment_lines(alignment, updates)
            write_json(alignment_path, edited)
            ass_text = build_ass(edited, title=clean_id)
            self.library.lyrics_ass(clean_id).parent.mkdir(parents=True, exist_ok=True)
            self.library.lyrics_ass(clean_id).write_text(ass_text, encoding="utf-8")
            update_report(
                self.library.report_json(clean_id),
                alignment={
                    **((read_json(self.library.report_json(clean_id), default={}) or {}).get("alignment") or {}),
                    "alignment_json": str(alignment_path),
                    "lyrics_ass": str(self.library.lyrics_ass(clean_id)),
                    "manual_edits": True,
                },
            )
            return edited

        return self._run_stage(clean_id, "edit-subtitles", stage)

    def mux(
        self,
        song_id: str,
        *,
        duration_limit: float | None = None,
        audio_order: str = "instrumental-first",
        cancel_file: Path | None = None,
    ) -> Path:
        clean_id = normalize_song_id(song_id)
        source = self.library.source_path(clean_id)
        instrumental = self._require_file(
            self.library.instrumental_wav(clean_id),
            "Run separate before mux, or place instrumental.wav in the output folder.",
        )
        mix = self._require_file(self.library.mix_wav(clean_id), "Run extract before mux.")
        ass = self._require_file(self.library.lyrics_ass(clean_id), "Run align before mux.")
        output = self.library.final_mkv(clean_id)

        def stage() -> Path:
            result = mux_ktv(
                source,
                instrumental,
                mix,
                ass,
                output,
                duration_limit=duration_limit,
                audio_order=audio_order,
                cancel_file=cancel_file,
            )
            update_report(
                self.library.report_json(clean_id),
                final_mkv=str(result),
                audio_order=audio_order,
                final_mkv_take=str(_archive_take(self.library, clean_id, result)),
            )
            return result

        return self._run_stage(clean_id, "mux", stage)

    def replace_audio(
        self,
        song_id: str,
        *,
        keep_audio_index: int = 0,
        copy_subtitles: bool = True,
        duration_limit: float | None = None,
        cancel_file: Path | None = None,
    ) -> Path:
        clean_id = normalize_song_id(song_id)
        source = self.library.source_path(clean_id)
        instrumental = self._require_file(
            self.library.instrumental_wav(clean_id),
            "Run separate before replace-audio.",
        )
        output = self.library.audio_replaced_mkv(clean_id)

        def stage() -> Path:
            _validate_audio_index(source, keep_audio_index)
            result = replace_audio_track(
                source,
                instrumental,
                output,
                keep_audio_index=keep_audio_index,
                copy_subtitles=copy_subtitles,
                duration_limit=duration_limit,
                cancel_file=cancel_file,
            )
            update_report(
                self.library.report_json(clean_id),
                audio_replaced_mkv=str(result),
                audio_replaced_mkv_take=str(_archive_take(self.library, clean_id, result)),
                kept_audio_index=keep_audio_index,
                kept_audio_track=keep_audio_index + 1,
                copied_source_subtitles=copy_subtitles,
            )
            return result

        return self._run_stage(clean_id, "replace-audio", stage)

    def normalize_instrumental(
        self,
        song_id: str,
        *,
        target_i: float = -16.0,
        replace_current: bool = False,
        cancel_file: Path | None = None,
    ) -> Path:
        clean_id = normalize_song_id(song_id)
        source = self._require_file(self.library.instrumental_wav(clean_id), "Run separate before normalize.")
        output = self.library.normalized_instrumental_wav(clean_id)

        def stage() -> Path:
            result = normalize_wav(source, output, target_i=target_i, cancel_file=cancel_file)
            if replace_current:
                shutil.copy2(result, source)
                current = source
            else:
                current = result
            update_report(
                self.library.report_json(clean_id),
                normalized_instrumental=str(result),
                normalization={"target_i": target_i, "replaced_current": replace_current},
                normalized_instrumental_take=str(
                    _archive_take(self.library, clean_id, current, label=f"normalized {target_i:g} LUFS")
                ),
            )
            return current

        return self._run_stage(clean_id, "normalize", stage)

    def clean_work(self, song_id: str) -> dict[str, Any]:
        clean_id = normalize_song_id(song_id)

        def stage() -> dict[str, Any]:
            removed: list[str] = []
            for path in [
                self.library.mix_wav(clean_id),
                self.library.vocals_wav(clean_id),
                self.library.alignment_json(clean_id),
            ]:
                if path.exists():
                    path.unlink()
                    removed.append(str(path))
            demucs_dir = self.library.work_dir(clean_id) / "demucs"
            if demucs_dir.exists():
                shutil.rmtree(demucs_dir)
                removed.append(str(demucs_dir))
            previews_dir = self.library.previews_dir(clean_id)
            if previews_dir.exists():
                shutil.rmtree(previews_dir)
                previews_dir.mkdir(parents=True, exist_ok=True)
                removed.append(str(previews_dir))
            update_report(self.library.report_json(clean_id), cleaned_work_files=removed)
            return {"removed": removed}

        return self._run_stage(clean_id, "clean-work", stage)

    def process(
        self,
        song_id: str,
        *,
        align_backend: str = "auto",
        cancel_file: Path | None = None,
    ) -> dict[str, Any]:
        clean_id = normalize_song_id(song_id)
        self.probe(clean_id)
        self.extract(clean_id, cancel_file=cancel_file)
        self.separate(clean_id, cancel_file=cancel_file)
        self.align(clean_id, backend=align_backend)
        final = self.mux(clean_id, cancel_file=cancel_file)
        return {"song_id": clean_id, "final_mkv": str(final)}

    def batch(self, *, raw_root: Path | None = None, align_backend: str = "auto") -> list[dict[str, Any]]:
        root = raw_root or self.library.raw_root
        results: list[dict[str, Any]] = []
        if not root.exists():
            return results
        for song_dir in sorted(path for path in root.iterdir() if path.is_dir()):
            song_id = normalize_song_id(song_dir.name)
            try:
                results.append(self.process(song_id, align_backend=align_backend))
            except Exception as exc:
                update_report(self.library.report_json(song_id), failure=str(exc))
                results.append({"song_id": song_id, "error": str(exc)})
        return results

    def batch_stage(self, stage: str, *, raw_root: Path | None = None, **params: Any) -> list[dict[str, Any]]:
        root = raw_root or self.library.raw_root
        results: list[dict[str, Any]] = []
        if not root.exists():
            return results
        for song_dir in sorted(path for path in root.iterdir() if path.is_dir()):
            song_id = normalize_song_id(song_dir.name)
            try:
                if stage == "probe":
                    result = self.probe(song_id)
                elif stage == "preview-tracks":
                    result = self.preview_tracks(
                        song_id,
                        duration=float(params.get("duration", 20.0)),
                        start=float(params.get("start", 0.0)),
                        count=int(params.get("count", 1)),
                        spacing=float(params.get("spacing", 45.0)),
                        preset=str(params.get("preset", "manual")),
                    )
                elif stage == "extract":
                    result = self.extract(song_id, audio_index=int(params.get("audio_index", 0)))
                elif stage == "separate":
                    result = self.separate(
                        song_id,
                        model=str(params.get("model", "htdemucs")),
                        device=params.get("device"),
                    )
                else:
                    raise PipelineStateError(f"Unsupported batch stage: {stage}")
                results.append({"song_id": song_id, "stage": stage, "result": result})
            except Exception as exc:
                update_report(self.library.report_json(song_id), failure=str(exc), failed_stage=stage)
                results.append({"song_id": song_id, "stage": stage, "error": str(exc)})
        return results

    def _run_stage(self, song_id: str, stage_name: str, func: StageFunc) -> Any:
        clean_id = normalize_song_id(song_id)
        self.library.ensure_song_dirs(clean_id)
        with song_lock(self.library, clean_id):
            append_stage_status(self.library.status_json(clean_id), stage_name, "running")
            start = perf_counter()
            try:
                result = func()
            except Exception as exc:
                record_stage_checkpoint(
                    self.library,
                    clean_id,
                    stage_name,
                    state="failed",
                    outputs=_stage_outputs(self.library, clean_id, stage_name),
                    message=str(exc),
                )
                append_stage_status(self.library.status_json(clean_id), stage_name, "failed", str(exc))
                update_report(self.library.report_json(clean_id), failure=str(exc), failed_stage=stage_name)
                raise
            elapsed = round(perf_counter() - start, 3)
            record_stage_checkpoint(
                self.library,
                clean_id,
                stage_name,
                state="completed",
                outputs=_stage_outputs(self.library, clean_id, stage_name),
                message=f"completed in {elapsed}s",
            )
            append_stage_status(
                self.library.status_json(clean_id),
                stage_name,
                "completed",
                f"completed in {elapsed}s",
            )
            update_report(
                self.library.report_json(clean_id),
                last_completed_stage=stage_name,
                failure=None,
                failed_stage=None,
            )
            try:
                song = load_song(self.library, clean_id)
                song.status = stage_name
                song.save(self.library.song_json(clean_id))
            except FileNotFoundError:
                pass
            return result

    @staticmethod
    def _require_file(path: Path, message: str) -> Path:
        if not path.exists():
            raise PipelineStateError(f"{message} Missing: {path}")
        return path


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
    if stage in {"align", "shift-subtitles", "shift-subtitle-lines", "edit-subtitles"}:
        return [library.alignment_json(song_id), library.lyrics_ass(song_id)]
    if stage == "mux":
        return [library.final_mkv(song_id)]
    if stage == "replace-audio":
        return [library.audio_replaced_mkv(song_id)]
    if stage == "normalize":
        return [library.normalized_instrumental_wav(song_id)]
    return []


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
