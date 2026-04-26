from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import unquote, urlparse

from .errors import KtvError

_SEPARATOR_RE = re.compile(r"[\\/:\0]+")
_SPACE_RE = re.compile(r"\s+")


def normalize_song_id(value: str) -> str:
    song_id = _SPACE_RE.sub("-", value.strip())
    song_id = _SEPARATOR_RE.sub("-", song_id)
    song_id = song_id.strip(".- ")
    if not song_id:
        raise KtvError("song_id cannot be empty")
    if song_id in {".", ".."}:
        raise KtvError(f"invalid song_id: {value!r}")
    return song_id


def is_url(value: str) -> bool:
    lowered = value.lower()
    return lowered.startswith("http://") or lowered.startswith("https://")


def derive_song_id_from_source(path_or_url: str, fallback: str = "download") -> str:
    if is_url(path_or_url):
        parsed = urlparse(path_or_url)
        candidate = Path(unquote(parsed.path)).stem or parsed.netloc or fallback
    else:
        candidate = Path(path_or_url).expanduser().stem or fallback
    return normalize_song_id(candidate)


@dataclass(frozen=True)
class LibraryPaths:
    root: Path = Path("library")

    def __post_init__(self) -> None:
        object.__setattr__(self, "root", Path(self.root))

    @property
    def raw_root(self) -> Path:
        return self.root / "raw"

    @property
    def work_root(self) -> Path:
        return self.root / "work"

    @property
    def output_root(self) -> Path:
        return self.root / "output"

    @property
    def jobs_root(self) -> Path:
        return self.root / "jobs"

    def raw_dir(self, song_id: str) -> Path:
        return self.raw_root / normalize_song_id(song_id)

    def work_dir(self, song_id: str) -> Path:
        return self.work_root / normalize_song_id(song_id)

    def output_dir(self, song_id: str) -> Path:
        return self.output_root / normalize_song_id(song_id)

    def takes_dir(self, song_id: str) -> Path:
        return self.output_dir(song_id) / "takes"

    def song_json(self, song_id: str) -> Path:
        return self.raw_dir(song_id) / "song.json"

    def lyrics_txt(self, song_id: str) -> Path:
        return self.raw_dir(song_id) / "lyrics.txt"

    def source_candidates(self, song_id: str) -> list[Path]:
        raw = self.raw_dir(song_id)
        ignored_suffixes = {".json", ".txt", ".part", ".ytdl"}
        return sorted(
            p
            for p in raw.glob("source.*")
            if p.is_file() and p.suffix.lower() not in ignored_suffixes
        )

    def source_path(self, song_id: str) -> Path:
        candidates = self.source_candidates(song_id)
        if not candidates:
            raise KtvError(f"no source media found for song_id={song_id!r}")
        return candidates[0]

    def mix_wav(self, song_id: str) -> Path:
        return self.work_dir(song_id) / "mix.wav"

    def vocals_wav(self, song_id: str) -> Path:
        return self.work_dir(song_id) / "vocals.wav"

    def previews_dir(self, song_id: str) -> Path:
        return self.work_dir(song_id) / "track-previews"

    def track_preview_wav(self, song_id: str, audio_index: int, segment_index: int = 0) -> Path:
        suffix = "" if segment_index <= 0 else f"-{segment_index + 1}"
        return self.previews_dir(song_id) / f"track-{audio_index + 1}{suffix}.wav"

    def instrumental_wav(self, song_id: str) -> Path:
        return self.output_dir(song_id) / "instrumental.wav"

    def normalized_instrumental_wav(self, song_id: str) -> Path:
        return self.output_dir(song_id) / "instrumental.normalized.wav"

    def original_lyrics_file(self, song_id: str, suffix: str = ".txt") -> Path:
        return self.raw_dir(song_id) / f"lyrics.original{suffix or '.txt'}"

    def alignment_json(self, song_id: str) -> Path:
        return self.work_dir(song_id) / "alignment.json"

    def lyrics_ass(self, song_id: str) -> Path:
        return self.output_dir(song_id) / "lyrics.ass"

    def final_mkv(self, song_id: str) -> Path:
        clean_id = normalize_song_id(song_id)
        return self.output_dir(clean_id) / f"{clean_id}.ktv.mkv"

    def audio_replaced_mkv(self, song_id: str) -> Path:
        clean_id = normalize_song_id(song_id)
        return self.output_dir(clean_id) / f"{clean_id}.audio-replaced.mkv"

    def report_json(self, song_id: str) -> Path:
        return self.output_dir(song_id) / "report.json"

    def status_json(self, song_id: str) -> Path:
        return self.work_dir(song_id) / "status.json"

    def checkpoints_json(self, song_id: str) -> Path:
        return self.work_dir(song_id) / "checkpoints.json"

    def stage_log(self, song_id: str, stage: str) -> Path:
        return self.work_dir(song_id) / "logs" / f"{normalize_song_id(stage)}.log"

    def lock_file(self, song_id: str) -> Path:
        return self.work_dir(song_id) / ".lock"

    def job_json(self, job_id: str) -> Path:
        return self.jobs_root / f"{job_id}.json"

    def job_cancel_file(self, job_id: str) -> Path:
        return self.jobs_root / f"{job_id}.cancel"

    def settings_json(self) -> Path:
        return self.root / "settings.json"

    def takes_json(self, song_id: str) -> Path:
        return self.takes_dir(song_id) / "takes.json"

    def package_zip(self, song_id: str) -> Path:
        clean_id = normalize_song_id(song_id)
        return self.output_dir(clean_id) / f"{clean_id}.package.zip"

    def ensure_song_dirs(self, song_id: str) -> None:
        self.raw_dir(song_id).mkdir(parents=True, exist_ok=True)
        self.work_dir(song_id).mkdir(parents=True, exist_ok=True)
        self.output_dir(song_id).mkdir(parents=True, exist_ok=True)
        (self.work_dir(song_id) / "logs").mkdir(parents=True, exist_ok=True)
        self.takes_dir(song_id).mkdir(parents=True, exist_ok=True)
        self.previews_dir(song_id).mkdir(parents=True, exist_ok=True)

    def list_song_ids(self) -> list[str]:
        if not self.raw_root.exists():
            return []
        return sorted(p.name for p in self.raw_root.iterdir() if p.is_dir())
