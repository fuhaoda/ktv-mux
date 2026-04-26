from __future__ import annotations

from pathlib import Path
from typing import Any

from .paths import LibraryPaths, normalize_song_id


def directory_size(path: Path) -> int:
    if not path.exists():
        return 0
    if path.is_file():
        return path.stat().st_size
    total = 0
    for child in path.rglob("*"):
        if child.is_file():
            total += child.stat().st_size
    return total


def human_bytes(size: int | float) -> str:
    value = float(size)
    for unit in ["B", "KB", "MB", "GB", "TB"]:
        if value < 1024 or unit == "TB":
            if unit == "B":
                return f"{int(value)} {unit}"
            return f"{value:.1f} {unit}"
        value /= 1024
    return f"{value:.1f} TB"


def song_storage_report(library: LibraryPaths, song_id: str) -> dict[str, Any]:
    clean_id = normalize_song_id(song_id)
    sections = {
        "raw": library.raw_dir(clean_id),
        "work": library.work_dir(clean_id),
        "output": library.output_dir(clean_id),
        "takes": library.takes_dir(clean_id),
    }
    rows = []
    for name, path in sections.items():
        size = directory_size(path)
        rows.append({"name": name, "path": str(path), "size_bytes": size, "size": human_bytes(size)})
    total = sum(int(row["size_bytes"]) for row in rows)
    return {"song_id": clean_id, "sections": rows, "total_bytes": total, "total": human_bytes(total)}


def library_storage_report(library: LibraryPaths) -> dict[str, Any]:
    roots = {
        "raw": library.raw_root,
        "work": library.work_root,
        "output": library.output_root,
        "jobs": library.jobs_root,
        "inbox": library.inbox_dir,
    }
    root_rows = []
    for name, path in roots.items():
        size = directory_size(path)
        root_rows.append({"name": name, "path": str(path), "size_bytes": size, "size": human_bytes(size)})

    songs = [song_storage_report(library, song_id) for song_id in library.list_song_ids()]
    songs.sort(key=lambda item: int(item["total_bytes"]), reverse=True)
    total = sum(int(row["size_bytes"]) for row in root_rows)
    return {"root": str(library.root), "total_bytes": total, "total": human_bytes(total), "roots": root_rows, "songs": songs}
