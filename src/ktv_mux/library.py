from __future__ import annotations

import hashlib
import shutil
from pathlib import Path
from typing import Any

from .commands import require_command, run_command, run_command_logged
from .errors import KtvError
from .jsonio import read_json, write_json
from .lyrics import lrc_text_to_alignment, normalize_lyrics_text
from .models import Song, update_report
from .paths import LibraryPaths, derive_song_id_from_source, is_url, normalize_song_id


def build_ytdlp_cmd(url: str, raw_dir: Path) -> list[str]:
    return [
        "yt-dlp",
        "--no-playlist",
        "--write-info-json",
        "--merge-output-format",
        "mkv",
        "-o",
        str(raw_dir / "source.%(ext)s"),
        url,
    ]


def import_source(
    path_or_url: str,
    *,
    song_id: str | None = None,
    library: LibraryPaths,
    title: str | None = None,
    artist: str | None = None,
    log_path: Path | None = None,
    cancel_file: Path | None = None,
) -> Song:
    clean_id = normalize_song_id(song_id) if song_id else derive_song_id_from_source(path_or_url)
    library.ensure_song_dirs(clean_id)
    raw_dir = library.raw_dir(clean_id)

    if is_url(path_or_url):
        require_command("yt-dlp")
        cmd = build_ytdlp_cmd(path_or_url, raw_dir)
        if log_path is not None:
            run_command_logged(cmd, log_path=log_path, cancel_file=cancel_file)
        else:
            run_command(cmd, cancel_file=cancel_file)
        source = _find_downloaded_source(library, clean_id)
    else:
        source_input = Path(path_or_url).expanduser()
        if not source_input.exists():
            raise KtvError(f"source file does not exist: {source_input}")
        dest = raw_dir / f"source{source_input.suffix.lower() or '.media'}"
        if source_input.resolve() != dest.resolve():
            shutil.copy2(source_input, dest)
        source = dest

    return record_imported_source(
        library,
        clean_id,
        source,
        title=title,
        artist=artist,
    )


def record_imported_source(
    library: LibraryPaths,
    song_id: str,
    source: Path,
    *,
    title: str | None = None,
    artist: str | None = None,
) -> Song:
    clean_id = normalize_song_id(song_id)
    existing = read_json(library.song_json(clean_id), default=None)
    song = Song(**existing) if existing else Song(song_id=clean_id)
    song.title = title or song.title
    song.artist = artist or song.artist
    song.source_path = str(source)
    if library.lyrics_txt(clean_id).exists():
        song.lyrics_path = str(library.lyrics_txt(clean_id))
    song.status = "imported"
    song.save(library.song_json(clean_id))
    duplicates = duplicate_sources(library, source, exclude_song_id=clean_id)
    update_report(
        library.report_json(clean_id),
        source_fingerprint=file_fingerprint(source),
        duplicate_sources=duplicates,
    )
    return song


def update_song_metadata(
    library: LibraryPaths,
    song_id: str,
    *,
    title: str | None = None,
    artist: str | None = None,
) -> Song:
    clean_id = normalize_song_id(song_id)
    try:
        song = load_song(library, clean_id)
    except FileNotFoundError:
        song = Song(song_id=clean_id)
    song.title = title if title is not None else song.title
    song.artist = artist if artist is not None else song.artist
    song.save(library.song_json(clean_id))
    return song


def rename_song(library: LibraryPaths, old_song_id: str, new_song_id: str) -> Song:
    old_id = normalize_song_id(old_song_id)
    new_id = normalize_song_id(new_song_id)
    if old_id == new_id:
        return load_song(library, old_id)
    if library.raw_dir(new_id).exists() or library.work_dir(new_id).exists() or library.output_dir(new_id).exists():
        raise KtvError(f"song_id already exists: {new_id}")
    for old_dir, new_dir in [
        (library.raw_dir(old_id), library.raw_dir(new_id)),
        (library.work_dir(old_id), library.work_dir(new_id)),
        (library.output_dir(old_id), library.output_dir(new_id)),
    ]:
        if old_dir.exists():
            new_dir.parent.mkdir(parents=True, exist_ok=True)
            shutil.move(str(old_dir), str(new_dir))
    library.ensure_song_dirs(new_id)

    try:
        song = load_song(library, new_id)
    except FileNotFoundError:
        song = Song(song_id=new_id)
    song.song_id = new_id
    if library.source_candidates(new_id):
        song.source_path = str(library.source_path(new_id))
    if library.lyrics_txt(new_id).exists():
        song.lyrics_path = str(library.lyrics_txt(new_id))
    song.save(library.song_json(new_id))

    if library.jobs_root.exists():
        for job_path in library.jobs_root.glob("*.json"):
            data = read_json(job_path, default={}) or {}
            if data.get("song_id") == old_id:
                data["song_id"] = new_id
                write_json(job_path, data)
    return song


def _find_downloaded_source(library: LibraryPaths, song_id: str) -> Path:
    candidates = library.source_candidates(song_id)
    if not candidates:
        raise KtvError("yt-dlp completed but no source media was found")
    candidates.sort(key=lambda p: p.stat().st_size, reverse=True)
    return candidates[0]


def load_song(library: LibraryPaths, song_id: str) -> Song:
    return Song.from_json(library.song_json(song_id))


