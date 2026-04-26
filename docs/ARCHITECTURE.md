# Architecture

`ktv-mux` is deliberately split into small modules so the same workflow works from CLI and Web UI.

## Modules

- `paths.py`: library layout and song id normalization.
- `library.py`: import, metadata, lyrics storage, and song summary.
- `media.py`: FFprobe, FFmpeg, Demucs command construction and execution.
- `alignment.py`: lyrics alignment abstraction; FunASR when installed, deterministic draft fallback otherwise.
- `ass.py`: ASS karaoke subtitle generation.
- `quality.py`: lightweight WAV duration and level metrics for separation review.
- `pipeline.py`: stage orchestration and status/report writing.
- `jobs.py`: file-backed local queue for long-running Web tasks.
- `cli.py`: `ktv` command line interface.
- `web.py`: local FastAPI routes.
- `views.py`: server-rendered HTML for the local workbench.

## Library Layout

```text
library/
  raw/{song_id}/
    source.mkv
    song.json
    lyrics.txt
  work/{song_id}/
    mix.wav
    vocals.wav
    alignment.json
    status.json
    logs/
    demucs/
  output/{song_id}/
    instrumental.wav
    lyrics.ass
    {song_id}.audio-replaced.mkv
    {song_id}.ktv.mkv
    report.json
  jobs/
    {job_id}.json
```

## Stages

1. `import`: copy a local file or download a URL into `raw/{song_id}`.
2. `probe`: record source media streams with FFprobe.
3. `extract`: extract a selected audio stream into `work/{song_id}/mix.wav`.
4. `separate`: run Demucs and write `instrumental.wav` plus `vocals.wav`.
5. `replace-audio`: create an MKV with original Track 1 and generated instrumental as Track 2.
6. `align`: turn `lyrics.txt` into `alignment.json` and `lyrics.ass`.
7. `shift-subtitles`: apply a manual timing offset and rebuild `lyrics.ass`.
8. `mux`: create the final KTV MKV with generated ASS lyrics.
9. `clean-work`: remove regenerable intermediate files while keeping source and outputs.

## Web Behavior

Long-running stage buttons enqueue a file-backed local job and immediately return to the song page. On app startup, jobs left in `queued` or `running` state are recovered and queued again.

Each pipeline stage takes a per-song file lock, so a user can click multiple actions without corrupting one song's working files. Failures are written to `status.json` and `report.json`; ordinary request failures render a friendly error page rather than a raw Internal Server Error.
