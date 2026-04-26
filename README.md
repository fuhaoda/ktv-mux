# ktv-mux

Local-first KTV MKV workshop for macOS. Import a music video, choose the source audio track, generate an instrumental with Demucs, listen to the result, tune subtitles, and optionally create an MKV where the new instrumental replaces Track 2.

The first polished workflow is built around real KTV production:

1. Import a local file or URL.
2. Probe the media tracks.
3. Extract Track 1 or Track 2.
4. Preview source audio tracks before deciding which one to separate.
5. Generate `instrumental.wav`.
6. Listen before committing and inspect the quality report.
7. Shift or edit ASS timing when needed.
8. Build an audio-replaced MKV or a full KTV MKV with ASS lyrics.

## Quick Start

Use Python 3.12.

Most users should start here:

- [Start Here / 快速开始](docs/START_HERE.md)
- [Bundled Sample Workflow](docs/SAMPLE_WORKFLOW.md)

One-click macOS path:

```bash
scripts/bootstrap_mac.sh
scripts/ktv-start.command
```

To create a Desktop launcher:

```bash
scripts/install_macos_launcher.sh
```

Manual path:

```bash
python3.12 -m venv .venv
source .venv/bin/activate
python -m pip install -e ".[web,dev,separation]"
ktv serve --host 127.0.0.1 --port 8000
```

Open:

```text
http://127.0.0.1:8000
```

For the first run, open `/wizard` or click **First Run Wizard** in the header. It can import the bundled `assets/朋友-周华健.mkv` sample without typing a file path.

If port `8000` is already running ktv-mux, `scripts/ktv-start.command` opens it. If another app is using `8000`, the script tries the next free local port from `8001` to `8010`.

## Try The Bundled Sample

```bash
ktv import assets/朋友-周华健.mkv
ktv probe 朋友-周华健
ktv preview-tracks 朋友-周华健 --start 30 --duration 20
ktv extract 朋友-周华健 --audio-index 0
ktv separate 朋友-周华健
```

Listen to:

```text
library/output/朋友-周华健/instrumental.wav
```

Then create an MKV with the original Track 1 and the new instrumental as Track 2:

```bash
ktv replace-audio 朋友-周华健 --keep-audio-index 0
```

For a faster check before running the full song:

```bash
ktv separate-sample 朋友-周华健 --audio-index 0 --start 45 --duration 30
```

If you already have a good accompaniment from another tool:

```bash
ktv set-instrumental 朋友-周华健 /path/to/instrumental.wav --label "manual candidate"
```

Output:

```text
library/output/朋友-周华健/朋友-周华健.audio-replaced.mkv
```

## CLI Reference

```bash
ktv import PATH_OR_URL [--song-id ID]
ktv import-many FILE1 FILE2
ktv metadata SONG_ID --title "Title" --artist "Artist"
ktv metadata SONG_ID --tags "duet,needs-review" --rating 4
ktv rename OLD_SONG_ID NEW_SONG_ID
ktv probe SONG_ID
ktv preview-tracks SONG_ID [--start SECONDS] [--duration SECONDS] [--count 3] [--preset chorus]
ktv extract SONG_ID --audio-index 0
ktv separate SONG_ID [--preset balanced|fast-review|clean-vocal|quality] [--model htdemucs] [--device auto]
ktv separate-sample SONG_ID --audio-index 0 [--start 45] [--duration 30]
ktv set-instrumental SONG_ID AUDIO_PATH [--label "external"]
ktv normalize SONG_ID [--target-i -16] [--replace-current]
ktv replace-audio SONG_ID --keep-audio-index 0 [--duration-limit SECONDS]
ktv remake-track SONG_ID --audio-index 0 --keep-audio-index 0
ktv lyrics SONG_ID lyrics.txt
ktv extract-subtitles SONG_ID [--subtitle-index 0]
ktv lyrics-versions SONG_ID
ktv align SONG_ID --backend simple|lrc|funasr
ktv shift SONG_ID --seconds 0.35
ktv edit-line SONG_ID --index 0 --start 10.2 --end 13.4 --text "第一句歌词"
ktv mux SONG_ID [--duration-limit SECONDS]
ktv run-from SONG_ID separate
ktv clean-work SONG_ID
ktv takes SONG_ID
ktv take-note SONG_ID FILENAME --label "good" --note "less vocal bleed"
ktv take-current SONG_ID FILENAME
ktv take-delete SONG_ID FILENAME
ktv export SONG_ID [--include-logs] [--no-audio] [--no-mkv] [--no-takes]
ktv inbox-scan [--limit N]
ktv storage [SONG_ID]
ktv next SONG_ID
ktv jobs
ktv jobs-prune
ktv batch-stage probe|preview-tracks|extract|separate [--dry-run] [--skip-completed] [--limit N]
ktv settings [--preview-start 30 --preview-duration 20 --preview-count 2 --demucs-device mps]
ktv delete SONG_ID
ktv status SONG_ID
ktv doctor [SONG_ID]
ktv serve
```

