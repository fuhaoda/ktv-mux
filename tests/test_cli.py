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
        ]
    )

    captured = capsys.readouterr()
    assert result == 0
    assert '"preview_start": 15.0' in captured.out


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
