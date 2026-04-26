from __future__ import annotations

import shutil
from pathlib import Path
from typing import Any

from .commands import require_command, run_command
from .errors import KtvError
from .jsonio import read_json
from .models import Song
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
) -> Song:
    clean_id = normalize_song_id(song_id) if song_id else derive_song_id_from_source(path_or_url)
    library.ensure_song_dirs(clean_id)
    raw_dir = library.raw_dir(clean_id)

    if is_url(path_or_url):
        require_command("yt-dlp")
        run_command(build_ytdlp_cmd(path_or_url, raw_dir))
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
    return song


def _find_downloaded_source(library: LibraryPaths, song_id: str) -> Path:
    candidates = library.source_candidates(song_id)
    if not candidates:
        raise KtvError("yt-dlp completed but no source media was found")
    candidates.sort(key=lambda p: p.stat().st_size, reverse=True)
    return candidates[0]


def load_song(library: LibraryPaths, song_id: str) -> Song:
    return Song.from_json(library.song_json(song_id))


def save_lyrics_text(library: LibraryPaths, song_id: str, lyrics_text: str) -> Path:
    clean_id = normalize_song_id(song_id)
    library.ensure_song_dirs(clean_id)
    path = library.lyrics_txt(clean_id)
    path.write_text(lyrics_text.rstrip() + "\n", encoding="utf-8")

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
    text = source_path.read_text(encoding="utf-8")
    return save_lyrics_text(library, song_id, text)


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
    summary["has_alignment"] = library.alignment_json(song_id).exists()
    summary["has_ass"] = library.lyrics_ass(song_id).exists()
    summary["has_mkv"] = library.final_mkv(song_id).exists()
    summary["has_audio_replaced_mkv"] = library.audio_replaced_mkv(song_id).exists()
    return summary
