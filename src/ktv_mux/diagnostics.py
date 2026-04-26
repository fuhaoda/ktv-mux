from __future__ import annotations

import importlib.util
import shutil
import sys
from typing import Any

from .jsonio import read_json
from .paths import LibraryPaths, normalize_song_id


def run_doctor(library: LibraryPaths, song_id: str | None = None) -> dict[str, Any]:
    checks = [
        _check_python(),
        _check_command("ffmpeg"),
        _check_command("ffprobe"),
        _check_command("yt-dlp", required=False),
        _check_package("demucs", required=False),
        _check_package("torchcodec", required=False),
        _check_package("funasr", required=False),
    ]
    result: dict[str, Any] = {
        "ok": all(check["ok"] or not check["required"] for check in checks),
        "checks": checks,
        "library": {
            "root": str(library.root),
            "raw_exists": library.raw_root.exists(),
            "work_exists": library.work_root.exists(),
            "output_exists": library.output_root.exists(),
        },
    }
    if song_id:
        result["song"] = _song_diagnostics(library, song_id)
    return result


def _check_python() -> dict[str, Any]:
    ok = sys.version_info[:2] == (3, 12)
    return {
        "name": "python",
        "ok": ok,
        "required": True,
        "detail": f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}",
        "hint": "Use Python 3.12 for the audio ML stack." if not ok else "",
        "fix": "python3.12 -m venv .venv && .venv/bin/python -m pip install -U pip && .venv/bin/pip install -e '.[web,dev]'"
        if not ok
        else "",
    }


def _check_command(name: str, *, required: bool = True) -> dict[str, Any]:
    path = shutil.which(name)
    fix = ""
    if not path:
        fix = {
            "ffmpeg": "brew install ffmpeg",
            "ffprobe": "brew install ffmpeg",
            "yt-dlp": "brew install yt-dlp",
        }.get(name, f"Install {name} and make sure it is on PATH.")
    return {
        "name": name,
        "ok": bool(path),
        "required": required,
        "detail": path or "not found",
        "hint": f"Install {name} and make sure it is on PATH." if required and not path else "",
        "fix": fix,
    }


def _check_package(name: str, *, required: bool = True) -> dict[str, Any]:
    found = importlib.util.find_spec(name) is not None
    extra = "ml" if name == "funasr" else "separation"
    return {
        "name": name,
        "ok": found,
        "required": required,
        "detail": "installed" if found else "not installed",
        "hint": f'Install with: python -m pip install -e ".[{extra}]"' if not found else "",
        "fix": f'.venv/bin/pip install -e ".[{extra}]"' if not found else "",
    }


def _song_diagnostics(library: LibraryPaths, song_id: str) -> dict[str, Any]:
    clean_id = normalize_song_id(song_id)
    status = read_json(library.status_json(clean_id), default={}) or {}
    report = read_json(library.report_json(clean_id), default={}) or {}
    return {
        "song_id": clean_id,
        "has_source": bool(library.source_candidates(clean_id)),
        "has_mix": library.mix_wav(clean_id).exists(),
        "has_instrumental": library.instrumental_wav(clean_id).exists(),
        "has_ass": library.lyrics_ass(clean_id).exists(),
        "state": status.get("state"),
        "current_stage": status.get("current_stage"),
        "failure": report.get("failure"),
        "failed_stage": report.get("failed_stage"),
        "next_hint": _next_hint(status, report),
    }


def _next_hint(status: dict[str, Any], report: dict[str, Any]) -> str:
    failure = str(report.get("failure") or status.get("message") or "")
    if "ffmpeg" in failure or "ffprobe" in failure:
        return "Install FFmpeg and rerun the failed stage."
    if "Audio Track" in failure:
        return "Run probe and choose an existing source audio track."
    if "Demucs" in failure or "demucs" in failure or "torchcodec" in failure:
        return 'Install or refresh separation dependencies with: python -m pip install -e ".[separation]"'
    if "lyrics" in failure:
        return "Add or clean lyrics.txt, then rerun align."
    return ""
