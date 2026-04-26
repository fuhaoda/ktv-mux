# Architecture

`ktv-mux` is deliberately split into small modules so the same workflow works from CLI and Web UI.

## Modules

- `paths.py`: library layout and song id normalization.
- `library.py`: import, metadata, lyrics storage, and song summary.
- `media.py`: FFprobe, FFmpeg, Demucs command construction and execution.
- `alignment.py`: lyrics alignment abstraction; FunASR when installed, deterministic draft fallback otherwise.
- `ass.py`: ASS karaoke subtitle generation.
- `quality.py`: lightweight WAV duration and level metrics for separation review.
- `progress.py`: stage progress estimation, especially Demucs log parsing.
- `diagnostics.py`: local dependency and per-song failure diagnosis.
- `planner.py`: next-action suggestions derived from current song files and reports.
- `settings.py`: library-level defaults for Web workers, preview windows, and refresh cadence.
- `exporter.py`: ZIP packaging for current outputs, reports, lyrics, and takes.
- `checkpoints.py`: per-stage checkpoint state used during job recovery.
- `pipeline.py`: stage orchestration and status/report writing.
- `jobs.py`: file-backed local queue for long-running Web tasks.
- `versions.py`: output take metadata, notes, delete, and set-current behavior.
- `waveform.py`: lightweight WAV waveform SVG rendering for subtitle timing.
- `cli.py`: `ktv` command line interface.
- `web.py`: local FastAPI routes.
- `views.py`: server-rendered HTML for the local workbench.
- `templates/base.html`: shared page shell for the local Web UI.
- `static/style.css`: Web UI styling without a frontend build step.

## Library Layout

```text
library/
  settings.json
  raw/{song_id}/
    source.mkv
    song.json
    lyrics.txt
  work/{song_id}/
    mix.wav
    vocals.wav
    alignment.json
    status.json
    checkpoints.json
    logs/
    track-previews/
    demucs/
  output/{song_id}/
    instrumental.wav
    lyrics.ass
    {song_id}.audio-replaced.mkv
    {song_id}.ktv.mkv
    report.json
    {song_id}.package.zip
    takes/
      takes.json
  jobs/
    {job_id}.json
    {job_id}.cancel
```

## Stages

1. `import`: copy a local file or download a URL into `raw/{song_id}`.
2. `probe`: record source media streams with FFprobe.
3. `extract`: extract a selected audio stream into `work/{song_id}/mix.wav`.
4. `preview-tracks`: extract short clips from every source audio stream.
5. `separate`: run Demucs and write `instrumental.wav` plus `vocals.wav`.
6. `replace-audio`: create an MKV with original Track 1 and generated instrumental as Track 2.
7. `align`: turn `lyrics.txt` into `alignment.json` and `lyrics.ass`.
8. `shift-subtitles`: apply a manual timing offset and rebuild `lyrics.ass`.
9. `edit-subtitles`: update line-level timing/text and rebuild `lyrics.ass`.
10. `mux`: create the final KTV MKV with generated ASS lyrics.
11. `clean-work`: remove regenerable intermediate files while keeping source and outputs.

## Web Behavior

Long-running stage buttons enqueue a file-backed local job and immediately return to the song page. On app startup, jobs left in `queued` or `running` state are recovered and queued again. Jobs run with a small worker pool configured by `settings.json`, so different songs can progress in parallel, while each song is still serialized by the per-song lock.

Queued jobs and running jobs can be canceled. Running subprocesses receive a cancel file path; FFmpeg, yt-dlp, and Demucs wrappers monitor it and terminate the child process when requested. Failed/canceled jobs can be retried, and finished jobs can be pruned. If the app restarts after a stage already wrote its expected outputs, checkpoint recovery can mark that running job complete instead of repeating expensive work. Demucs progress is estimated from the stage log, and URL download progress is estimated from `import.log`.

Each pipeline stage takes a per-song file lock, so a user can click multiple actions without corrupting one song's working files. Failures are written to `status.json` and `report.json`; ordinary request failures render a friendly error page rather than a raw Internal Server Error.

Outputs keep a stable "latest" file for normal use and a timestamped copy under `takes/` for comparison across models, source tracks, and subtitle edits. `takes.json` stores labels, notes, and which take is currently promoted back to the stable output filename.

The Web detail page asks `planner.py` for next actions rather than hard-coding a single linear happy path. This keeps the UI flexible when a user only wants to preview tracks, replace audio, edit subtitles, or export a package.

Track previews are stored as `track-{track}.wav` for the first segment and `track-{track}-{segment}.wav` for additional segments. Web audio routes map those names back to playable clips.
