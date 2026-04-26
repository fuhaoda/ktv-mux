import json
import zipfile

from ktv_mux.compatibility import compatibility_report
from ktv_mux.exporter import export_song_package
from ktv_mux.jsonio import write_json
from ktv_mux.library import save_lyrics_file
from ktv_mux.output_templates import render_output_filename
from ktv_mux.paths import LibraryPaths
from ktv_mux.planner import next_actions
from ktv_mux.settings import load_settings, save_settings
from ktv_mux.storage import library_storage_report, song_storage_report


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
            "default_audio_order": "original-first",
            "output_template": "{artist}-{title}.{kind}.mkv",
            "subtitle_font_size": 64,
            "subtitle_margin_v": 80,
            "instrumental_track_title": "Karaoke",
        },
    )
    loaded = load_settings(library)

    assert saved["worker_count"] == 1
    assert loaded["preview_start"] == 12.0
    assert loaded["preview_duration"] == 8.0
    assert saved["preview_count"] == 2
    assert loaded["preview_preset"] == "chorus"
    assert loaded["demucs_device"] == "cpu"
    assert loaded["default_audio_order"] == "original-first"
    assert loaded["output_template"] == "{artist}-{title}.{kind}.mkv"
    assert loaded["subtitle_font_size"] == 64
    assert loaded["subtitle_margin_v"] == 80
    assert loaded["instrumental_track_title"] == "Karaoke"


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


def test_export_song_package_includes_support_bundle(tmp_path):
    library = LibraryPaths(tmp_path / "library")
    library.ensure_song_dirs("song")
    library.report_json("song").write_text("{}", encoding="utf-8")

    package = export_song_package(library, "song")

    with zipfile.ZipFile(package) as archive:
        names = archive.namelist()
        assert "support/doctor.json" in names
        assert "support/settings.json" in names
        assert "support/storage.json" in names
        assert "support/environment.json" in names


def test_storage_reports_song_and_library_sizes(tmp_path):
    library = LibraryPaths(tmp_path / "library")
    library.ensure_song_dirs("song")
    (library.raw_dir("song") / "source.mkv").write_bytes(b"12345")

    song_report = song_storage_report(library, "song")
    library_report = library_storage_report(library)

    assert song_report["total_bytes"] >= 5
    assert library_report["roots"]


def test_output_template_and_compatibility_matrix():
    assert render_output_filename("{artist}-{title}.{kind}.mkv", {"song_id": "id", "artist": "周华健", "title": "朋友", "kind": "ktv"}) == "周华健-朋友.ktv.mkv"
    report = compatibility_report({"ok": True, "audio_streams": 2, "subtitle_streams": 1})
    assert report["recommended_player"]
    assert any(item["player"] == "IINA" for item in report["matrix"])


def test_save_lyrics_file_imports_srt_alignment(tmp_path):
    library = LibraryPaths(tmp_path / "library")
    library.ensure_song_dirs("song")
    srt = tmp_path / "lyrics.srt"
    srt.write_text("1\n00:00:01,000 --> 00:00:03,000\n朋友一生一起走\n", encoding="utf-8")

    save_lyrics_file(library, "song", srt)

    alignment = json.loads(library.alignment_json("song").read_text(encoding="utf-8"))
    assert alignment["backend"] == "srt"
    assert library.lyrics_ass("song").exists()
