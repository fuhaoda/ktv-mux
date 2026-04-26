from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from .jsonio import read_json, write_json
from .paths import normalize_song_id


def utc_now() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat()


@dataclass
class Song:
    song_id: str
    title: str | None = None
    artist: str | None = None
    source_path: str | None = None
    lyrics_path: str | None = None
    status: str = "new"
    created_at: str = field(default_factory=utc_now)
    updated_at: str = field(default_factory=utc_now)

    def __post_init__(self) -> None:
        self.song_id = normalize_song_id(self.song_id)

    @classmethod
    def from_json(cls, path: Path) -> Song:
        data = read_json(path)
        if not data:
            raise FileNotFoundError(path)
        return cls(**data)

    def save(self, path: Path) -> None:
        self.updated_at = utc_now()
        write_json(path, asdict(self))


def update_report(path: Path, **values: Any) -> dict[str, Any]:
    report = read_json(path, default={}) or {}
    report.update(values)
    report["updated_at"] = utc_now()
    write_json(path, report)
    return report


def append_stage_status(status_path: Path, stage: str, state: str, message: str = "") -> None:
    data = read_json(status_path, default={}) or {}
    history = data.setdefault("history", [])
    history.append(
        {
            "stage": stage,
            "state": state,
            "message": message,
            "time": utc_now(),
        }
    )
    data["current_stage"] = stage
    data["state"] = state
    data["message"] = message
    data["updated_at"] = utc_now()
    write_json(status_path, data)

