from ktv_mux.jobs import Job, LocalJobRunner, run_pipeline_stage
from ktv_mux.jsonio import read_json, write_json
from ktv_mux.paths import LibraryPaths


class FakePipeline:
    def __init__(self):
        self.calls = []

    def import_source(self, source, *, song_id=None, title=None, artist=None, cancel_file=None):
        self.calls.append(("import-url", song_id, source, title, artist, cancel_file is not None))

    def extract(self, song_id, *, audio_index=0, cancel_file=None):
        self.calls.append(("extract", song_id, audio_index, cancel_file is not None))

    def preview_tracks(
        self,
        song_id,
        *,
        duration=20.0,
        start=0.0,
        count=1,
        spacing=45.0,
        preset="manual",
        cancel_file=None,
    ):
        self.calls.append(("preview-tracks", song_id, duration, start, count, spacing, preset, cancel_file is not None))

    def shift_subtitles(self, song_id, *, seconds=0.0):
        self.calls.append(("shift-subtitles", song_id, seconds))

    def shift_subtitle_lines(self, song_id, *, start_line=0, end_line=0, seconds=0.0):
        self.calls.append(("shift-subtitle-lines", song_id, start_line, end_line, seconds))

    def stretch_subtitle_lines(self, song_id, *, start_line=0, end_line=0, target_start=0.0, target_end=1.0):
        self.calls.append(("stretch-subtitle-lines", song_id, start_line, end_line, target_start, target_end))

    def mux(self, song_id, *, audio_order="instrumental-first", duration_limit=None, cancel_file=None):
        self.calls.append(("mux", song_id, audio_order, duration_limit, cancel_file is not None))

    def separate(self, song_id, *, model="htdemucs", device=None, cancel_file=None):
        self.calls.append(("separate", song_id, model, device, cancel_file is not None))

    def replace_audio(self, song_id, *, keep_audio_index=0, copy_subtitles=True, duration_limit=None, cancel_file=None):
        self.calls.append(("replace-audio", song_id, keep_audio_index, copy_subtitles, duration_limit, cancel_file is not None))

    def process_from(
        self,
        song_id,
        *,
        start_stage="probe",
        align_backend="auto",
        audio_index=0,
        model="htdemucs",
        device=None,
        duration_limit=None,
        cancel_file=None,
    ):
        self.calls.append(
            (
                "process-from",
                song_id,
                start_stage,
                align_backend,
                audio_index,
                model,
                device,
                duration_limit,
                cancel_file is not None,
            )
        )


def test_job_runner_submit_persists_queue_state(tmp_path):
    library = LibraryPaths(tmp_path / "library")
    runner = LocalJobRunner(library, FakePipeline())

    job = runner.submit("朋友 周华健", "extract", {"audio_index": 1})

    saved = read_json(library.job_json(job.job_id))
    status = read_json(library.status_json("朋友-周华健"))
    assert saved["song_id"] == "朋友-周华健"
    assert saved["state"] == "queued"
    assert status["state"] == "queued"
    assert runner.list_jobs()[0].job_id == job.job_id


def test_job_runner_cancel_and_retry(tmp_path):
    library = LibraryPaths(tmp_path / "library")
    runner = LocalJobRunner(library, FakePipeline())
    job = runner.submit("song", "extract", {"audio_index": 1})

    assert runner.cancel(job.job_id) is True
    canceled = read_json(library.job_json(job.job_id))
    assert canceled["state"] == "canceled"

    retry = runner.retry(job.job_id)
    assert retry is not None
    assert retry.params["retry_of"] == job.job_id


def test_job_runner_cancel_running_job_writes_cancel_file(tmp_path):
    library = LibraryPaths(tmp_path / "library")
    runner = LocalJobRunner(library, FakePipeline())
    job = runner.submit("song", "extract", {"audio_index": 1})
    saved = read_json(library.job_json(job.job_id))
    saved["state"] = "running"
    write_json(library.job_json(job.job_id), saved)

    assert runner.cancel(job.job_id) is True

    canceled = read_json(library.job_json(job.job_id))
    assert canceled["state"] == "canceling"
    assert library.job_cancel_file(job.job_id).exists()


def test_job_runner_prunes_finished_jobs(tmp_path):
    library = LibraryPaths(tmp_path / "library")
    runner = LocalJobRunner(library, FakePipeline())
    done = runner.submit("song", "extract")
    queued = runner.submit("song", "probe")
    done_data = read_json(library.job_json(done.job_id))
    done_data["state"] = "completed"
    write_json(library.job_json(done.job_id), done_data)

    assert runner.prune_jobs() == 1
    assert not library.job_json(done.job_id).exists()
    assert library.job_json(queued.job_id).exists()


def test_job_runner_recovers_running_job_from_checkpoint(tmp_path):
    library = LibraryPaths(tmp_path / "library")
    library.ensure_song_dirs("song")
    library.mix_wav("song").write_bytes(b"mix")
    runner = LocalJobRunner(library, FakePipeline())
    job = runner.submit("song", "extract")
    data = read_json(library.job_json(job.job_id))
    data["state"] = "running"
    write_json(library.job_json(job.job_id), data)
    write_json(
        library.checkpoints_json("song"),
        {"extract": {"state": "completed", "outputs": [str(library.mix_wav("song"))]}},
    )

    runner._recover_jobs()

    recovered = read_json(library.job_json(job.job_id))
    assert recovered["state"] == "completed"


def test_run_pipeline_stage_passes_stage_parameters():
    pipeline = FakePipeline()

    run_pipeline_stage(
        pipeline,
        Job(job_id="import", song_id="song", stage="import-url", params={"source": "https://example.invalid/v"}),
    )
    run_pipeline_stage(
        pipeline,
        Job(job_id="1", song_id="song", stage="extract", params={"audio_index": 2}),
        cancel_file="cancel",
    )
    run_pipeline_stage(
        pipeline,
        Job(job_id="preview", song_id="song", stage="preview-tracks", params={"duration": "7.5", "start": "12"}),
    )
    run_pipeline_stage(
        pipeline,
        Job(job_id="2", song_id="song", stage="shift-subtitles", params={"seconds": "-0.25"}),
    )
    run_pipeline_stage(
        pipeline,
        Job(job_id="mux", song_id="song", stage="mux", params={"duration_limit": "3"}),
    )
    run_pipeline_stage(
        pipeline,
        Job(job_id="replace", song_id="song", stage="replace-audio", params={"keep_audio_index": "1", "duration_limit": "4"}),
    )
    run_pipeline_stage(
        pipeline,
        Job(job_id="from", song_id="song", stage="process-from", params={"start_stage": "separate", "audio_index": "1"}),
    )

    assert pipeline.calls == [
        ("import-url", "song", "https://example.invalid/v", None, None, False),
        ("extract", "song", 2, True),
        ("preview-tracks", "song", 7.5, 12.0, 1, 45.0, "manual", False),
        ("shift-subtitles", "song", -0.25),
        ("mux", "song", "instrumental-first", 3.0, False),
        ("replace-audio", "song", 1, True, 4.0, False),
        ("process-from", "song", "separate", "auto", 1, "htdemucs", None, None, False),
    ]
