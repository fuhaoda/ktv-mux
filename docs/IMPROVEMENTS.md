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

## Fourth Improvement Pass

This pass addressed the next ten self-review items.

1. Library-level settings now persist worker count, preview defaults, and Web refresh timing.
2. CLI and Web can edit song title/artist metadata after import.
3. Web upload supports multiple local media files in one selection.
4. A next-action planner suggests the most useful next stage for each song.
5. CLI exposes `jobs` for inspecting file-backed Web jobs.
6. CLI and Web expose job pruning for completed, failed, and canceled jobs.
7. CLI and Web expose mux duration limits for faster short-sample validation.
8. `ktv export` and the Web Outputs panel can create a ZIP package with outputs, reports, lyrics, and takes.
9. `ktv import-many` imports several local files in one command, using filenames as song IDs.
10. Tests and docs now cover the new settings, planner, export, CLI, and Web management paths.

## Fifth Improvement Pass

This pass addressed the next ten self-review items.

1. Pipeline stages now write checkpoints, and recovered running jobs can be marked complete if their expected outputs already exist.
2. Demucs model and device are configurable from CLI, Web workflow controls, and settings.
3. Track previews support multi-segment extraction and a chorus-oriented preset.
4. Subtitle editing now includes range sliders, line-range shifting, and browser draft autosave for lyrics text.
5. Lyrics file upload handles `.txt`/`.lrc`, preserves the original file, detects common encodings, and records import warnings.
6. Instrumental loudness normalization is available as a separate CLI/Web stage.
7. Export ZIPs can include or exclude audio, MKV files, takes, and logs.
8. Web song pages show inline log tails in addition to log download links.
9. `ktv batch-stage` supports batch probe, preview, extract, and separate workflows.
10. The macOS starter runs Doctor first and opens the Doctor page before serving the workbench.

## Sixth Improvement Pass

This pass addressed the next ten self-review items.

1. `scripts/smoke_e2e.sh` now runs a real short import/probe/preview/extract/LRC-align/mux/ffprobe validation flow.
2. WAV quality reports now flag duration mismatches, channel mismatches, sample-rate mismatches, vocal clipping, and existing level issues.
3. CLI/Web can run the pipeline from a selected stage with `run-from` / `process-from`, complementing existing cancel and retry.
4. Import UX now has drag-and-drop upload styling, recent import records, duplicate source fingerprints, and song ID rename.
5. Subtitle editing now supports waveform click-to-time and line-range stretching in addition to edits and shifts.
6. Alignment supports explicit `lrc` backend and `auto` now prefers saved LRC timing before falling back to draft timing.
7. Web job tables show updated time and expected output hints for better status visibility.
8. Mux and replace-audio outputs are probed after creation and audited into `report.json`.
9. `doctor` checks include concrete fix commands for missing runtime dependencies.
10. Docs now include a deterministic bundled-sample smoke workflow and updated command reference.

## Product Hardening Pass

This pass addressed the twenty strict product-engineering review items.

1. Added a First Run Wizard and bundled sample import button.
2. Added URL import confirmation with explicit rights acknowledgement.
3. Added failure recovery UI with force rerun and run-from-failed-stage actions.
4. Added A/B review controls for current audio and saved instrumental takes.
5. Added Chinese quality recommendations alongside raw metrics.
6. Added a lightweight SSE job status endpoint and browser EventSource hook.
7. Added subtitle playhead coupling for focused timing inputs.
8. Added SRT and ASS lyric import into `alignment.json` and `lyrics.ass`.
9. Added `library/inbox` scan import from CLI and Web.
10. Added library search/filter controls.
11. Added disk usage reporting and a Web Disk Manager.
12. Added output template settings with template-named MKV copies.
13. Expanded export ZIPs into support bundles with Doctor, settings, storage, and environment data.
14. Added a player compatibility matrix for VLC, IINA, Infuse, QuickTime, and Windows Media Player.
15. Expanded install docs and browser-test optional dependency metadata.
16. Added Web batch-stage console.
17. Added copyright/permissions copy in the URL import flow.
18. Added explicit roadmap, v1/v2 boundaries, and non-goals.
19. Added take scoring so listening decisions are recorded.
20. Added focused tests for the new parsing, storage, Web, export, settings, and compatibility paths.

## Modular Product Pass

This pass addressed the strict 30-point module-level product review.

1. Added Web workflow tabs and a single-module launcher so track review, audio, lyrics, mux, outputs, and jobs can be opened directly.
2. Added CLI/Web `separate-sample` for short Demucs trial runs before processing a full song.
3. Added separation presets (`fast-review`, `balanced`, `clean-vocal`, `quality`) with model/device overrides.
4. Added CLI/Web `remake-track` for the common Track 1 -> instrumental -> replace Track 2 scenario.
5. Added CLI/Web external instrumental import through `set-instrumental` and Web upload.
6. Added embedded subtitle extraction into lyrics/alignment/ASS.
7. Added lyrics revision snapshots under `raw/{song_id}/lyrics-versions`.
8. Added song tags and rating metadata for library triage.
9. Added subtitle style settings and configurable MKV audio track titles.
10. Added residual vocal risk scoring and Chinese warnings for high vocal bleed.
11. Added Track Decision buttons for choosing, sampling, or remaking from each source audio track.
12. Added source subtitle track actions for using embedded subtitles as lyrics input.
13. Added copy-subtitles controls to replace-audio/remake workflows.
14. Added sample instrumental/vocal preview and download paths.
15. Added final MKV and audio-replaced MKV inline video preview.
16. Added macOS Finder reveal links for generated outputs.
17. Added Web job detail pages with params, progress, actions, and log tails.
18. Added batch console dry-run, audio-index, and separation-preset controls.
19. Improved URL rights text in Chinese for local-first personal-use workflows.
20. Added duplicate-source hints based on similar extension and size, complementing exact fingerprints.
21. Expanded library search to include tags.
22. Added keyboard/playhead helpers for subtitle timing buttons.
23. Added CPU retry and short-sample recovery actions after failures.
24. Added output settings for subtitle font size, margin, colors, and audio track names.
25. Added command-construction tests for subtitle extraction and configurable track titles.
26. Added unit tests for presets, lyrics revisions, tags/rating, ASS style, and residual vocal risk.
27. Added Web tests for module controls, job details, external instrumental upload, and localized rights copy.
28. Kept v1 dependency boundaries: no Node frontend and no MKVToolNix requirement.
29. Documented modular CLI usage in the README.
30. Added an acceptance checklist for manual and automated release verification.
