# Acceptance Checklist

Use this checklist before treating the local KTV workbench as releasable.

## Automated

```bash
.venv/bin/python -m ruff check .
.venv/bin/python -m pytest -q
.venv/bin/python -m pytest -q -m browser
scripts/smoke_e2e.sh
KTV_RUN_SLOW=1 .venv/bin/python -m pytest -q -m slow
.venv/bin/ktv preflight 朋友-周华健
.venv/bin/ktv mux-plan 朋友-周华健
.venv/bin/ktv replace-plan 朋友-周华健 --keep-audio-index 0
```

## Manual Product Scenarios

1. Import `assets/朋友-周华健.mkv` from the First Run Wizard.
2. Run Probe and confirm the UI shows video, two audio tracks, and one subtitle track.
3. Run Track Preview and listen to Track 1 and Track 2 segments.
4. Run `separate-sample` from Track 1 and listen to `instrumental.sample.wav`.
5. Confirm the sample has a saved take under `output/{song_id}/takes`.
6. Save source track roles and confirm they appear in Source Tracks.
7. Run full separation from Track 1 and listen to `instrumental.wav`.
8. If an external accompaniment is available, upload it with offset/gain/fit controls and confirm it becomes current.
9. Confirm the external accompaniment fit report appears in Preflight when `mix.wav` exists.
10. Extract embedded subtitles, then upload or edit `lyrics.txt` if the embedded text is not the real lyric.
11. Generate ASS, use line play buttons, shift one range, stretch one range, and save subtitle edits across all lines.
12. Preview `replace-plan`, then build audio-replaced MKV with original Track 1 and new instrumental Track 2.
13. Preview `mux-plan`, then build full KTV MKV and verify VLC/IINA show two audio tracks plus ASS subtitles.
14. Confirm the Task Modes panel offers instrumental-only, replace Track 2, existing lyrics, external instrumental, final MKV, and support package paths.
15. Confirm the advanced workbench is collapsed by default and can be opened when detailed controls are needed.
16. Confirm the Preflight panel and `ktv preflight` show readiness for sample review, instrumental review, replace-audio, and final MKV.
17. Dry-run `batch-recipe instrumental-review`, then queue it from the Web Batch Console.
18. Open the job detail page for a completed or failed job and confirm params/log tail are visible.
19. Export the support package and confirm reports, settings, lyrics, outputs, and takes are included.
20. On a 390px-wide mobile viewport, confirm the Home, Doctor, and song detail pages have no horizontal page overflow.
