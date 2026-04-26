from ktv_mux.library import import_source, song_summary
from ktv_mux.paths import LibraryPaths


def test_import_source_defaults_song_id_to_filename(tmp_path):
    source = tmp_path / "朋友-周华健.mkv"
    source.write_bytes(b"sample")
    library = LibraryPaths(tmp_path / "library")

    song = import_source(str(source), library=library)

    assert song.song_id == "朋友-周华健"
    assert (library.raw_dir("朋友-周华健") / "source.mkv").read_bytes() == b"sample"
    assert song_summary(library, "朋友-周华健")["has_source"] is True

