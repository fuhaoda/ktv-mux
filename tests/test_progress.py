from ktv_mux.paths import LibraryPaths
from ktv_mux.progress import demucs_log_progress, estimate_stage_progress


def test_demucs_log_progress_reads_latest_percent(tmp_path):
    log = tmp_path / "separate.log"
    log.write_text(" 10%|abc\n 42%|def\n", encoding="utf-8")
    assert demucs_log_progress(log) == 42


def test_estimate_stage_progress_uses_state_and_log(tmp_path):
    library = LibraryPaths(tmp_path / "library")
    library.ensure_song_dirs("song")
    library.stage_log("song", "separate").write_text(" 73%|abc\n", encoding="utf-8")

    assert estimate_stage_progress(library, "song", "separate", "running") == 73
    assert estimate_stage_progress(library, "song", "extract", "completed") == 100
    assert estimate_stage_progress(library, "song", "extract", "queued") == 0
