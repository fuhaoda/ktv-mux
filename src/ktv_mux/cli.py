from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from .errors import KtvError
from .jsonio import read_json
from .library import song_summary
from .paths import LibraryPaths
from .pipeline import Pipeline


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="ktv", description="KTV MKV production pipeline")
    parser.add_argument("--library", default="library", help="library root directory")
    sub = parser.add_subparsers(dest="command", required=True)

    import_p = sub.add_parser("import", help="import a local media file or URL")
    import_p.add_argument("source", help="local path or URL")
    import_p.add_argument("--song-id", help="optional; defaults to the source filename")
    import_p.add_argument("--title")
    import_p.add_argument("--artist")

    lyrics_p = sub.add_parser("lyrics", help="copy lyrics text into the song folder")
    lyrics_p.add_argument("song_id")
    lyrics_p.add_argument("lyrics_path")

    sub.add_parser("list", help="list known songs")

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

    separate_p = sub.add_parser("separate", help="separate vocals from accompaniment")
    separate_p.add_argument("song_id")
    separate_p.add_argument("--model", default="htdemucs")

    align_p = sub.add_parser("align", help="align lyrics and generate ASS")
    align_p.add_argument("song_id")
    align_p.add_argument("--backend", default="auto", choices=["auto", "funasr", "simple"])

    mux_p = sub.add_parser("mux", help="mux final dual-audio MKV")
    mux_p.add_argument("song_id")
    mux_p.add_argument(
        "--audio-order",
        default="instrumental-first",
        choices=["instrumental-first", "original-first"],
        help="instrumental-first makes accompaniment track 1; original-first keeps original mix as track 1",
    )

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

    process_p = sub.add_parser("process", help="run probe/extract/separate/align/mux")
    process_p.add_argument("song_id")
    process_p.add_argument("--align-backend", default="auto", choices=["auto", "funasr", "simple"])

    batch_p = sub.add_parser("batch", help="process every raw song folder")
    batch_p.add_argument("--root", default=None, help="raw root, defaults to library/raw")
    batch_p.add_argument("--align-backend", default="auto", choices=["auto", "funasr", "simple"])

    status_p = sub.add_parser("status", help="show song status")
    status_p.add_argument("song_id")

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
    if args.command == "lyrics":
        return {"lyrics_path": str(pipeline.set_lyrics(args.song_id, Path(args.lyrics_path)))}
    if args.command == "list":
        return [song_summary(library, song_id) for song_id in library.list_song_ids()]
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
    if args.command == "mux":
        return {"final_mkv": str(pipeline.mux(args.song_id, audio_order=args.audio_order))}
    if args.command == "replace-audio":
        return {
            "audio_replaced_mkv": str(
                pipeline.replace_audio(
                    args.song_id,
                    keep_audio_index=args.keep_audio_index,
                    copy_subtitles=not args.no_copy_subtitles,
                )
            )
        }
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
    if args.command == "serve":
        from .web import serve

        serve(library=library, host=args.host, port=args.port)
        return None
    raise KtvError(f"unknown command: {args.command}")


def print_result(value: Any) -> None:
    if hasattr(value, "__dataclass_fields__"):
        from dataclasses import asdict

        value = asdict(value)
    print(json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True))


if __name__ == "__main__":
    raise SystemExit(main())
