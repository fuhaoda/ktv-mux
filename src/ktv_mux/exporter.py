from __future__ import annotations

import json
import platform
import sys
import zipfile
from pathlib import Path

from .diagnostics import run_doctor
from .paths import LibraryPaths, normalize_song_id
from .settings import load_settings
from .storage import library_storage_report


def export_song_package(
    library: LibraryPaths,
    song_id: str,
    *,
    include_audio: bool = True,
    include_mkv: bool = True,
    include_takes: bool = True,
    include_logs: bool = False,
) -> Path:
    clean_id = normalize_song_id(song_id)
    output = library.package_zip(clean_id)
    output.parent.mkdir(parents=True, exist_ok=True)
    candidates = [
        library.song_json(clean_id),
        library.lyrics_txt(clean_id),
        library.status_json(clean_id),
        library.report_json(clean_id),
        library.alignment_json(clean_id),
        library.lyrics_ass(clean_id),
        library.takes_json(clean_id),
    ]
    if include_audio:
        candidates.extend(
            [
                library.mix_wav(clean_id),
                library.vocals_wav(clean_id),
                library.instrumental_wav(clean_id),
                library.normalized_instrumental_wav(clean_id),
            ]
        )
    if include_mkv:
        candidates.extend(
            [
                library.audio_replaced_mkv(clean_id),
                library.final_mkv(clean_id),
            ]
        )
    with zipfile.ZipFile(output, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for path in candidates:
            if path.exists() and path.is_file():
                archive.write(path, path.relative_to(library.root))
        if include_takes:
            for path in sorted(library.takes_dir(clean_id).glob("*")):
                if path.is_file() and path.name != output.name:
                    archive.write(path, path.relative_to(library.root))
        if include_logs:
            for path in sorted((library.work_dir(clean_id) / "logs").glob("*.log")):
                if path.is_file():
                    archive.write(path, path.relative_to(library.root))
        archive.writestr("support/doctor.json", _json_bytes(run_doctor(library, clean_id)))
        archive.writestr("support/settings.json", _json_bytes(load_settings(library)))
        archive.writestr("support/storage.json", _json_bytes(library_storage_report(library)))
        archive.writestr("support/environment.json", _json_bytes(environment_report()))
        archive.writestr(
            "support/README.txt",
            "ktv-mux support bundle\n\n"
            "Attach this ZIP when debugging a song. It contains song metadata, reports, logs when requested, "
            "doctor output, local settings, storage sizes, and environment information.\n",
        )
    return output


def environment_report() -> dict[str, str]:
    return {
        "python": sys.version,
        "platform": platform.platform(),
        "machine": platform.machine(),
        "processor": platform.processor(),
    }


def _json_bytes(value: object) -> str:
    return json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True)
