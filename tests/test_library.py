from ktv_mux.alignment import generate_even_alignment
from ktv_mux.jsonio import read_json, write_json
from ktv_mux.library import (
    delete_song,
    import_source,
    rename_song,
    save_lyrics_file,
    save_lyrics_text,
    song_summary,
    update_song_metadata,
)
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


def test_import_source_records_duplicate_sources(tmp_path):
    first = tmp_path / "first.mkv"
    second = tmp_path / "second.mkv"
    first.write_bytes(b"same media")
    second.write_bytes(b"same media")
    library = LibraryPaths(tmp_path / "library")

    import_source(str(first), library=library)
    import_source(str(second), library=library)

    report = read_json(library.report_json("second"))
    assert report["duplicate_sources"][0]["song_id"] == "first"


def test_rename_song_moves_library_folders(tmp_path):
    source = tmp_path / "old.mkv"
    source.write_bytes(b"sample")
    library = LibraryPaths(tmp_path / "library")
    import_source(str(source), library=library)
    library.mix_wav("old").write_bytes(b"mix")

    song = rename_song(library, "old", "new name")

    assert song.song_id == "new-name"
    assert not library.raw_dir("old").exists()
    assert library.source_path("new-name").exists()
    assert library.mix_wav("new-name").read_bytes() == b"mix"


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


def test_edit_subtitles_rebuilds_alignment_and_ass(tmp_path):
    library = LibraryPaths(tmp_path / "library")
    library.ensure_song_dirs("song")
    write_json(library.alignment_json("song"), generate_even_alignment(["旧歌词"], duration=4))

    Pipeline(library).edit_subtitles("song", [{"index": 0, "start": 1, "end": 2, "text": "新歌词"}])

    assert "新" in library.lyrics_ass("song").read_text(encoding="utf-8")


def test_save_lyrics_text_writes_lrc_alignment(tmp_path):
    library = LibraryPaths(tmp_path / "library")

    save_lyrics_text(library, "song", "[00:01.00]第一句\n[00:03.00]第二句")

    assert library.lyrics_txt("song").read_text(encoding="utf-8") == "第一句\n第二句\n"
    alignment = read_json(library.alignment_json("song"))
    assert alignment["backend"] == "lrc"
    assert alignment["lines"][0]["end"] == 3.0
    assert song_summary(library, "song")["lyrics_versions"]


def test_update_song_metadata_saves_tags_and_rating(tmp_path):
    library = LibraryPaths(tmp_path / "library")

    song = update_song_metadata(library, "song", tags=["duet", " needs-review "], rating=9)
    summary = song_summary(library, "song")

    assert song.rating == 5
    assert summary["tags"] == ["duet", "needs-review"]
    assert summary["rating"] == 5


def test_save_lyrics_file_detects_encoding_and_keeps_original(tmp_path):
    source = tmp_path / "lyrics.lrc"
    source.write_bytes("[00:01.00]朋友".encode("gb18030"))
    library = LibraryPaths(tmp_path / "library")

    save_lyrics_file(library, "song", source)

    assert library.lyrics_txt("song").read_text(encoding="utf-8") == "朋友\n"
    assert library.original_lyrics_file("song", ".lrc").read_bytes() == source.read_bytes()
    report = read_json(library.report_json("song"))
    assert report["lyrics_import"]["encoding"] == "gb18030"


def test_delete_song_removes_library_folders(tmp_path):
    library = LibraryPaths(tmp_path / "library")
    library.ensure_song_dirs("song")
    library.jobs_root.mkdir(parents=True)
    library.job_json("abc").write_text('{"song_id": "song"}', encoding="utf-8")
    library.job_cancel_file("abc").write_text("cancel", encoding="utf-8")
    delete_song(library, "song")

    assert not library.raw_dir("song").exists()
    assert not library.work_dir("song").exists()
    assert not library.output_dir("song").exists()
    assert not library.job_json("abc").exists()
    assert not library.job_cancel_file("abc").exists()
