import zipfile

from ktv_mux.exporter import export_song_package
from ktv_mux.jsonio import write_json
from ktv_mux.paths import LibraryPaths
from ktv_mux.planner import next_actions
from ktv_mux.settings import load_settings, save_settings


def test_settings_are_persisted_and_sanitized(tmp_path):
    library = LibraryPaths(tmp_path / "library")

    saved = save_settings(
        library,
        {
            "worker_count": 0,
            "preview_start": 12,
            "preview_duration": 8,
            "preview_count": 2,
            "preview_preset": "chorus",
            "demucs_device": "cpu",
        },
    )
    loaded = load_settings(library)

    assert saved["worker_count"] == 1
    assert loaded["preview_start"] == 12.0
    assert loaded["preview_duration"] == 8.0
    assert saved["preview_count"] == 2
    assert loaded["preview_preset"] == "chorus"
    assert loaded["demucs_device"] == "cpu"


def test_next_actions_progress_with_song_files(tmp_path):
    library = LibraryPaths(tmp_path / "library")
    library.ensure_song_dirs("song")

    assert next_actions(library, "song")[0]["stage"] == "import"

    (library.raw_dir("song") / "source.mkv").write_bytes(b"source")
    assert next_actions(library, "song")[0]["stage"] == "probe"

    write_json(library.report_json("song"), {"probe": {"streams": []}})
    library.mix_wav("song").write_bytes(b"mix")
    library.instrumental_wav("song").write_bytes(b"instrumental")
    stages = [item["stage"] for item in next_actions(library, "song")]
    assert "lyrics" in stages
    assert "replace-audio" in stages


def test_export_song_package_includes_outputs_and_reports(tmp_path):
    library = LibraryPaths(tmp_path / "library")
    library.ensure_song_dirs("song")
    library.instrumental_wav("song").write_bytes(b"instrumental")
    library.report_json("song").write_text("{}", encoding="utf-8")

    package = export_song_package(library, "song")

    assert package.exists()
    with zipfile.ZipFile(package) as archive:
        assert "output/song/instrumental.wav" in archive.namelist()
        assert "output/song/report.json" in archive.namelist()


def test_export_song_package_can_exclude_audio_and_include_logs(tmp_path):
    library = LibraryPaths(tmp_path / "library")
    library.ensure_song_dirs("song")
    library.instrumental_wav("song").write_bytes(b"instrumental")
    library.stage_log("song", "separate").write_text("log", encoding="utf-8")

    package = export_song_package(library, "song", include_audio=False, include_logs=True)

    with zipfile.ZipFile(package) as archive:
        names = archive.namelist()
        assert "output/song/instrumental.wav" not in names
        assert "work/song/logs/separate.log" in names
