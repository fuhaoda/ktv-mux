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

    def preview_tracks(self, song_id, *, duration=20.0, start=0.0, cancel_file=None):
        self.calls.append(("preview-tracks", song_id, duration, start, cancel_file is not None))

    def shift_subtitles(self, song_id, *, seconds=0.0):
        self.calls.append(("shift-subtitles", song_id, seconds))


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

    assert pipeline.calls == [
        ("import-url", "song", "https://example.invalid/v", None, None, False),
        ("extract", "song", 2, True),
        ("preview-tracks", "song", 7.5, 12.0, False),
        ("shift-subtitles", "song", -0.25),
    ]
