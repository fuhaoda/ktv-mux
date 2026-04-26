from ktv_mux.paths import LibraryPaths
from ktv_mux.versions import delete_take, list_takes, record_take, set_current_take, update_take


def test_take_metadata_update_set_current_and_delete(tmp_path):
    library = LibraryPaths(tmp_path / "library")
    library.ensure_song_dirs("song")
    take = library.takes_dir("song") / "instrumental.20260425T010101Z.wav"
    take.write_bytes(b"audio")
    record_take(library, "song", take)

    update_take(library, "song", take.name, label="good", note="less vocal bleed", score=5)
    current = set_current_take(library, "song", take.name)
    takes = list_takes(library, "song")

    assert current == library.instrumental_wav("song")
    assert current.read_bytes() == b"audio"
    assert takes[0]["label"] == "good"
    assert takes[0]["score"] == 5
    assert takes[0]["is_current"] is True

    delete_take(library, "song", take.name)
    assert list_takes(library, "song") == []
