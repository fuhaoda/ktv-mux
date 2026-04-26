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


def test_upload_defaults_song_id_to_filename(tmp_path):
    library = LibraryPaths(tmp_path / "library")
    client = TestClient(create_app(library))
    response = client.post(
        "/import-upload",
        files={"file": ("朋友-周华健.mkv", b"not a real mkv", "video/x-matroska")},
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
    assert "Diagnostics" in response.text
    assert "Clean Regenerable Work Files" in response.text
    assert "Delete Song" in response.text


def test_doctor_page_renders(tmp_path):
    client = TestClient(create_app(LibraryPaths(tmp_path / "library")))
    response = client.get("/doctor")
    assert response.status_code == 200
    assert "Dependency and library checks" in response.text
