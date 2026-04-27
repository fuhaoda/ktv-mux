from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict, is_dataclass
from pathlib import Path
from typing import Any

from .diagnostics import run_doctor
from .errors import KtvError
from .exporter import export_song_package
from .jobs import LocalJobRunner
from .jsonio import read_json
from .library import delete_song, import_inbox, rename_song, song_summary, update_song_metadata
from .paths import LibraryPaths
from .pipeline import Pipeline
from .planner import next_actions
from .preflight import song_preflight
from .recipes import RECIPE_STAGES
from .separation_presets import PRESETS
from .settings import load_settings, save_settings
from .storage import library_storage_report, song_storage_report
from .track_roles import TRACK_ROLES
from .versions import delete_take, list_takes, set_current_take, update_take


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="ktv", description="KTV MKV production pipeline")
    parser.add_argument("--library", default="library", help="library root directory")
    sub = parser.add_subparsers(dest="command", required=True)

    import_p = sub.add_parser("import", help="import a local media file or URL")
    import_p.add_argument("source", help="local path or URL")
    import_p.add_argument("--song-id", help="optional; defaults to the source filename")
    import_p.add_argument("--title")
    import_p.add_argument("--artist")

    import_many_p = sub.add_parser("import-many", help="import several local media files")
    import_many_p.add_argument("sources", nargs="+", help="local paths or URLs")

    metadata_p = sub.add_parser("metadata", help="edit song title and artist")
    metadata_p.add_argument("song_id")
    metadata_p.add_argument("--title")
    metadata_p.add_argument("--artist")
    metadata_p.add_argument("--tags", help="comma-separated tags")
    metadata_p.add_argument("--rating", type=int, choices=range(1, 6))

    rename_p = sub.add_parser("rename", help="rename a song id and move its library folders")
    rename_p.add_argument("old_song_id")
    rename_p.add_argument("new_song_id")

    lyrics_p = sub.add_parser("lyrics", help="copy lyrics text into the song folder")
    lyrics_p.add_argument("song_id")
    lyrics_p.add_argument("lyrics_path")

    sub.add_parser("list", help="list known songs")

    next_p = sub.add_parser("next", help="show suggested next actions for a song")
    next_p.add_argument("song_id")

    preflight_p = sub.add_parser(
        "preflight",
        help="check whether a song is ready for sample review, instrumental review, replace-audio, or final MKV",
    )
    preflight_p.add_argument("song_id")

    probe_p = sub.add_parser("probe", help="probe source media")
    probe_p.add_argument("song_id")

    extract_p = sub.add_parser("extract", help="extract original mix audio")
    extract_p.add_argument("song_id")
    extract_p.add_argument(
        "--audio-index",
        type=int,
        default=0,
        help="zero-based audio stream index; Track 1 is 0, Track 2 is 1",
    )

    preview_p = sub.add_parser("preview-tracks", help="extract short previews for every source audio track")
    preview_p.add_argument("song_id")
    preview_p.add_argument("--start", type=float, default=0.0, help="preview start offset in seconds")
    preview_p.add_argument("--duration", type=float, default=20.0)
    preview_p.add_argument("--count", type=int, default=1, help="number of preview segments per audio track")
    preview_p.add_argument("--spacing", type=float, default=45.0, help="seconds between preview segments")
    preview_p.add_argument("--preset", default="manual", choices=["manual", "chorus"], help="preview start strategy")

    separate_p = sub.add_parser("separate", help="separate vocals from accompaniment")
    separate_p.add_argument("song_id")
    separate_p.add_argument("--preset", default="balanced", choices=sorted(PRESETS))
    separate_p.add_argument("--model")
    separate_p.add_argument("--device", default="auto", choices=["auto", "cpu", "mps", "cuda"])

    sample_p = sub.add_parser("separate-sample", help="separate a short segment before running the full song")
    sample_p.add_argument("song_id")
    sample_p.add_argument("--audio-index", type=int, default=0)
    sample_p.add_argument("--start", type=float, default=0.0)
    sample_p.add_argument("--duration", type=float, default=30.0)
    sample_p.add_argument("--preset", default="fast-review", choices=sorted(PRESETS))
    sample_p.add_argument("--model")
    sample_p.add_argument("--device", default="auto", choices=["auto", "cpu", "mps", "cuda"])

    set_instrumental_p = sub.add_parser("set-instrumental", help="use an existing WAV/AIFF/MP3 file as instrumental.wav")
    set_instrumental_p.add_argument("song_id")
    set_instrumental_p.add_argument("audio_path")
    set_instrumental_p.add_argument("--label", default="external instrumental")
    set_instrumental_p.add_argument("--offset", type=float, default=0.0, help="positive delays audio; negative trims start")
    set_instrumental_p.add_argument("--gain-db", type=float, default=0.0, help="apply gain before review/mux")
    set_instrumental_p.add_argument("--fit-to-mix", action="store_true", help="pad/trim to match mix.wav duration")
    set_instrumental_p.add_argument("--normalize", action="store_true", help="apply loudness normalization while importing")

    track_role_p = sub.add_parser("track-role", help="save a manual role label for a source audio track")
    track_role_p.add_argument("song_id")
    track_role_p.add_argument("--audio-index", type=int, required=True)
    track_role_p.add_argument("--role", required=True, choices=TRACK_ROLES)
    track_role_p.add_argument("--note", default="")

    normalize_p = sub.add_parser("normalize", help="create a loudness-normalized instrumental WAV")
    normalize_p.add_argument("song_id")
    normalize_p.add_argument("--target-i", type=float, default=-16.0, help="target integrated loudness")
    normalize_p.add_argument("--replace-current", action="store_true", help="replace instrumental.wav with normalized audio")

    align_p = sub.add_parser("align", help="align lyrics and generate ASS")
    align_p.add_argument("song_id")
    align_p.add_argument("--backend", default="auto", choices=["auto", "funasr", "simple", "lrc"])

    shift_p = sub.add_parser("shift", help="shift generated subtitle timing and rebuild ASS")
    shift_p.add_argument("song_id")
    shift_p.add_argument(
        "--seconds",
        type=float,
        required=True,
        help="positive delays subtitles; negative makes them earlier",
    )

    edit_line_p = sub.add_parser("edit-line", help="edit one aligned lyric line and rebuild ASS")
    edit_line_p.add_argument("song_id")
    edit_line_p.add_argument("--index", type=int, required=True, help="zero-based lyric line index")
    edit_line_p.add_argument("--start", type=float, required=True)
    edit_line_p.add_argument("--end", type=float, required=True)
    edit_line_p.add_argument("--text", required=True)

    mux_p = sub.add_parser("mux", help="mux final dual-audio MKV")
    mux_p.add_argument("song_id")
    mux_p.add_argument(
        "--audio-order",
        default="instrumental-first",
        choices=["instrumental-first", "original-first"],
        help="instrumental-first makes accompaniment track 1; original-first keeps original mix as track 1",
    )
    mux_p.add_argument("--duration-limit", type=float, default=None, help="mux only the first N seconds")

    mux_plan_p = sub.add_parser("mux-plan", help="preview final KTV MKV track order before muxing")
    mux_plan_p.add_argument("song_id")
    mux_plan_p.add_argument("--audio-order", default="instrumental-first", choices=["instrumental-first", "original-first"])

    replace_p = sub.add_parser(
        "replace-audio",
        help="create an MKV with source video, original Track 1, and generated instrumental as Track 2",
    )
    replace_p.add_argument("song_id")
    replace_p.add_argument(
        "--keep-audio-index",
        type=int,
        default=0,
        help="zero-based original audio stream to keep as Track 1",
    )
    replace_p.add_argument(
        "--no-copy-subtitles",
        action="store_true",
        help="do not copy source subtitle streams",
    )
    replace_p.add_argument("--duration-limit", type=float, default=None, help="mux only the first N seconds")

    replace_plan_p = sub.add_parser("replace-plan", help="preview audio-replaced MKV track order before muxing")
    replace_plan_p.add_argument("song_id")
    replace_plan_p.add_argument("--keep-audio-index", type=int, default=0)
    replace_plan_p.add_argument("--no-copy-subtitles", action="store_true")

    remake_p = sub.add_parser("remake-track", help="extract one source track, remake accompaniment, and replace audio")
    remake_p.add_argument("song_id")
    remake_p.add_argument("--audio-index", type=int, default=0, help="source audio track to separate")
    remake_p.add_argument("--keep-audio-index", type=int, default=0, help="source audio track to keep in the new MKV")
    remake_p.add_argument("--preset", default="balanced", choices=sorted(PRESETS))
    remake_p.add_argument("--model")
    remake_p.add_argument("--device", default="auto", choices=["auto", "cpu", "mps", "cuda"])
    remake_p.add_argument("--no-copy-subtitles", action="store_true")
    remake_p.add_argument("--duration-limit", type=float, default=None)

    extract_subs_p = sub.add_parser("extract-subtitles", help="extract an embedded subtitle track into lyrics.txt/ASS")
    extract_subs_p.add_argument("song_id")
    extract_subs_p.add_argument("--subtitle-index", type=int, default=0)

    lyrics_versions_p = sub.add_parser("lyrics-versions", help="list saved lyrics revisions")
    lyrics_versions_p.add_argument("song_id")

    clean_p = sub.add_parser("clean-work", help="remove regenerable work files for one song")
    clean_p.add_argument("song_id")

    takes_p = sub.add_parser("takes", help="list saved output takes for one song")
    takes_p.add_argument("song_id")

    take_note_p = sub.add_parser("take-note", help="edit a saved output take label/note")
    take_note_p.add_argument("song_id")
    take_note_p.add_argument("filename")
    take_note_p.add_argument("--label", default="")
    take_note_p.add_argument("--note", default="")
    take_note_p.add_argument("--score", type=int)

    take_current_p = sub.add_parser("take-current", help="promote a saved take to the stable output filename")
    take_current_p.add_argument("song_id")
    take_current_p.add_argument("filename")

    take_delete_p = sub.add_parser("take-delete", help="delete a saved output take")
    take_delete_p.add_argument("song_id")
    take_delete_p.add_argument("filename")

    export_p = sub.add_parser("export", help="zip current song outputs and reports")
    export_p.add_argument("song_id")
    export_p.add_argument("--no-audio", action="store_true")
    export_p.add_argument("--no-mkv", action="store_true")
    export_p.add_argument("--no-takes", action="store_true")
    export_p.add_argument("--include-logs", action="store_true")

    inbox_p = sub.add_parser("inbox-scan", help="import media files from library/inbox")
    inbox_p.add_argument("--limit", type=int)

    storage_p = sub.add_parser("storage", help="show disk usage for the library or one song")
    storage_p.add_argument("song_id", nargs="?")

    jobs_p = sub.add_parser("jobs", help="list local Web jobs")
    jobs_p.add_argument("--limit", type=int, default=25)

    sub.add_parser("jobs-prune", help="delete completed, failed, and canceled local Web jobs")

    settings_p = sub.add_parser("settings", help="show or update local defaults")
    settings_p.add_argument("--worker-count", type=int)
    settings_p.add_argument("--preview-start", type=float)
    settings_p.add_argument("--preview-duration", type=float)
    settings_p.add_argument("--preview-count", type=int)
    settings_p.add_argument("--preview-spacing", type=float)
    settings_p.add_argument("--preview-preset", choices=["manual", "chorus"])
    settings_p.add_argument("--demucs-model")
    settings_p.add_argument("--demucs-device", choices=["auto", "cpu", "mps", "cuda"])
    settings_p.add_argument("--normalize-target-i", type=float)
    settings_p.add_argument("--auto-refresh-seconds", type=int)
    settings_p.add_argument("--default-audio-order", choices=["instrumental-first", "original-first"])
    settings_p.add_argument("--default-duration-limit", type=float)
    settings_p.add_argument("--output-template")
    settings_p.add_argument("--package-include-logs", action="store_true")
    settings_p.add_argument("--subtitle-font-size", type=int)
    settings_p.add_argument("--subtitle-margin-v", type=int)
    settings_p.add_argument("--subtitle-primary-colour")
    settings_p.add_argument("--subtitle-secondary-colour")
    settings_p.add_argument("--instrumental-track-title")
    settings_p.add_argument("--original-track-title")

    delete_p = sub.add_parser("delete", help="delete raw/work/output folders for one song")
    delete_p.add_argument("song_id")

    process_p = sub.add_parser("process", help="run probe/extract/separate/align/mux")
    process_p.add_argument("song_id")
    process_p.add_argument("--align-backend", default="auto", choices=["auto", "funasr", "simple", "lrc"])

    run_from_p = sub.add_parser("run-from", help="run the full pipeline starting from one stage")
    run_from_p.add_argument("song_id")
    run_from_p.add_argument("start_stage", choices=["probe", "extract", "separate", "align", "mux"])
    run_from_p.add_argument("--align-backend", default="auto", choices=["auto", "funasr", "simple", "lrc"])
    run_from_p.add_argument("--audio-index", type=int, default=0)
    run_from_p.add_argument("--model", default="htdemucs")
    run_from_p.add_argument("--device", default="auto", choices=["auto", "cpu", "mps", "cuda"])
    run_from_p.add_argument("--duration-limit", type=float, default=None)

    batch_p = sub.add_parser("batch", help="process every raw song folder")
    batch_p.add_argument("--root", default=None, help="raw root, defaults to library/raw")
    batch_p.add_argument("--align-backend", default="auto", choices=["auto", "funasr", "simple", "lrc"])

    batch_stage_p = sub.add_parser("batch-stage", help="run one stage for every raw song folder")
    batch_stage_p.add_argument("stage", choices=["probe", "preview-tracks", "extract", "separate", "separate-sample"])
    batch_stage_p.add_argument("--root", default=None, help="raw root, defaults to library/raw")
    batch_stage_p.add_argument("--audio-index", type=int, default=0)
    batch_stage_p.add_argument("--start", type=float, default=0.0)
    batch_stage_p.add_argument("--duration", type=float, default=20.0)
    batch_stage_p.add_argument("--count", type=int, default=1)
    batch_stage_p.add_argument("--spacing", type=float, default=45.0)
    batch_stage_p.add_argument("--preset", default="manual", choices=["manual", "chorus"])
    batch_stage_p.add_argument("--separation-preset", default="balanced", choices=sorted(PRESETS))
    batch_stage_p.add_argument("--model", default="htdemucs")
    batch_stage_p.add_argument("--device", default="auto", choices=["auto", "cpu", "mps", "cuda"])
    batch_stage_p.add_argument("--limit", type=int)
    batch_stage_p.add_argument("--skip-completed", action="store_true")
    batch_stage_p.add_argument("--stop-on-error", action="store_true")
    batch_stage_p.add_argument("--dry-run", action="store_true")

    batch_recipe_p = sub.add_parser("batch-recipe", help="run a saved multi-stage recipe for every raw song folder")
    batch_recipe_p.add_argument("recipe", choices=sorted(RECIPE_STAGES))
    batch_recipe_p.add_argument("--root", default=None, help="raw root, defaults to library/raw")
    batch_recipe_p.add_argument("--audio-index", type=int, default=0)
    batch_recipe_p.add_argument("--keep-audio-index", type=int, default=0)
    batch_recipe_p.add_argument("--start", type=float, default=0.0)
    batch_recipe_p.add_argument("--duration", type=float, default=20.0)
    batch_recipe_p.add_argument("--count", type=int, default=1)
    batch_recipe_p.add_argument("--spacing", type=float, default=45.0)
    batch_recipe_p.add_argument("--separation-preset", default="balanced", choices=sorted(PRESETS))
    batch_recipe_p.add_argument("--model", default="htdemucs")
    batch_recipe_p.add_argument("--device", default="auto", choices=["auto", "cpu", "mps", "cuda"])
    batch_recipe_p.add_argument("--align-backend", default="auto", choices=["auto", "funasr", "simple", "lrc"])
    batch_recipe_p.add_argument("--audio-order", default="instrumental-first", choices=["instrumental-first", "original-first"])
    batch_recipe_p.add_argument("--duration-limit", type=float, default=None)
    batch_recipe_p.add_argument("--dry-run", action="store_true")

    status_p = sub.add_parser("status", help="show song status")
    status_p.add_argument("song_id")

    doctor_p = sub.add_parser("doctor", help="diagnose local dependencies and optional song state")
    doctor_p.add_argument("song_id", nargs="?")

    serve_p = sub.add_parser("serve", help="start local web UI")
    serve_p.add_argument("--host", default="127.0.0.1")
    serve_p.add_argument("--port", default=8000, type=int)

    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    library = LibraryPaths(Path(args.library))
    pipeline = Pipeline(library)

    try:
        result = dispatch(args, pipeline, library)
    except KtvError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    except KeyboardInterrupt:
        print("interrupted", file=sys.stderr)
        return 130

    if result is not None:
        print_result(result)
    return 0


