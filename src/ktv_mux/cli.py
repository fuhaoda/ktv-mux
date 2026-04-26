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
from .library import delete_song, song_summary, update_song_metadata
from .paths import LibraryPaths
from .pipeline import Pipeline
from .planner import next_actions
from .settings import load_settings, save_settings
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

    lyrics_p = sub.add_parser("lyrics", help="copy lyrics text into the song folder")
    lyrics_p.add_argument("song_id")
    lyrics_p.add_argument("lyrics_path")

    sub.add_parser("list", help="list known songs")

    next_p = sub.add_parser("next", help="show suggested next actions for a song")
    next_p.add_argument("song_id")

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

    separate_p = sub.add_parser("separate", help="separate vocals from accompaniment")
    separate_p.add_argument("song_id")
    separate_p.add_argument("--model", default="htdemucs")

    align_p = sub.add_parser("align", help="align lyrics and generate ASS")
    align_p.add_argument("song_id")
    align_p.add_argument("--backend", default="auto", choices=["auto", "funasr", "simple"])

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

    clean_p = sub.add_parser("clean-work", help="remove regenerable work files for one song")
    clean_p.add_argument("song_id")

    takes_p = sub.add_parser("takes", help="list saved output takes for one song")
    takes_p.add_argument("song_id")

    take_note_p = sub.add_parser("take-note", help="edit a saved output take label/note")
    take_note_p.add_argument("song_id")
    take_note_p.add_argument("filename")
    take_note_p.add_argument("--label", default="")
    take_note_p.add_argument("--note", default="")

    take_current_p = sub.add_parser("take-current", help="promote a saved take to the stable output filename")
    take_current_p.add_argument("song_id")
    take_current_p.add_argument("filename")

    take_delete_p = sub.add_parser("take-delete", help="delete a saved output take")
    take_delete_p.add_argument("song_id")
    take_delete_p.add_argument("filename")

    export_p = sub.add_parser("export", help="zip current song outputs and reports")
    export_p.add_argument("song_id")

    jobs_p = sub.add_parser("jobs", help="list local Web jobs")
    jobs_p.add_argument("--limit", type=int, default=25)

    sub.add_parser("jobs-prune", help="delete completed, failed, and canceled local Web jobs")

    settings_p = sub.add_parser("settings", help="show or update local defaults")
    settings_p.add_argument("--worker-count", type=int)
    settings_p.add_argument("--preview-start", type=float)
    settings_p.add_argument("--preview-duration", type=float)
    settings_p.add_argument("--auto-refresh-seconds", type=int)

    delete_p = sub.add_parser("delete", help="delete raw/work/output folders for one song")
    delete_p.add_argument("song_id")

    process_p = sub.add_parser("process", help="run probe/extract/separate/align/mux")
    process_p.add_argument("song_id")
    process_p.add_argument("--align-backend", default="auto", choices=["auto", "funasr", "simple"])

    batch_p = sub.add_parser("batch", help="process every raw song folder")
    batch_p.add_argument("--root", default=None, help="raw root, defaults to library/raw")
    batch_p.add_argument("--align-backend", default="auto", choices=["auto", "funasr", "simple"])

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
        return update_song_metadata(library, args.song_id, title=args.title, artist=args.artist)
    if args.command == "lyrics":
        return {"lyrics_path": str(pipeline.set_lyrics(args.song_id, Path(args.lyrics_path)))}
    if args.command == "list":
        return [song_summary(library, song_id) for song_id in library.list_song_ids()]
    if args.command == "next":
        return next_actions(library, args.song_id)
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
        return pipeline.preview_tracks(args.song_id, duration=args.duration, start=args.start)
    if args.command == "separate":
        return pipeline.separate(args.song_id, model=args.model)
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
    if args.command == "clean-work":
        return pipeline.clean_work(args.song_id)
    if args.command == "takes":
        return list_takes(library, args.song_id)
    if args.command == "take-note":
        update_take(library, args.song_id, args.filename, label=args.label, note=args.note)
        return {"updated": args.filename}
    if args.command == "take-current":
        return {"current": str(set_current_take(library, args.song_id, args.filename))}
    if args.command == "take-delete":
        delete_take(library, args.song_id, args.filename)
        return {"deleted": args.filename}
    if args.command == "export":
        return {"package_zip": str(export_song_package(library, args.song_id))}
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
            "auto_refresh_seconds": args.auto_refresh_seconds,
        }
        if any(value is not None for value in updates.values()):
            return save_settings(library, updates)
        return load_settings(library)
    if args.command == "delete":
        delete_song(library, args.song_id)
        return {"deleted": args.song_id}
    if args.command == "process":
        return pipeline.process(args.song_id, align_backend=args.align_backend)
    if args.command == "batch":
        raw_root = Path(args.root) if args.root else None
        return pipeline.batch(raw_root=raw_root, align_backend=args.align_backend)
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
