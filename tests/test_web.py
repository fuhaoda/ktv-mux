from fastapi.testclient import TestClient

from ktv_mux.paths import LibraryPaths
from ktv_mux.web import create_app


def test_index_makes_song_id_optional(tmp_path):
    client = TestClient(create_app(LibraryPaths(tmp_path / "library")))
    response = client.get("/")
    assert response.status_code == 200
    assert "Song ID optional" in response.text
    assert "Choose File" in response.text
    assert "Recent Jobs" in response.text
    assert "Doctor" in response.text
    assert "Settings" in response.text
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
    assert "Next Actions" in response.text
    assert "Metadata" in response.text
    assert "Diagnostics" in response.text
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


def test_metadata_route_updates_song(tmp_path):
    library = LibraryPaths(tmp_path / "library")
    library.ensure_song_dirs("song")
    (library.raw_dir("song") / "source.mkv").write_bytes(b"sample")
    client = TestClient(create_app(library))

    response = client.post("/songs/song/metadata", data={"title": "朋友", "artist": "周华健"}, follow_redirects=False)

    assert response.status_code == 303
    assert "朋友" in client.get("/songs/song").text


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