def save_lyrics_text(library: LibraryPaths, song_id: str, lyrics_text: str, *, clean: bool = True) -> Path:
    clean_id = normalize_song_id(song_id)
    library.ensure_song_dirs(clean_id)
    path = library.lyrics_txt(clean_id)
    text = normalize_lyrics_text(lyrics_text) if clean else lyrics_text.rstrip()
    path.write_text(text + "\n", encoding="utf-8")
    alignment = lrc_text_to_alignment(lyrics_text) if clean else {"lines": []}
    if alignment.get("lines"):
        write_json(library.alignment_json(clean_id), alignment)

    try:
        song = load_song(library, clean_id)
    except FileNotFoundError:
        song = Song(song_id=clean_id)
    song.lyrics_path = str(path)
    if song.status == "new":
        song.status = "lyrics_added"
    song.save(library.song_json(clean_id))
    return path


def save_lyrics_file(library: LibraryPaths, song_id: str, source_path: Path) -> Path:
    clean_id = normalize_song_id(song_id)
    library.ensure_song_dirs(clean_id)
    data = source_path.read_bytes()
    text, encoding, warnings = decode_lyrics_bytes(data)
    original = library.original_lyrics_file(clean_id, source_path.suffix or ".txt")
    original.write_bytes(data)
    path = save_lyrics_text(library, clean_id, text)
    report = read_json(library.report_json(clean_id), default={}) or {}
    report["lyrics_import"] = {
        "source": str(source_path),
        "original_copy": str(original),
        "encoding": encoding,
        "warnings": warnings,
    }
    write_json(library.report_json(clean_id), report)
    return path


def decode_lyrics_bytes(data: bytes) -> tuple[str, str, list[str]]:
    warnings: list[str] = []
    encodings = ["utf-8-sig", "gb18030", "big5"]
    if data.startswith((b"\xff\xfe", b"\xfe\xff")):
        encodings.insert(1, "utf-16")
    for encoding in encodings:
        try:
            text = data.decode(encoding)
            if encoding != "utf-8-sig":
                warnings.append(f"Decoded lyrics as {encoding}.")
            return text, encoding, warnings
        except UnicodeDecodeError:
            continue
    warnings.append("Lyrics encoding was not recognized; invalid characters were replaced.")
    return data.decode("utf-8", errors="replace"), "utf-8-replace", warnings


def file_fingerprint(path: Path, *, head_bytes: int = 16 * 1024 * 1024) -> dict[str, Any]:
    digest = hashlib.sha256()
    size = path.stat().st_size
    with path.open("rb") as handle:
        digest.update(handle.read(head_bytes))
    return {"size_bytes": size, "sha256_head": digest.hexdigest(), "head_bytes": head_bytes}


def duplicate_sources(library: LibraryPaths, source: Path, *, exclude_song_id: str | None = None) -> list[dict[str, str]]:
    source_fp = file_fingerprint(source)
    exclude = normalize_song_id(exclude_song_id) if exclude_song_id else None
    duplicates: list[dict[str, str]] = []
    for song_id in library.list_song_ids():
        if exclude and normalize_song_id(song_id) == exclude:
            continue
        for candidate in library.source_candidates(song_id):
            try:
                candidate_fp = file_fingerprint(candidate)
            except OSError:
                continue
            if (
                candidate_fp["size_bytes"] == source_fp["size_bytes"]
                and candidate_fp["sha256_head"] == source_fp["sha256_head"]
            ):
                duplicates.append({"song_id": song_id, "path": str(candidate)})
    return duplicates


def delete_song(library: LibraryPaths, song_id: str) -> None:
    clean_id = normalize_song_id(song_id)
    for path in [library.raw_dir(clean_id), library.work_dir(clean_id), library.output_dir(clean_id)]:
        if path.exists():
            shutil.rmtree(path)
    if library.jobs_root.exists():
        for job_path in library.jobs_root.glob("*.json"):
            data = read_json(job_path, default={}) or {}
            if data.get("song_id") == clean_id:
                job_path.unlink()
                cancel_path = library.job_cancel_file(job_path.stem)
                if cancel_path.exists():
                    cancel_path.unlink()


def song_summary(library: LibraryPaths, song_id: str) -> dict[str, Any]:
    summary: dict[str, Any] = {"song_id": song_id}
    song_path = library.song_json(song_id)
    if song_path.exists():
        summary.update(read_json(song_path, default={}) or {})
    summary["has_source"] = bool(library.source_candidates(song_id))
    summary["has_lyrics"] = library.lyrics_txt(song_id).exists()
    summary["has_mix"] = library.mix_wav(song_id).exists()
    summary["has_vocals"] = library.vocals_wav(song_id).exists()
    summary["has_instrumental"] = library.instrumental_wav(song_id).exists()
    summary["has_normalized_instrumental"] = library.normalized_instrumental_wav(song_id).exists()
    summary["has_alignment"] = library.alignment_json(song_id).exists()
    summary["has_ass"] = library.lyrics_ass(song_id).exists()
    summary["has_mkv"] = library.final_mkv(song_id).exists()
    summary["has_audio_replaced_mkv"] = library.audio_replaced_mkv(song_id).exists()
    summary["take_files"] = [
        path.name for path in sorted(library.takes_dir(song_id).glob("*")) if path.is_file() and path.name != "takes.json"
    ]
    summary["track_previews"] = [
        path.name for path in sorted(library.previews_dir(song_id).glob("track-*.wav")) if path.is_file()
    ]
    return summary
