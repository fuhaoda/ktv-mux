# Implemented Improvement Pass

This pass addressed the ten self-review items from the first working version.

1. File-backed Web job queue under `library/jobs`, with startup recovery.
2. Per-song file locks around pipeline stages.
3. Demucs output streamed to `library/work/{song_id}/logs/separate.log`.
4. Web routes split from server-rendered views.
5. Subtitle timing can be shifted without rerunning alignment.
6. Separation writes a basic WAV quality report for mix, instrumental, and vocals.
7. Probe and audio-track selection now fail early on invalid media/track choices.
8. Demucs has an opt-in slow smoke test gated by `KTV_RUN_SLOW=1`.
9. Ruff linting and GitHub Actions CI are configured.
10. Library management supports `clean-work` and `delete` from CLI and Web.

## Second Improvement Pass

This pass addressed the next ten self-review items.

1. Jobs now expose progress, queued-job cancel, and failed/canceled retry.
2. Demucs progress is parsed from `separate.log` and rendered as a progress bar.
3. Source audio tracks can be previewed before selecting the separation track.
4. Subtitles can be edited line-by-line after alignment.
5. Lyrics saving cleans LRC timestamps, chord tags, full-width spaces, and duplicate whitespace.
6. `ktv doctor` and the Web Doctor page diagnose dependencies and per-song failures.
7. Generated audio and MKV outputs are copied into timestamped `takes/`.
8. WAV quality metrics now include clipping and silence ratios.
9. The Web detail page has dedicated panels for source tracks, diagnostics, jobs, takes, and subtitle editing.
10. CLI and docs now cover doctor, preview tracks, subtitle line edits, and output versions.

## Third Improvement Pass

This pass addressed the next ten self-review items.

1. Running jobs can now be canceled through cancel files monitored by FFmpeg, yt-dlp, and Demucs wrappers.
2. The Web runner uses a small worker pool so different songs can run in parallel while the per-song lock keeps one song serialized.
3. Source audio previews support configurable start offset and duration from CLI and Web.
4. The subtitle editor now shows an audio waveform/timeline above editable line timing.
5. Output takes have labels, notes, delete actions, and set-current promotion back to the stable output filename.
6. Separation quality reports include concrete recommendations, not only raw metrics.
7. Web styling moved to `static/style.css` while keeping a no-Node FastAPI UI.
8. URL imports run as background jobs with `import.log`, progress parsing, and saved download metadata when yt-dlp writes it.
9. LRC timestamps are converted into an initial `alignment.json` when lyrics are saved.
10. macOS bootstrap, startup, and Desktop launcher scripts provide a one-click local startup path.