`song_id` is optional on import. Local files default to the original filename without extension.

Web `Track 1` is CLI `--audio-index 0`; Web `Track 2` is CLI `--audio-index 1`.

## Project Docs

- [Start Here / 快速开始](docs/START_HERE.md)
- [Usage](docs/USAGE.md)
- [Bundled Sample Workflow](docs/SAMPLE_WORKFLOW.md)
- [Installation](docs/INSTALL.md)
- [Architecture](docs/ARCHITECTURE.md)
- [Troubleshooting](docs/TROUBLESHOOTING.md)
- [Roadmap And Boundaries](docs/ROADMAP.md)
- [Implemented Improvements](docs/IMPROVEMENTS.md)
- [Acceptance Checklist](docs/ACCEPTANCE.md)

## Development

```bash
make setup-separation
make lint
make test
make serve
```

The test suite includes unit tests for path handling, command construction, ASS generation, job persistence, Web upload behavior, and FFmpeg integration against the bundled sample. Demucs has a separate slow smoke test:

```bash
KTV_RUN_SLOW=1 .venv/bin/python -m pytest -q -m slow
```

Run a real short end-to-end FFmpeg smoke without Demucs:

```bash
scripts/smoke_e2e.sh
```

## Notes

- `ffmpeg`, `ffprobe`, and `yt-dlp` are external command dependencies.
- Demucs model weights download on first use.
- Long-running Web stages use a local file-backed job queue under `library/jobs`.
- Running Web jobs can be canceled; supported subprocesses receive a cancel signal through `library/jobs/{job_id}.cancel`.
- Stage checkpoints are written under `library/work/{song_id}/checkpoints.json` for better recovery.
- Muxed MKVs are probed after creation and audited in `report.json`.
- Local imports record a lightweight source fingerprint and possible duplicate sources.
- Finished Web jobs can be pruned from the Web UI or with `ktv jobs-prune`.
- Demucs logs are written under `library/work/{song_id}/logs/separate.log`.
- URL download logs are written under `library/work/{song_id}/logs/import.log`.
- Source track previews are written under `library/work/{song_id}/track-previews`.
- Each generated audio or MKV output also keeps a versioned copy under `library/output/{song_id}/takes`.
- `ktv export SONG_ID` creates `library/output/{song_id}/{song_id}.package.zip`.
- The package ZIP includes a support bundle with Doctor, settings, storage, and environment reports.
- `scripts/ktv-start.command` runs Doctor first and opens `/doctor`.
- Generated media under `library/` is ignored by git.
- Only process media you have the right to use.
- URL downloads require rights confirmation in the Web UI; the project does not implement DRM bypass or copyright-evasion workflows.
- Product scope and non-goals are tracked in `docs/ROADMAP.md`.
