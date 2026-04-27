from __future__ import annotations

import shutil
from collections.abc import Callable
from pathlib import Path
from time import perf_counter
from typing import Any

from .alignment import (
    align_lyrics,
    shift_alignment,
    shift_alignment_lines,
    stretch_alignment_lines,
    update_alignment_lines,
)
from .ass import build_ass
from .checkpoints import record_stage_checkpoint
from .compatibility import compatibility_report
from .errors import PipelineStateError
from .jsonio import read_json, write_json
from .library import load_song, save_lyrics_file, song_summary
from .media import (
    extract_mix,
    extract_preview,
    extract_subtitle,
    mux_ktv,
    normalize_wav,
    probe_media,
    render_audio_wav,
    replace_audio_track,
    run_demucs_two_stems,
)
from .models import Song, append_stage_status, update_report
from .mux_plan import ktv_mux_plan
from .mux_plan import replace_audio_plan as build_replace_audio_plan
from .paths import LibraryPaths, derive_song_id_from_source, normalize_song_id
from .pipeline_support import (
    _archive_take,
    _ass_style,
    _checkpoint_has_outputs,
    _copy_templated_output,
    _import_and_report,
    _optional_float,
    _optional_int,
    _preview_starts,
    _probe_duration,
    _stage_outputs,
    _validate_audio_index,
    _validate_probe_has_required_streams,
    song_lock,
)
from .quality import instrumental_fit_report, mkv_audit_report, separation_quality_report
from .recipes import RECIPE_STAGES, recipe_plan
from .separation_presets import resolve_separation_preset
from .settings import load_settings
from .track_roles import set_track_role

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
        preset: str = "balanced",
        model: str | None = None,
        device: str | None = None,
        cancel_file: Path | None = None,
    ) -> dict[str, Any]:
        clean_id = normalize_song_id(song_id)
        mix = self._require_file(self.library.mix_wav(clean_id), "Run extract before separate.")

        def stage() -> dict[str, Any]:
            separation = resolve_separation_preset(preset, model=model, device=device)
            result = run_demucs_two_stems(
                mix,
                self.library.work_dir(clean_id),
                self.library.instrumental_wav(clean_id),
                self.library.vocals_wav(clean_id),
                model=str(separation["model"]),
                device=str(separation["device"]),
                log_path=self.library.stage_log(clean_id, "separate"),
                cancel_file=cancel_file,
            )
            result["preset"] = separation["id"]
            result["preset_label"] = separation["label"]
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
                        label=f"{result.get('preset_label')} / {result.get('model')} / {result.get('requested_device')}",
                    )
                ),
            )
            return result

        return self._run_stage(clean_id, "separate", stage)

    def separate_sample(
        self,
        song_id: str,
        *,
        audio_index: int = 0,
        start: float = 0.0,
        duration: float = 30.0,
        preset: str = "fast-review",
        model: str | None = None,
        device: str | None = None,
        cancel_file: Path | None = None,
    ) -> dict[str, Any]:
        clean_id = normalize_song_id(song_id)
        source = self.library.source_path(clean_id)

        def stage() -> dict[str, Any]:
            _validate_audio_index(source, audio_index)
            mix = extract_preview(
                source,
                self.library.sample_mix_wav(clean_id),
                audio_index=audio_index,
                start=start,
                duration=duration,
                cancel_file=cancel_file,
            )
            separation = resolve_separation_preset(preset, model=model, device=device)
            result = run_demucs_two_stems(
                mix,
                self.library.work_dir(clean_id) / "sample",
                self.library.instrumental_sample_wav(clean_id),
                self.library.vocals_sample_wav(clean_id),
                model=str(separation["model"]),
                device=str(separation["device"]),
                log_path=self.library.stage_log(clean_id, "separate-sample"),
                cancel_file=cancel_file,
            )
            result.update(
                {
                    "preset": separation["id"],
                    "preset_label": separation["label"],
                    "audio_index": audio_index,
                    "start": start,
                    "duration": duration,
                    "sample_mix": str(mix),
                }
            )
            update_report(
                self.library.report_json(clean_id),
                separation_sample=result,
                separation_sample_quality=separation_quality_report(
                    mix_wav=mix,
                    instrumental_wav=self.library.instrumental_sample_wav(clean_id),
                    vocals_wav=self.library.vocals_sample_wav(clean_id),
                ),
                instrumental_sample_take=str(
                    _archive_take(
                        self.library,
                        clean_id,
                        self.library.instrumental_sample_wav(clean_id),
                        label=f"sample {duration:g}s from Track {audio_index + 1} / {result.get('preset_label')}",
                    )
                ),
            )
            return result

        return self._run_stage(clean_id, "separate-sample", stage)

    def set_instrumental(
        self,
        song_id: str,
        source_path: Path,
        *,
        label: str = "external instrumental",
        offset: float = 0.0,
        gain_db: float = 0.0,
        fit_to_mix: bool = False,
        normalize: bool = False,
        cancel_file: Path | None = None,
    ) -> Path:
        clean_id = normalize_song_id(song_id)
        source = Path(source_path).expanduser()
        if not source.exists():
            raise PipelineStateError(f"Instrumental file does not exist: {source}")

        def stage() -> Path:
            target = self.library.instrumental_wav(clean_id)
            target.parent.mkdir(parents=True, exist_ok=True)
            reference = self.library.mix_wav(clean_id)
            target_duration = _probe_duration(reference) if fit_to_mix and reference.exists() else None
            if source.resolve() != target.resolve():
                render_audio_wav(
                    source,
                    target,
                    offset=offset,
                    target_duration=target_duration,
                    gain_db=gain_db,
                    normalize=normalize,
                    cancel_file=cancel_file,
                )
            take = _archive_take(self.library, clean_id, target, label=label)
            update_report(
                self.library.report_json(clean_id),
                instrumental_wav=str(target),
                external_instrumental={
                    "source": str(source),
                    "label": label,
                    "offset": offset,
                    "gain_db": gain_db,
                    "fit_to_mix": fit_to_mix,
                    "target_duration": target_duration,
                    "normalize": normalize,
                },
                external_instrumental_fit=instrumental_fit_report(
                    reference_wav=reference if reference.exists() else None,
                    instrumental_wav=target,
                ),
                instrumental_take=str(take),
            )
            return target

        return self._run_stage(clean_id, "set-instrumental", stage)

    def set_track_role(self, song_id: str, *, audio_index: int, role: str, note: str = "") -> dict[str, Any]:
        clean_id = normalize_song_id(song_id)

        def stage() -> dict[str, Any]:
            _validate_audio_index(self.library.source_path(clean_id), audio_index)
            return set_track_role(self.library, clean_id, audio_index=audio_index, role=role, note=note)

        return self._run_stage(clean_id, "track-role", stage)

    def mux_plan(self, song_id: str, *, audio_order: str = "instrumental-first") -> dict[str, Any]:
        clean_id = normalize_song_id(song_id)
        summary = song_summary(self.library, clean_id)
        report = read_json(self.library.report_json(clean_id), default={}) or {}
        plan = ktv_mux_plan(summary, report, audio_order=audio_order)
        update_report(self.library.report_json(clean_id), planned_ktv_mux=plan)
        return plan

    def replace_audio_plan(
        self,
        song_id: str,
        *,
        keep_audio_index: int = 0,
        copy_subtitles: bool = True,
    ) -> dict[str, Any]:
        clean_id = normalize_song_id(song_id)
        summary = song_summary(self.library, clean_id)
        report = read_json(self.library.report_json(clean_id), default={}) or {}
        plan = build_replace_audio_plan(summary, report, keep_audio_index=keep_audio_index, copy_subtitles=copy_subtitles)
        update_report(self.library.report_json(clean_id), planned_audio_replace=plan)
        return plan

    def remake_track(
        self,
        song_id: str,
        *,
        audio_index: int = 0,
        keep_audio_index: int = 0,
        preset: str = "balanced",
        model: str | None = None,
        device: str | None = None,
        copy_subtitles: bool = True,
        duration_limit: float | None = None,
        cancel_file: Path | None = None,
    ) -> dict[str, Any]:
        clean_id = normalize_song_id(song_id)
        self.extract(clean_id, audio_index=audio_index, cancel_file=cancel_file)
        separation = self.separate(clean_id, preset=preset, model=model, device=device, cancel_file=cancel_file)
        replaced = self.replace_audio(
            clean_id,
            keep_audio_index=keep_audio_index,
            copy_subtitles=copy_subtitles,
            duration_limit=duration_limit,
            cancel_file=cancel_file,
        )
        update_report(
            self.library.report_json(clean_id),
            remade_from_audio_index=audio_index,
            remade_from_audio_track=audio_index + 1,
            remade_keep_audio_index=keep_audio_index,
            remade_keep_audio_track=keep_audio_index + 1,
        )
        return {"song_id": clean_id, "separation": separation, "audio_replaced_mkv": str(replaced)}

    def extract_embedded_subtitles(
        self,
        song_id: str,
        *,
        subtitle_index: int = 0,
        cancel_file: Path | None = None,
    ) -> Path:
        clean_id = normalize_song_id(song_id)
        source = self.library.source_path(clean_id)

        def stage() -> Path:
            info = probe_media(source)
            subtitle_streams = info["subtitle_streams"]
            if subtitle_index < 0 or subtitle_index >= len(subtitle_streams):
                raise PipelineStateError(
                    f"Subtitle Track {subtitle_index + 1} does not exist. "
                    f"This source has {len(subtitle_streams)} subtitle track(s)."
                )
            codec = str(subtitle_streams[subtitle_index].get("codec_name") or "").lower()
            suffix = ".srt" if codec in {"subrip", "srt"} else ".ass"
            extracted = self.library.embedded_lyrics_file(clean_id, suffix)
            extract_subtitle(source, extracted, subtitle_index=subtitle_index, cancel_file=cancel_file)
            result = save_lyrics_file(self.library, clean_id, extracted)
            update_report(
                self.library.report_json(clean_id),
                extracted_subtitles={
                    "subtitle_index": subtitle_index,
                    "subtitle_track": subtitle_index + 1,
                    "codec": codec,
                    "path": str(extracted),
                    "lyrics_path": str(result),
                },
            )
            return result

        return self._run_stage(clean_id, "extract-subtitles", stage)

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
            lrc_path = self.library.original_lyrics_file(clean_id, ".lrc")
            alignment = align_lyrics(audio, lyrics, duration=duration, backend=backend, lrc_path=lrc_path)
            write_json(self.library.alignment_json(clean_id), alignment)
            ass_text = build_ass(alignment, title=clean_id, style=_ass_style(self.library))
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
            ass_text = build_ass(shifted, title=clean_id, style=_ass_style(self.library))
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
            ass_text = build_ass(shifted, title=clean_id, style=_ass_style(self.library))
            self.library.lyrics_ass(clean_id).parent.mkdir(parents=True, exist_ok=True)
            self.library.lyrics_ass(clean_id).write_text(ass_text, encoding="utf-8")
            update_report(
                self.library.report_json(clean_id),
                subtitle_line_shift_seconds=seconds,
                subtitle_line_shift_range=[start_line, end_line],
            )
            return shifted

        return self._run_stage(clean_id, "shift-subtitle-lines", stage)

    def stretch_subtitle_lines(
        self,
        song_id: str,
        *,
        start_line: int,
        end_line: int,
        target_start: float,
        target_end: float,
    ) -> dict[str, Any]:
        clean_id = normalize_song_id(song_id)
        alignment_path = self._require_file(
            self.library.alignment_json(clean_id),
            "Run align before stretching subtitle lines.",
        )

        def stage() -> dict[str, Any]:
            alignment = read_json(alignment_path, default={}) or {}
            stretched = stretch_alignment_lines(
                alignment,
                start_index=start_line,
                end_index=end_line,
                target_start=target_start,
                target_end=target_end,
            )
            write_json(alignment_path, stretched)
            ass_text = build_ass(stretched, title=clean_id, style=_ass_style(self.library))
            self.library.lyrics_ass(clean_id).parent.mkdir(parents=True, exist_ok=True)
            self.library.lyrics_ass(clean_id).write_text(ass_text, encoding="utf-8")
            update_report(
                self.library.report_json(clean_id),
                subtitle_stretch_range=[start_line, end_line],
                subtitle_stretch_window=[target_start, target_end],
            )
            return stretched

        return self._run_stage(clean_id, "stretch-subtitle-lines", stage)

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
            ass_text = build_ass(edited, title=clean_id, style=_ass_style(self.library))
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
            settings = load_settings(self.library)
            plan = ktv_mux_plan(
                song_summary(self.library, clean_id),
                read_json(self.library.report_json(clean_id), default={}) or {},
                audio_order=audio_order,
            )
            result = mux_ktv(
                source,
                instrumental,
                mix,
                ass,
                output,
                duration_limit=duration_limit,
                audio_order=audio_order,
                instrumental_title=str(settings["instrumental_track_title"]),
                original_title=str(settings["original_track_title"]),
                cancel_file=cancel_file,
            )
            output_probe = probe_media(result)
            audit = mkv_audit_report(output_probe, expected_audio_streams=2, expected_subtitle_streams=1)
            templated = _copy_templated_output(self.library, clean_id, result, kind="ktv")
            update_report(
                self.library.report_json(clean_id),
                final_mkv=str(result),
                audio_order=audio_order,
                planned_ktv_mux=plan,
                final_mkv_audit=audit,
                compatibility=compatibility_report(audit),
                templated_final_mkv=str(templated) if templated else None,
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
            settings = load_settings(self.library)
            plan = build_replace_audio_plan(
                song_summary(self.library, clean_id),
                read_json(self.library.report_json(clean_id), default={}) or {},
                keep_audio_index=keep_audio_index,
                copy_subtitles=copy_subtitles,
            )
            result = replace_audio_track(
                source,
                instrumental,
                output,
                keep_audio_index=keep_audio_index,
                copy_subtitles=copy_subtitles,
                duration_limit=duration_limit,
                instrumental_title=str(settings["instrumental_track_title"]),
                original_title=str(settings["original_track_title"]),
                cancel_file=cancel_file,
            )
            output_probe = probe_media(result)
            audit = mkv_audit_report(
                output_probe,
                expected_audio_streams=2,
                expected_subtitle_streams=0,
            )
            update_report(
                self.library.report_json(clean_id),
                audio_replaced_mkv=str(result),
                planned_audio_replace=plan,
                audio_replaced_mkv_audit=audit,
                audio_replaced_compatibility=compatibility_report(audit),
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
                self.library.sample_mix_wav(clean_id),
                self.library.vocals_sample_wav(clean_id),
                self.library.instrumental_sample_wav(clean_id),
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

    def process_from(
        self,
        song_id: str,
        *,
        start_stage: str,
        align_backend: str = "auto",
        audio_index: int = 0,
        model: str | None = None,
        device: str | None = None,
        duration_limit: float | None = None,
        cancel_file: Path | None = None,
    ) -> dict[str, Any]:
        clean_id = normalize_song_id(song_id)
        ordered = ["probe", "extract", "separate", "align", "mux"]
        if start_stage not in ordered:
            raise PipelineStateError(f"Unsupported run-from stage: {start_stage}")
        ran: list[str] = []
        for stage in ordered[ordered.index(start_stage) :]:
            if stage == "probe":
                self.probe(clean_id)
            elif stage == "extract":
                self.extract(clean_id, audio_index=audio_index, cancel_file=cancel_file)
            elif stage == "separate":
                self.separate(clean_id, model=model, device=device, cancel_file=cancel_file)
            elif stage == "align":
                self.align(clean_id, backend=align_backend)
            elif stage == "mux":
                self.mux(clean_id, duration_limit=duration_limit, cancel_file=cancel_file)
            ran.append(stage)
        return {"song_id": clean_id, "start_stage": start_stage, "ran": ran}

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
        limit = _optional_int(params.get("limit"))
        stop_on_error = bool(params.get("stop_on_error", False))
        skip_completed = bool(params.get("skip_completed", False))
        dry_run = bool(params.get("dry_run", False))
        processed = 0
        for song_dir in sorted(path for path in root.iterdir() if path.is_dir()):
            song_id = normalize_song_id(song_dir.name)
            if limit is not None and processed >= limit:
                break
            if skip_completed and _checkpoint_has_outputs(self.library, song_id, stage):
                results.append({"song_id": song_id, "stage": stage, "skipped": "completed"})
                continue
            if dry_run:
                results.append({"song_id": song_id, "stage": stage, "planned": True})
                processed += 1
                continue
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
                        preset=str(params.get("separation_preset", params.get("preset", "balanced"))),
                        model=params.get("model"),
                        device=params.get("device"),
                    )
                elif stage == "separate-sample":
                    result = self.separate_sample(
                        song_id,
                        audio_index=int(params.get("audio_index", 0)),
                        start=float(params.get("start", 0.0)),
                        duration=float(params.get("duration", 30.0)),
                        preset=str(params.get("separation_preset", params.get("preset", "fast-review"))),
                        model=params.get("model"),
                        device=params.get("device"),
                    )
                else:
                    raise PipelineStateError(f"Unsupported batch stage: {stage}")
                results.append({"song_id": song_id, "stage": stage, "result": result})
                processed += 1
            except Exception as exc:
                update_report(self.library.report_json(song_id), failure=str(exc), failed_stage=stage)
                results.append({"song_id": song_id, "stage": stage, "error": str(exc)})
                processed += 1
                if stop_on_error:
                    break
        return results

    def batch_recipe(self, recipe: str, *, raw_root: Path | None = None, dry_run: bool = False, **params: Any) -> dict[str, Any]:
        root = raw_root or self.library.raw_root
        song_ids = [normalize_song_id(path.name) for path in sorted(root.iterdir()) if path.is_dir()] if root.exists() else []
        if recipe not in RECIPE_STAGES:
            raise PipelineStateError(f"Unsupported batch recipe: {recipe}")
        plan = recipe_plan(recipe, song_ids=song_ids)
        if dry_run:
            return {**plan, "dry_run": True, "results": []}
        results = []
        for song_id in song_ids:
            song_result: dict[str, Any] = {"song_id": song_id, "stages": []}
            for stage in RECIPE_STAGES[recipe]:
                try:
                    song_result["stages"].append({"stage": stage, "result": self._run_recipe_stage(song_id, stage, params)})
                except Exception as exc:
                    update_report(self.library.report_json(song_id), failure=str(exc), failed_stage=stage)
                    song_result["stages"].append({"stage": stage, "error": str(exc)})
                    break
            results.append(song_result)
        return {**plan, "dry_run": False, "results": results}

    def _run_recipe_stage(self, song_id: str, stage: str, params: dict[str, Any]) -> Any:
        if stage == "probe":
            return self.probe(song_id)
        if stage == "preview-tracks":
            return self.preview_tracks(
                song_id,
                duration=float(params.get("duration", 20.0)),
                start=float(params.get("start", 0.0)),
                count=int(params.get("count", 1)),
                spacing=float(params.get("spacing", 45.0)),
                preset=str(params.get("preview_preset", params.get("preset", "manual"))),
            )
        if stage == "extract":
            return self.extract(song_id, audio_index=int(params.get("audio_index", 0)))
        if stage == "separate":
            return self.separate(
                song_id,
                preset=str(params.get("separation_preset", "balanced")),
                model=params.get("model"),
                device=params.get("device"),
            )
        if stage == "separate-sample":
            return self.separate_sample(
                song_id,
                audio_index=int(params.get("audio_index", 0)),
                start=float(params.get("start", 0.0)),
                duration=float(params.get("sample_duration", params.get("duration", 30.0))),
                preset=str(params.get("separation_preset", "fast-review")),
                model=params.get("model"),
                device=params.get("device"),
            )
        if stage == "replace-audio":
            return self.replace_audio(
                song_id,
                keep_audio_index=int(params.get("keep_audio_index", 0)),
                copy_subtitles=bool(params.get("copy_subtitles", True)),
                duration_limit=_optional_float(params.get("duration_limit")),
            )
        if stage == "align":
            return self.align(song_id, backend=str(params.get("align_backend", "auto")))
        if stage == "mux":
            return self.mux(
                song_id,
                audio_order=str(params.get("audio_order", "instrumental-first")),
                duration_limit=_optional_float(params.get("duration_limit")),
            )
        raise PipelineStateError(f"Unsupported recipe stage: {stage}")

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
