from __future__ import annotations

import shutil
from pathlib import Path
from typing import Any

from .errors import KtvError
from .jsonio import read_json, write_json
from .models import utc_now
from .paths import LibraryPaths, normalize_song_id


def list_takes(library: LibraryPaths, song_id: str) -> list[dict[str, Any]]:
    clean_id = normalize_song_id(song_id)
    data = _read_takes(library, clean_id)
    items = data.get("items") if isinstance(data.get("items"), dict) else {}
    current = data.get("current") if isinstance(data.get("current"), dict) else {}
    takes = []
    for path in sorted(library.takes_dir(clean_id).glob("*")):
        if not path.is_file() or path.name == "takes.json":
            continue
        meta = dict(items.get(path.name) or {})
        kind = str(meta.get("kind") or take_kind(path.name))
        takes.append(
            {
                "filename": path.name,
                "path": str(path),
                "size_bytes": path.stat().st_size,
                "kind": kind,
                "label": meta.get("label") or "",
                "note": meta.get("note") or "",
                "score": meta.get("score"),
                "created_at": meta.get("created_at") or "",
                "updated_at": meta.get("updated_at") or "",
                "is_current": current.get(kind) == path.name,
            }
        )
    return takes


def record_take(library: LibraryPaths, song_id: str, path: Path, *, label: str = "") -> None:
    clean_id = normalize_song_id(song_id)
    data = _read_takes(library, clean_id)
    items = data.setdefault("items", {})
    now = utc_now()
    items.setdefault(path.name, {})
    items[path.name].update(
        {
            "kind": take_kind(path.name),
            "label": label or items[path.name].get("label") or "",
            "created_at": items[path.name].get("created_at") or now,
            "updated_at": now,
        }
    )
    _write_takes(library, clean_id, data)


def update_take(library: LibraryPaths, song_id: str, filename: str, *, label: str, note: str, score: int | None = None) -> None:
    clean_id = normalize_song_id(song_id)
    path = _take_path(library, clean_id, filename)
    data = _read_takes(library, clean_id)
    items = data.setdefault("items", {})
    item = items.setdefault(path.name, {"kind": take_kind(path.name), "created_at": utc_now()})
    update = {"label": label.strip(), "note": note.strip(), "updated_at": utc_now()}
    if score is not None:
        update["score"] = max(1, min(5, int(score)))
    item.update(update)
    _write_takes(library, clean_id, data)


def delete_take(library: LibraryPaths, song_id: str, filename: str) -> None:
    clean_id = normalize_song_id(song_id)
    path = _take_path(library, clean_id, filename)
    data = _read_takes(library, clean_id)
    kind = take_kind(path.name)
    if path.exists():
        path.unlink()
    items = data.setdefault("items", {})
    items.pop(path.name, None)
    current = data.setdefault("current", {})
    if current.get(kind) == path.name:
        current.pop(kind, None)
    _write_takes(library, clean_id, data)


def set_current_take(library: LibraryPaths, song_id: str, filename: str) -> Path:
    clean_id = normalize_song_id(song_id)
    source = _take_path(library, clean_id, filename)
    kind = take_kind(source.name)
    target = _current_target(library, clean_id, kind)
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source, target)
    data = _read_takes(library, clean_id)
    current = data.setdefault("current", {})
    current[kind] = source.name
    _write_takes(library, clean_id, data)
    return target


def take_kind(filename: str) -> str:
    if ".sample." in filename or filename.startswith("instrumental.sample"):
        return "instrumental-sample"
    if filename.endswith(".wav"):
        return "instrumental"
    if ".audio-replaced." in filename:
        return "audio-replaced"
    if ".ktv." in filename:
        return "ktv"
    return "other"


def _current_target(library: LibraryPaths, song_id: str, kind: str) -> Path:
    if kind == "instrumental":
        return library.instrumental_wav(song_id)
    if kind == "audio-replaced":
        return library.audio_replaced_mkv(song_id)
    if kind == "ktv":
        return library.final_mkv(song_id)
    raise KtvError(f"Cannot set current for take kind: {kind}")


def _take_path(library: LibraryPaths, song_id: str, filename: str) -> Path:
    path = library.takes_dir(song_id) / Path(filename).name
    if not path.exists():
        raise KtvError(f"take not found: {path.name}")
    return path


def _read_takes(library: LibraryPaths, song_id: str) -> dict[str, Any]:
    return read_json(library.takes_json(song_id), default={"items": {}, "current": {}}) or {"items": {}, "current": {}}


def _write_takes(library: LibraryPaths, song_id: str, data: dict[str, Any]) -> None:
    write_json(library.takes_json(song_id), data)
