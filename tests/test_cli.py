from ktv_mux.cli import main


def test_cli_settings_command_updates_library(tmp_path, capsys):
    result = main(
        [
            "--library",
            str(tmp_path / "library"),
            "settings",
            "--preview-start",
            "15",
            "--preview-duration",
            "6",
            "--default-audio-order",
            "original-first",
            "--output-template",
            "{artist}-{title}.ktv.mkv",
            "--subtitle-font-size",
            "60",
        ]
    )

    captured = capsys.readouterr()
    assert result == 0
    assert '"preview_start": 15.0' in captured.out
    assert '"default_audio_order": "original-first"' in captured.out
    assert '"subtitle_font_size": 60' in captured.out


def test_cli_import_many_uses_filenames(tmp_path, capsys):
    first = tmp_path / "one.mkv"
    second = tmp_path / "two.mkv"
    first.write_bytes(b"1")
    second.write_bytes(b"2")

    result = main(["--library", str(tmp_path / "library"), "import-many", str(first), str(second)])

    captured = capsys.readouterr()
    assert result == 0
    assert '"song_id": "one"' in captured.out
    assert '"song_id": "two"' in captured.out


def test_cli_batch_stage_probe_handles_empty_library(tmp_path, capsys):
    result = main(["--library", str(tmp_path / "library"), "batch-stage", "probe"])

    captured = capsys.readouterr()
    assert result == 0
    assert captured.out.strip() == "[]"


def test_cli_batch_stage_dry_run_lists_existing_song(tmp_path, capsys):
    raw = tmp_path / "library" / "raw" / "song"
    raw.mkdir(parents=True)

    result = main(["--library", str(tmp_path / "library"), "batch-stage", "probe", "--dry-run"])

    captured = capsys.readouterr()
    assert result == 0
    assert '"planned": true' in captured.out


def test_cli_storage_reports_library(tmp_path, capsys):
    raw = tmp_path / "library" / "raw" / "song"
    raw.mkdir(parents=True)
    (raw / "source.mkv").write_bytes(b"123")

    result = main(["--library", str(tmp_path / "library"), "storage"])

    captured = capsys.readouterr()
    assert result == 0
    assert '"roots"' in captured.out
    assert '"songs"' in captured.out


def test_cli_inbox_scan_imports_files(tmp_path, capsys):
    inbox = tmp_path / "library" / "inbox"
    inbox.mkdir(parents=True)
    (inbox / "sample.mkv").write_bytes(b"media")

    result = main(["--library", str(tmp_path / "library"), "inbox-scan"])

    captured = capsys.readouterr()
    assert result == 0
    assert '"song_id": "sample"' in captured.out


def test_cli_metadata_tags_and_lyrics_versions(tmp_path, capsys):
    result = main(
        [
            "--library",
            str(tmp_path / "library"),
            "metadata",
            "song",
            "--tags",
            "duet, needs-review",
            "--rating",
            "5",
        ]
    )

    captured = capsys.readouterr()
    assert result == 0
    assert '"tags": [' in captured.out
    assert '"rating": 5' in captured.out