def dispatch(args: argparse.Namespace, pipeline: Pipeline, library: LibraryPaths) -> Any:
    if args.command == "import":
        return pipeline.import_source(args.source, song_id=args.song_id, title=args.title, artist=args.artist)
    if args.command == "import-many":
        return [pipeline.import_source(source) for source in args.sources]
    if args.command == "metadata":
        tags = [tag.strip() for tag in args.tags.split(",")] if args.tags is not None else None
        return update_song_metadata(library, args.song_id, title=args.title, artist=args.artist, tags=tags, rating=args.rating)
    if args.command == "rename":
        return rename_song(library, args.old_song_id, args.new_song_id)
    if args.command == "lyrics":
        return {"lyrics_path": str(pipeline.set_lyrics(args.song_id, Path(args.lyrics_path)))}
    if args.command == "list":
        return [song_summary(library, song_id) for song_id in library.list_song_ids()]
    if args.command == "next":
        return next_actions(library, args.song_id)
    if args.command == "preflight":
        return song_preflight(library, args.song_id)
    if args.command == "probe":
        info = pipeline.probe(args.song_id)
        return {
            "duration": info["duration"],
            "video_streams": len(info["video_streams"]),
            "audio_streams": len(info["audio_streams"]),
            "subtitle_streams": len(info["subtitle_streams"]),
        }
    if args.command == "extract":
        return {"mix_wav": str(pipeline.extract(args.song_id, audio_index=args.audio_index))}
    if args.command == "preview-tracks":
        return pipeline.preview_tracks(
            args.song_id,
            duration=args.duration,
            start=args.start,
            count=args.count,
            spacing=args.spacing,
            preset=args.preset,
        )
    if args.command == "separate":
        return pipeline.separate(args.song_id, preset=args.preset, model=args.model, device=args.device)
    if args.command == "separate-sample":
        return pipeline.separate_sample(
            args.song_id,
            audio_index=args.audio_index,
            start=args.start,
            duration=args.duration,
            preset=args.preset,
            model=args.model,
            device=args.device,
        )
    if args.command == "set-instrumental":
        return {
            "instrumental_wav": str(
                pipeline.set_instrumental(
                    args.song_id,
                    Path(args.audio_path),
                    label=args.label,
                    offset=args.offset,
                    gain_db=args.gain_db,
                    fit_to_mix=args.fit_to_mix,
                    normalize=args.normalize,
                )
            )
        }
    if args.command == "track-role":
        return pipeline.set_track_role(args.song_id, audio_index=args.audio_index, role=args.role, note=args.note)
    if args.command == "normalize":
        return {
            "normalized_wav": str(
                pipeline.normalize_instrumental(
                    args.song_id,
                    target_i=args.target_i,
                    replace_current=args.replace_current,
                )
            )
        }
    if args.command == "align":
        result = pipeline.align(args.song_id, backend=args.backend)
        return {
            "backend": result.get("backend"),
            "warning": result.get("warning"),
            "alignment_json": str(library.alignment_json(args.song_id)),
            "lyrics_ass": str(library.lyrics_ass(args.song_id)),
        }
    if args.command == "shift":
        pipeline.shift_subtitles(args.song_id, seconds=args.seconds)
        return {
            "alignment_json": str(library.alignment_json(args.song_id)),
            "lyrics_ass": str(library.lyrics_ass(args.song_id)),
            "subtitle_shift_seconds": args.seconds,
        }
    if args.command == "edit-line":
        result = pipeline.edit_subtitles(
            args.song_id,
            [{"index": args.index, "start": args.start, "end": args.end, "text": args.text}],
        )
        return {"lines": len(result.get("lines") or []), "lyrics_ass": str(library.lyrics_ass(args.song_id))}
    if args.command == "mux":
        return {
            "final_mkv": str(
                pipeline.mux(args.song_id, audio_order=args.audio_order, duration_limit=args.duration_limit)
            )
        }
    if args.command == "mux-plan":
        return pipeline.mux_plan(args.song_id, audio_order=args.audio_order)
    if args.command == "replace-audio":
        return {
            "audio_replaced_mkv": str(
                pipeline.replace_audio(
                    args.song_id,
                    keep_audio_index=args.keep_audio_index,
                    copy_subtitles=not args.no_copy_subtitles,
                    duration_limit=args.duration_limit,
                )
            )
        }
    if args.command == "replace-plan":
        return pipeline.replace_audio_plan(
            args.song_id,
            keep_audio_index=args.keep_audio_index,
            copy_subtitles=not args.no_copy_subtitles,
        )
    if args.command == "remake-track":
        return pipeline.remake_track(
            args.song_id,
            audio_index=args.audio_index,
            keep_audio_index=args.keep_audio_index,
            preset=args.preset,
            model=args.model,
            device=args.device,
            copy_subtitles=not args.no_copy_subtitles,
            duration_limit=args.duration_limit,
        )
    if args.command == "extract-subtitles":
        return {"lyrics_path": str(pipeline.extract_embedded_subtitles(args.song_id, subtitle_index=args.subtitle_index))}
    if args.command == "lyrics-versions":
        return [
            {"filename": path.name, "path": str(path)}
            for path in sorted(library.lyrics_versions_dir(args.song_id).glob("*"))
            if path.is_file()
        ]
    if args.command == "clean-work":
        return pipeline.clean_work(args.song_id)
    if args.command == "takes":
        return list_takes(library, args.song_id)
    if args.command == "take-note":
        update_take(library, args.song_id, args.filename, label=args.label, note=args.note, score=args.score)
        return {"updated": args.filename}
    if args.command == "take-current":
        return {"current": str(set_current_take(library, args.song_id, args.filename))}
    if args.command == "take-delete":
        delete_take(library, args.song_id, args.filename)
        return {"deleted": args.filename}
    if args.command == "export":
        return {
            "package_zip": str(
                export_song_package(
                    library,
                    args.song_id,
                    include_audio=not args.no_audio,
                    include_mkv=not args.no_mkv,
                    include_takes=not args.no_takes,
                    include_logs=args.include_logs,
                )
            )
        }
    if args.command == "inbox-scan":
        return import_inbox(library, pipeline, limit=args.limit)
    if args.command == "storage":
        if args.song_id:
            return song_storage_report(library, args.song_id)
        return library_storage_report(library)
    if args.command == "jobs":
        runner = LocalJobRunner(library, pipeline)
        return [job.to_dict() for job in runner.list_jobs(limit=args.limit)]
    if args.command == "jobs-prune":
        runner = LocalJobRunner(library, pipeline)
        return {"removed": runner.prune_jobs()}
    if args.command == "settings":
        updates = {
            "worker_count": args.worker_count,
            "preview_start": args.preview_start,
            "preview_duration": args.preview_duration,
            "preview_count": args.preview_count,
            "preview_spacing": args.preview_spacing,
            "preview_preset": args.preview_preset,
            "demucs_model": args.demucs_model,
            "demucs_device": args.demucs_device,
            "normalize_target_i": args.normalize_target_i,
            "auto_refresh_seconds": args.auto_refresh_seconds,
            "default_audio_order": args.default_audio_order,
            "default_duration_limit": args.default_duration_limit,
            "output_template": args.output_template,
            "package_include_logs": True if args.package_include_logs else None,
            "subtitle_font_size": args.subtitle_font_size,
            "subtitle_margin_v": args.subtitle_margin_v,
            "subtitle_primary_colour": args.subtitle_primary_colour,
            "subtitle_secondary_colour": args.subtitle_secondary_colour,
            "instrumental_track_title": args.instrumental_track_title,
            "original_track_title": args.original_track_title,
        }
        if any(value is not None for value in updates.values()):
            return save_settings(library, updates)
        return load_settings(library)
    if args.command == "delete":
        delete_song(library, args.song_id)
        return {"deleted": args.song_id}
    if args.command == "process":
        return pipeline.process(args.song_id, align_backend=args.align_backend)
    if args.command == "run-from":
        return pipeline.process_from(
            args.song_id,
            start_stage=args.start_stage,
            align_backend=args.align_backend,
            audio_index=args.audio_index,
            model=args.model,
            device=args.device,
            duration_limit=args.duration_limit,
        )
    if args.command == "batch":
        raw_root = Path(args.root) if args.root else None
        return pipeline.batch(raw_root=raw_root, align_backend=args.align_backend)
    if args.command == "batch-stage":
        raw_root = Path(args.root) if args.root else None
        return pipeline.batch_stage(
            args.stage,
            raw_root=raw_root,
            audio_index=args.audio_index,
            start=args.start,
            duration=args.duration,
            count=args.count,
            spacing=args.spacing,
            preset=args.preset,
            separation_preset=args.separation_preset,
            model=args.model,
            device=args.device,
            limit=args.limit,
            skip_completed=args.skip_completed,
            stop_on_error=args.stop_on_error,
            dry_run=args.dry_run,
        )
    if args.command == "batch-recipe":
        raw_root = Path(args.root) if args.root else None
        return pipeline.batch_recipe(
            args.recipe,
            raw_root=raw_root,
            dry_run=args.dry_run,
            audio_index=args.audio_index,
            keep_audio_index=args.keep_audio_index,
            start=args.start,
            duration=args.duration,
            count=args.count,
            spacing=args.spacing,
            separation_preset=args.separation_preset,
            model=args.model,
            device=args.device,
            align_backend=args.align_backend,
            audio_order=args.audio_order,
            duration_limit=args.duration_limit,
        )
    if args.command == "status":
        return {
            "summary": song_summary(library, args.song_id),
            "status": read_json(library.status_json(args.song_id), default={}),
            "report": read_json(library.report_json(args.song_id), default={}),
        }
    if args.command == "doctor":
        return run_doctor(library, args.song_id)
    if args.command == "serve":
        from .web import serve

        serve(library=library, host=args.host, port=args.port)
        return None
    raise KtvError(f"unknown command: {args.command}")


def print_result(value: Any) -> None:
    print(json.dumps(jsonable(value), ensure_ascii=False, indent=2, sort_keys=True))


def jsonable(value: Any) -> Any:
    if is_dataclass(value):
        return asdict(value)
    if isinstance(value, list):
        return [jsonable(item) for item in value]
    if isinstance(value, dict):
        return {key: jsonable(item) for key, item in value.items()}
    return value


if __name__ == "__main__":
    raise SystemExit(main())
