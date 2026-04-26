from ktv_mux.diagnostics import run_doctor
from ktv_mux.paths import LibraryPaths


def test_doctor_reports_core_checks(tmp_path):
    result = run_doctor(LibraryPaths(tmp_path / "library"))

    names = {check["name"] for check in result["checks"]}
    assert {"python", "ffmpeg", "ffprobe"}.issubset(names)
    assert "library" in result


def test_doctor_song_hint_for_track_failure(tmp_path):
    library = LibraryPaths(tmp_path / "library")
    library.ensure_song_dirs("song")
    library.report_json("song").write_text('{"failure": "Audio Track 3 does not exist."}', encoding="utf-8")

    result = run_doctor(library, "song")

    assert "choose an existing source audio track" in result["song"]["next_hint"]
