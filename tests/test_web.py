from fastapi.testclient import TestClient

from ktv_mux.paths import LibraryPaths
from ktv_mux.web import create_app


def test_index_makes_song_id_optional(tmp_path):
    client = TestClient(create_app(LibraryPaths(tmp_path / "library")))
    response = client.get("/")
    assert response.status_code == 200
    assert "Song ID optional" in response.text
    assert "Choose File" in response.text
    assert "First Run Wizard" in response.text
    assert "Import Bundled Sample" in response.text
    assert "Batch Console" in response.text
    assert "Single Module Launcher" in response.text
    assert "Track Review" in response.text
    assert "我确认自己有权处理" in response.text
    assert "Inbox Auto-Import" in response.text
    assert "Search & Filter" in response.text
    assert "Recent Jobs" in response.text
    assert "Doctor" in response.text
    assert "Settings" in response.text
    assert "Storage" in response.text
    assert "/static/style.css" in response.text


def test_upload_defaults_song_id_to_filename(tmp_path):
    library = LibraryPaths(tmp_path / "library")
    client = TestClient(create_app(library))
    response = client.post(
        "/import-upload",
        files={"files": ("朋友-周华健.mkv", b"not a real mkv", "video/x-matroska")},
        data={"song_id": "", "title": "", "artist": ""},
        follow_redirects=False,
    )
    assert response.status_code == 303
    assert response.headers["location"] == "/songs/%E6%9C%8B%E5%8F%8B-%E5%91%A8%E5%8D%8E%E5%81%A5"
    assert (library.raw_dir("朋友-周华健") / "source.mkv").exists()


def test_detail_exposes_separate_steps_and_management(tmp_path):
    library = LibraryPaths(tmp_path / "library")
    library.ensure_song_dirs("song")
    (library.raw_dir("song") / "source.mkv").write_bytes(b"sample")
    client = TestClient(create_app(library))

    response = client.get("/songs/song")

    assert response.status_code == 200
    assert "Shift ASS" in response.text
    assert "Preview Tracks" in response.text
    assert "Start seconds" in response.text
    assert "Segments" in response.text
    assert "Device" in response.text
    assert "Sample Separate" in response.text
    assert "Remake Track" in response.text
    assert "Extract Embedded Subtitles" in response.text
    assert "Use External Instrumental" in response.text
    assert "Subtitle Workbench" in response.text
    assert "Run From Stage" in response.text
    assert "Rename Song" in response.text
    assert "Stretch Lines" not in response.text
    assert "Next Actions" in response.text
    assert "Metadata" in response.text
    assert "Diagnostics" in response.text
    assert "A/B Review" in response.text
    assert "Player Compatibility" in response.text
    assert "Failure Recovery" not in response.text
    assert "Clean Regenerable Work Files" in response.text
    assert "Delete Song" in response.text


def test_settings_page_updates_preview_defaults(tmp_path):
    library = LibraryPaths(tmp_path / "library")
    client = TestClient(create_app(library))

    response = client.post(
        "/settings",
        data={"worker_count": "3", "preview_start": "12", "preview_duration": "9", "auto_refresh_seconds": "4"},
        follow_redirects=False,
    )

    assert response.status_code == 303
    page = client.get("/settings")
    assert 'value="12.000"' in page.text
    assert "Demucs device" in page.text
    assert "Output template" in page.text
    assert "Subtitle font size" in page.text
    assert "Instrumental track title" in page.text


def test_metadata_route_updates_song(tmp_path):
    library = LibraryPaths(tmp_path / "library")
    library.ensure_song_dirs("song")
    (library.raw_dir("song") / "source.mkv").write_bytes(b"sample")
    client = TestClient(create_app(library))

    response = client.post(
        "/songs/song/metadata",
        data={"title": "朋友", "artist": "周华健", "tags": "needs-review, duet", "rating": "4"},
        follow_redirects=False,
    )

    assert response.status_code == 303
    page = client.get("/songs/song").text
    assert "朋友" in page
    assert "needs-review" in page
    assert 'value="4"' in page


def test_rename_route_moves_song(tmp_path):
    library = LibraryPaths(tmp_path / "library")
    library.ensure_song_dirs("song")
    (library.raw_dir("song") / "source.mkv").write_bytes(b"sample")
    client = TestClient(create_app(library))

    response = client.post("/songs/song/rename", data={"new_song_id": "new song"}, follow_redirects=False)

    assert response.status_code == 303
    assert response.headers["location"] == "/songs/new-song"
    assert library.raw_dir("new-song").exists()


