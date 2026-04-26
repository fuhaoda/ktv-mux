# Acceptance Checklist

Use this checklist before treating the local KTV workbench as releasable.

## Automated

```bash
.venv/bin/python -m ruff check .
.venv/bin/python -m pytest -q
.venv/bin/python -m pytest -q -m browser
scripts/smoke_e2e.sh
KTV_RUN_SLOW=1 .venv/bin/python -m pytest -q -m slow
```

## Manual Product Scenarios

1. Import `assets/朋友-周华健.mkv` from the First Run Wizard.
2. Run Probe and confirm the UI shows video, two audio tracks, and one subtitle track.
3. Run Track Preview and listen to Track 1 and Track 2 segments.
4. Run `separate-sample` from Track 1 and listen to `instrumental.sample.wav`.
5. Run full separation from Track 1 and listen to `instrumental.wav`.
6. If an external accompaniment is available, upload it with "Use External Instrumental" and confirm it becomes current.
7. Extract embedded subtitles, then upload or edit `lyrics.txt` if the embedded text is not the real lyric.
8. Generate ASS, use line play buttons, shift one range, and save subtitle edits.
9. Build audio-replaced MKV with original Track 1 and new instrumental Track 2.
10. Build full KTV MKV and verify VLC/IINA show two audio tracks plus ASS subtitles.
11. Open the job detail page for a completed or failed job and confirm params/log tail are visible.
12. Export the support package and confirm reports, settings, lyrics, outputs, and takes are included.
