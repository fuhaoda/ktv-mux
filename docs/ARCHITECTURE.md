# Architecture

`ktv-mux` is deliberately split into small modules so the same workflow works from CLI and Web UI.

## Modules

- `paths.py`: library layout and song id normalization.
- `library.py`: import, metadata, lyrics storage, and song summary.
- `media.py`: FFprobe, FFmpeg, Demucs command construction and execution.
- `alignment.py`: lyrics alignment abstraction; FunASR when installed, deterministic draft fallback otherwise.
- `ass.py`: ASS karaoke subtitle generation.
- `pipeline.py`: stage orchestration and status/report writing.
- `cli.py`: `ktv` command line interface.
- `web.py`: local FastAPI workbench.

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
    demucs/
  output/{song_id}/
    instrumental.wav
    lyrics.ass
    {song_id}.audio-replaced.mkv
    {song_id}.ktv.mkv
    report.json
```

## Stages

1. `import`: copy a local file or download a URL into `raw/{song_id}`.
2. `probe`: record source media streams with FFprobe.
3. `extract`: extract a selected audio stream into `work/{song_id}/mix.wav`.
4. `separate`: run Demucs and write `instrumental.wav` plus `vocals.wav`.
5. `replace-audio`: create an MKV with original Track 1 and generated instrumental as Track 2.
6. `align`: turn `lyrics.txt` into `alignment.json` and `lyrics.ass`.
7. `mux`: create the final KTV MKV with generated ASS lyrics.

## Web Behavior

Long-running stage buttons enqueue a background task and immediately return to the song page. The page auto-refreshes while a stage is running. Failures are written to `status.json` and `report.json`; ordinary request failures render a friendly error page rather than a raw Internal Server Error.

