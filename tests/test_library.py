from ktv_mux.library import delete_song, import_source, song_summary
from ktv_mux.paths import LibraryPaths
from ktv_mux.pipeline import Pipeline


def test_import_source_defaults_song_id_to_filename(tmp_path):
    source = tmp_path / "朋友-周华健.mkv"
    source.write_bytes(b"sample")
    library = LibraryPaths(tmp_path / "library")

    song = import_source(str(source), library=library)

    assert song.song_id == "朋友-周华健"
    assert (library.raw_dir("朋友-周华健") / "source.mkv").read_bytes() == b"sample"
    assert song_summary(library, "朋友-周华健")["has_source"] is True


def test_clean_work_keeps_outputs_and_removes_regenerable_files(tmp_path):
    library = LibraryPaths(tmp_path / "library")
    library.ensure_song_dirs("song")
    library.mix_wav("song").write_bytes(b"mix")
    library.vocals_wav("song").write_bytes(b"vocals")
    library.alignment_json("song").write_text("{}", encoding="utf-8")
    library.instrumental_wav("song").write_bytes(b"instrumental")

    result = Pipeline(library).clean_work("song")

    assert result["removed"]
    assert not library.mix_wav("song").exists()
    assert not library.vocals_wav("song").exists()
    assert library.instrumental_wav("song").exists()


def test_delete_song_removes_library_folders(tmp_path):
    library = LibraryPaths(tmp_path / "library")
    library.ensure_song_dirs("song")
    library.jobs_root.mkdir(parents=True)
    library.job_json("abc").write_text('{"song_id": "song"}', encoding="utf-8")
    delete_song(library, "song")

    assert not library.raw_dir("song").exists()
    assert not library.work_dir("song").exists()
    assert not library.output_dir("song").exists()
    assert not library.job_json("abc").exists()
