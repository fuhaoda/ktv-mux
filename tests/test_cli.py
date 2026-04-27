import argparse
from pathlib import Path

import pytest

from ktv_mux.cli import build_parser, dispatch, main


class FakePipeline:
    def __init__(self):
        self.calls = []

    def separate_sample(
        self,
        song_id,
        *,
        audio_index=0,
        start=0.0,
        duration=30.0,
        preset="fast-review",
        model=None,
        device=None,
    ):
        self.calls.append(("separate-sample", song_id, audio_index, start, duration, preset, model, device))
        return {"ok": True}

    def batch_stage(self, stage, *, raw_root=None, **params):
        self.calls.append(("batch-stage", stage, raw_root, params))
        return [{"planned": True}]

    def batch_recipe(self, recipe, *, raw_root=None, dry_run=False, **params):
        self.calls.append(("batch-recipe", recipe, raw_root, dry_run, params))
        return {"planned": True}

    def set_instrumental(
        self,
        song_id,
        audio_path,
        *,
        label="external instrumental",
        offset=0.0,
        gain_db=0.0,
        fit_to_mix=False,
        normalize=False,
    ):
        self.calls.append(("set-instrumental", song_id, audio_path, label, offset, gain_db, fit_to_mix, normalize))
        return audio_path

    def set_track_role(self, song_id, *, audio_index, role, note=""):
        self.calls.append(("track-role", song_id, audio_index, role, note))
        return {"role": role}

    def mux_plan(self, song_id, *, audio_order="instrumental-first"):
        self.calls.append(("mux-plan", song_id, audio_order))
        return {"kind": "ktv-mkv"}

    def replace_audio_plan(self, song_id, *, keep_audio_index=0, copy_subtitles=True):
        self.calls.append(("replace-plan", song_id, keep_audio_index, copy_subtitles))
        return {"kind": "audio-replaced-mkv"}


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


def test_every_cli_subcommand_exposes_help(capsys):
    parser = build_parser()
    subparsers = next(action for action in parser._actions if isinstance(action, argparse._SubParsersAction))

    for command in subparsers.choices:
        with pytest.raises(SystemExit) as exc:
            parser.parse_args([command, "--help"])
        assert exc.value.code == 0
    capsys.readouterr()


def test_cli_separate_sample_uses_preset_argument():
    parser = build_parser()
    args = parser.parse_args(
        [
            "separate-sample",
            "song",
            "--audio-index",
            "1",
            "--start",
            "12",
            "--duration",
            "8",
            "--preset",
            "fast-review",
            "--model",
            "htdemucs",
            "--device",
            "cpu",
        ]
    )
    fake = FakePipeline()

    result = dispatch(args, fake, None)

    assert result == {"ok": True}
    assert fake.calls == [("separate-sample", "song", 1, 12.0, 8.0, "fast-review", "htdemucs", "cpu")]


def test_cli_batch_stage_forwards_separation_preset(tmp_path):
    parser = build_parser()
    args = parser.parse_args(
        [
            "--library",
            str(tmp_path / "library"),
            "batch-stage",
            "separate",
            "--separation-preset",
            "quality",
            "--model",
            "htdemucs",
            "--device",
            "cpu",
            "--dry-run",
        ]
    )
    fake = FakePipeline()

    dispatch(args, fake, None)

    call = fake.calls[0]
    assert call[0] == "batch-stage"
    assert call[1] == "separate"
    assert call[3]["separation_preset"] == "quality"
    assert call[3]["model"] == "htdemucs"
    assert call[3]["device"] == "cpu"


def test_cli_batch_recipe_forwards_recipe_params(tmp_path):
    parser = build_parser()
    args = parser.parse_args(
        [
            "--library",
            str(tmp_path / "library"),
            "batch-recipe",
            "instrumental-review",
            "--audio-index",
            "1",
            "--separation-preset",
            "fast-review",
            "--dry-run",
        ]
    )
    fake = FakePipeline()

    dispatch(args, fake, None)

    call = fake.calls[0]
    assert call[0] == "batch-recipe"
    assert call[1] == "instrumental-review"
    assert call[3] is True
    assert call[4]["audio_index"] == 1
    assert call[4]["separation_preset"] == "fast-review"


def test_cli_set_instrumental_forwards_fit_options():
    parser = build_parser()
    args = parser.parse_args(
        [
            "set-instrumental",
            "song",
            "candidate.mp3",
            "--label",
            "take",
            "--offset",
            "0.25",
            "--gain-db",
            "-2",
            "--fit-to-mix",
            "--normalize",
        ]
    )
    fake = FakePipeline()

    dispatch(args, fake, None)

    assert fake.calls == [("set-instrumental", "song", Path("candidate.mp3"), "take", 0.25, -2.0, True, True)]


def test_cli_track_role_and_plan_commands():
    parser = build_parser()
    fake = FakePipeline()

    dispatch(parser.parse_args(["track-role", "song", "--audio-index", "1", "--role", "instrumental"]), fake, None)
    dispatch(parser.parse_args(["mux-plan", "song", "--audio-order", "original-first"]), fake, None)
    dispatch(parser.parse_args(["replace-plan", "song", "--keep-audio-index", "1", "--no-copy-subtitles"]), fake, None)

    assert fake.calls == [
        ("track-role", "song", 1, "instrumental", ""),
        ("mux-plan", "song", "original-first"),
        ("replace-plan", "song", 1, False),
    ]


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


def test_cli_preflight_reports_song_readiness(tmp_path, capsys):
    library = tmp_path / "library"
    raw = library / "raw" / "song"
    work = library / "work" / "song"
    output = library / "output" / "song"
    raw.mkdir(parents=True)
    work.mkdir(parents=True)
    output.mkdir(parents=True)
    (raw / "source.mkv").write_bytes(b"source")
    (work / "mix.wav").write_bytes(b"mix")
    (output / "instrumental.wav").write_bytes(b"instrumental")
    (output / "lyrics.ass").write_text("ass", encoding="utf-8")

    result = main(["--library", str(library), "preflight", "song"])

    captured = capsys.readouterr()
    assert result == 0
    assert '"ok_for_replace_audio": true' in captured.out
    assert '"ok_for_final_mkv": true' in captured.out


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
