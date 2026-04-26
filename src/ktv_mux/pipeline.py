from __future__ import annotations

from pathlib import Path
from time import perf_counter
from typing import Any, Callable

from .alignment import align_lyrics
from .ass import build_ass
from .errors import PipelineStateError
from .jsonio import write_json
from .library import import_source, load_song, save_lyrics_file
from .media import extract_mix, mux_ktv, probe_media, replace_audio_track, run_demucs_two_stems
from .models import Song, append_stage_status, update_report
from .paths import LibraryPaths, derive_song_id_from_source, normalize_song_id

StageFunc = Callable[[], Any]


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
    ) -> Song:
        stage_id = song_id or derive_song_id_from_source(path_or_url)
        return self._run_stage(
            stage_id,
            "import",
            lambda: import_source(
                path_or_url,
                song_id=song_id,
                library=self.library,
                title=title,
                artist=artist,
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

    def extract(self, song_id: str, *, audio_index: int = 0) -> Path:
        clean_id = normalize_song_id(song_id)
        source = self.library.source_path(clean_id)
        mix = self.library.mix_wav(clean_id)

        def stage() -> Path:
            result = extract_mix(source, mix, audio_index=audio_index)
            update_report(
                self.library.report_json(clean_id),
                mix_wav=str(result),
                selected_audio_index=audio_index,
                selected_audio_track=audio_index + 1,
            )
            return result

        return self._run_stage(clean_id, "extract", stage)

    def separate(self, song_id: str, *, model: str = "htdemucs") -> dict[str, Any]:
        clean_id = normalize_song_id(song_id)
        mix = self._require_file(self.library.mix_wav(clean_id), "Run extract before separate.")

        def stage() -> dict[str, Any]:
            result = run_demucs_two_stems(
                mix,
                self.library.work_dir(clean_id),
                self.library.instrumental_wav(clean_id),
                self.library.vocals_wav(clean_id),
                model=model,
            )
            update_report(self.library.report_json(clean_id), separation=result)
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

    def mux(
        self,
        song_id: str,
        *,
        duration_limit: float | None = None,
        audio_order: str = "instrumental-first",
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
            )
            update_report(
                self.library.report_json(clean_id),
                final_mkv=str(result),
                audio_order=audio_order,
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
    ) -> Path:
        clean_id = normalize_song_id(song_id)
        source = self.library.source_path(clean_id)
        instrumental = self._require_file(
            self.library.instrumental_wav(clean_id),
            "Run separate before replace-audio.",
        )
        output = self.library.audio_replaced_mkv(clean_id)

        def stage() -> Path:
            result = replace_audio_track(
                source,
                instrumental,
                output,
                keep_audio_index=keep_audio_index,
                copy_subtitles=copy_subtitles,
                duration_limit=duration_limit,
            )
            update_report(
                self.library.report_json(clean_id),
                audio_replaced_mkv=str(result),
                kept_audio_index=keep_audio_index,
                kept_audio_track=keep_audio_index + 1,
                copied_source_subtitles=copy_subtitles,
            )
            return result

        return self._run_stage(clean_id, "replace-audio", stage)

    def process(self, song_id: str, *, align_backend: str = "auto") -> dict[str, Any]:
        clean_id = normalize_song_id(song_id)
        self.probe(clean_id)
        self.extract(clean_id)
        self.separate(clean_id)
        self.align(clean_id, backend=align_backend)
        final = self.mux(clean_id)
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

    def _run_stage(self, song_id: str, stage_name: str, func: StageFunc) -> Any:
        clean_id = normalize_song_id(song_id)
        self.library.ensure_song_dirs(clean_id)
        append_stage_status(self.library.status_json(clean_id), stage_name, "running")
        start = perf_counter()
        try:
            result = func()
        except Exception as exc:
            append_stage_status(self.library.status_json(clean_id), stage_name, "failed", str(exc))
            update_report(self.library.report_json(clean_id), failure=str(exc), failed_stage=stage_name)
            raise
        elapsed = round(perf_counter() - start, 3)
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
