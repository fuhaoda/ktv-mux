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

## Strict Product Engineering Pass

This pass implemented the follow-up 30-point hardening review with emphasis on independent modules and real user workflows.

1. Fixed the `ktv separate-sample` CLI dispatch bug where `--preset` was parsed but `args.separation_preset` was read.
2. Added CLI contract tests so every subcommand exposes help and `separate-sample` dispatch is covered.
3. Added `ktv preflight SONG_ID` for standalone readiness checks.
4. Added a reusable preflight module shared by CLI and Web.
5. Added Web Task Modes for instrumental-only, bad Track 2 replacement, existing lyrics, external instrumental, final MKV, and support package workflows.
6. Added a Preflight panel showing readiness for sample review, instrumental review, replace-audio, and final MKV.
7. Added warning aggregation from quality reports, sample reports, external instrumental fit reports, and MKV audits into Preflight.
8. Added explicit track decision badges for source default, selected separation source, kept guide track, and last remake source.
9. Added visible CLI `--audio-index` mapping beside each Web track.
10. Added fast-review defaults to per-track sample separation actions.
11. Added synchronized A/B review controls for visible mix, instrumental, and instrumental-take players.
12. Added external instrumental transcoding to 44.1 kHz stereo PCM WAV instead of byte-copying arbitrary audio into `instrumental.wav`.
13. Added external instrumental fit reports against `mix.wav` when available.
14. Added fit warnings for duration mismatch, sample-rate mismatch, channel mismatch, clipping, long silence, and very quiet audio.
15. Added Chinese fit recommendations for external accompaniment review.
16. Added media command tests for external audio WAV rendering.
17. Added quality tests for external instrumental fit analysis.
18. Updated Web upload tests to use a real tiny WAV and confirm fit-report persistence.
19. Added batch support for `batch-stage separate-sample`.
20. Fixed CLI forwarding for `batch-stage --separation-preset`.
21. Added pipeline tests proving `batch-stage separate-sample` passes audio index, timing, preset, and device.
22. Added failure playbooks with concrete next actions by failed stage.
23. Added mobile layout hardening for tables, task cards, rows, buttons, and top navigation.
24. Added browser regression checks for mobile page overflow on Home, Doctor, and song detail pages.
25. Added responsive table behavior so dense diagnostic/history/library tables do not expand the page width.
26. Updated README with `preflight`, external instrumental rendering, task modes, and batch sample separation.
27. Updated Start Here with `preflight` checks in instrumental, external-accompaniment, and mux flows.
28. Updated Acceptance with Task Modes, Preflight, external accompaniment fit, and mobile overflow checks.
29. Kept Node-free Web UI while adding richer browser behavior through the existing static JS file.
30. Preserved local-first and rights-confirmed boundaries while tightening module-level workflows.

## Product Engineering Closeout Pass

This pass implemented the follow-up 20-point product plan with emphasis on task-first UX, track decisions, mux safety, and maintainability.

1. Split the oversized server-rendered UI into `views.py`, `view_common.py`, `view_song.py`, and `view_admin.py`.
2. Split pipeline support helpers into `pipeline_support.py` so locks, validation, output discovery, and take archiving are isolated.
3. Collapsed the dense song workbench behind an Advanced Workbench disclosure so task cards remain the first-screen experience.
4. Added source audio track roles with manual `ktv track-role` persistence and Web Source Track controls.
5. Added inferred role hints for default tracks, karaoke/instrumental titles, and likely KTV second-track accompaniments.
6. Added `ktv mux-plan` and `ktv replace-plan` so final audio/subtitle order can be reviewed before writing MKVs.
7. Added a Web Mux Preview panel for final KTV and Track 2 replacement outputs.
8. Added external accompaniment offset, gain, fit-to-mix, and normalize controls in CLI and Web upload.
9. Added sample instrumental take archiving so short separation experiments are preserved for comparison.
10. Distinguished `instrumental-sample` takes from full instrumental takes.
11. Prevented sample takes from showing unsupported "Set Current" actions.
12. Expanded the subtitle timing editor from the first 24 lines to all aligned lines.
13. Added batch recipes for `instrumental-review`, `full-instrumental`, `replace-track2`, and `final-ktv`.
14. Added Web Batch Console recipe dry-run and queue controls.
15. Added CLI tests for external accompaniment fit options, track roles, mux plans, replace plans, and batch recipes.
16. Added media command tests for offset/gain/normalize render filters.
17. Added product-model tests for track role inference, mux plans, sample take kinds, and recipe dry-runs.
18. Updated README, Usage, Start Here, Architecture, and Acceptance docs for the new module workflows.
19. Preserved the old `ktv_mux.views` import surface while moving implementation into smaller modules.
20. Re-ran targeted tests after each structural pass before proceeding to full validation.