def test_waveform_route_returns_svg(tmp_path):
    library = LibraryPaths(tmp_path / "library")
    library.ensure_song_dirs("song")
    client = TestClient(create_app(library))

    response = client.get("/songs/song/waveform.svg")

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("image/svg+xml")
    assert response.text.startswith("<svg")


def test_doctor_page_renders(tmp_path):
    client = TestClient(create_app(LibraryPaths(tmp_path / "library")))
    response = client.get("/doctor")
    assert response.status_code == 200
    assert "Dependency and library checks" in response.text


def test_wizard_storage_and_roadmap_pages_render(tmp_path):
    client = TestClient(create_app(LibraryPaths(tmp_path / "library")))

    assert "First Run Wizard" in client.get("/wizard").text
    assert "Disk Manager" in client.get("/storage").text
    assert "Non-Goals" in client.get("/roadmap").text


def test_url_import_requires_confirmation(tmp_path):
    client = TestClient(create_app(LibraryPaths(tmp_path / "library")))

    response = client.post("/import", data={"source": "https://example.com/video"}, follow_redirects=False)

    assert response.status_code == 200
    assert "Confirm URL Import" in response.text
    assert "我确认自己有权下载" in response.text


def test_search_filter_limits_library_rows(tmp_path):
    library = LibraryPaths(tmp_path / "library")
    library.ensure_song_dirs("keep")
    library.ensure_song_dirs("drop")
    (library.raw_dir("keep") / "source.mkv").write_bytes(b"sample")
    client = TestClient(create_app(library))

    response = client.get("/?q=keep&file_filter=source")

    assert response.status_code == 200
    assert "/songs/keep" in response.text
    assert "/songs/drop" not in response.text


def test_failure_recovery_and_live_events_render(tmp_path):
    library = LibraryPaths(tmp_path / "library")
    library.ensure_song_dirs("song")
    (library.raw_dir("song") / "source.mkv").write_bytes(b"sample")
    library.report_json("song").write_text('{"failed_stage": "extract", "failure": "bad track"}', encoding="utf-8")
    client = TestClient(create_app(library))

    detail = client.get("/songs/song")
    events = client.get("/events")

    assert "Failure Recovery" in detail.text
    assert "Force Rerun Failed Stage" in detail.text
    assert events.status_code == 200
    assert "data:" in events.text


def test_upload_srt_lyrics_builds_alignment(tmp_path):
    library = LibraryPaths(tmp_path / "library")
    library.ensure_song_dirs("song")
    client = TestClient(create_app(library))

    response = client.post(
        "/songs/song/lyrics-file",
        files={"file": ("lyrics.srt", b"1\n00:00:01,000 --> 00:00:02,000\nhello\n", "application/x-subrip")},
        follow_redirects=False,
    )

    assert response.status_code == 303
    assert library.alignment_json("song").exists()
    assert library.lyrics_ass("song").exists()


def test_inbox_scan_and_batch_console_routes(tmp_path):
    library = LibraryPaths(tmp_path / "library")
    library.inbox_dir.mkdir(parents=True)
    (library.inbox_dir / "inbox-song.mkv").write_bytes(b"media")
    client = TestClient(create_app(library))

    inbox_response = client.post("/inbox-scan", follow_redirects=False)
    batch_response = client.post("/batch-stage", data={"stage": "probe", "limit": "1"}, follow_redirects=False)

    assert inbox_response.status_code == 303
    assert library.raw_dir("inbox-song").exists()
    assert batch_response.status_code == 303


def test_job_detail_page_and_batch_options_render(tmp_path):
    library = LibraryPaths(tmp_path / "library")
    library.ensure_song_dirs("song")
    client = TestClient(create_app(library))

    batch_page = client.get("/")
    assert "separate-sample" in batch_page.text
    response = client.post("/songs/song/run/extract-subtitles", data={"subtitle_index": "0"}, follow_redirects=False)
    assert response.status_code == 303

    jobs = list(library.jobs_root.glob("*.json"))
    assert jobs
    job_id = jobs[0].stem
    detail = client.get(f"/jobs/{job_id}")
    assert detail.status_code == 200
    assert "Job Detail" in detail.text
    assert "extract-subtitles" in detail.text


def test_upload_external_instrumental_sets_current(tmp_path):
    library = LibraryPaths(tmp_path / "library")
    library.ensure_song_dirs("song")
    client = TestClient(create_app(library))

    response = client.post(
        "/songs/song/instrumental-file",
        files={"file": ("candidate.wav", b"audio", "audio/wav")},
        data={"label": "my take"},
        follow_redirects=False,
    )

    assert response.status_code == 303
    assert library.instrumental_wav("song").read_bytes() == b"audio"
