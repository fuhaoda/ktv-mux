# Troubleshooting

## `Internal Server Error`

The Web UI now renders a friendly error page and writes stage failures to:

```text
library/work/{song_id}/status.json
library/output/{song_id}/report.json
```

Use:

```bash
ktv status SONG_ID
ktv doctor SONG_ID
```

The Web page also shows recent queued/running jobs from `library/jobs`, plus a Doctor panel with the most likely next action.

## Demucs Fails With `TorchCodec is required`

Install the separation extra:

```bash
.venv/bin/python -m pip install -e ".[separation]"
```

The extra includes `torchcodec`, which newer `torchaudio` versions require for saving WAV files.

## Python Version

Use Python 3.12. The local machine may also have Python 3.14, but the audio ML stack is more reliable under Python 3.12.

```bash
python3.12 -m venv .venv
```

## Track Choice Is Wrong

Run probe, generate previews, listen, then choose another track:

```bash
ktv probe SONG_ID
ktv preview-tracks SONG_ID --start 30 --duration 20
ktv extract SONG_ID --audio-index 1
ktv separate SONG_ID
```

In the Web UI, this is `Track 2`.

## Demucs Is Running For A Long Time

Open:

```text
library/work/{song_id}/logs/separate.log
```

The song detail page links to the same log after separation starts. First runs can be slow because Demucs downloads model weights.

Queued and running jobs can be canceled from the Web job table. Failed or canceled jobs can be retried from the same table. If cancellation is requested, the app writes `library/jobs/{job_id}.cancel` and supported subprocesses terminate cleanly.

## URL Download Fails

Open the import log:

```text
library/work/{song_id}/logs/import.log
```

The Web page links this log after URL import starts. The app does not bypass platform restrictions or copyright controls; use only URLs you have the right to process.

## Subtitles Are Early Or Late

Shift timing without rerunning alignment:

```bash
ktv shift SONG_ID --seconds 0.25   # later
ktv shift SONG_ID --seconds -0.25  # earlier
```

For one bad line, use the Web subtitle timing editor or:

```bash
ktv edit-line SONG_ID --index 0 --start 10.0 --end 13.2 --text "corrected lyric line"
```

## Output Was Overwritten

The latest files keep stable names, but every generated audio/MKV output is copied to:

```text
library/output/{song_id}/takes/
```

Use the Web Outputs panel to label takes, add notes, delete bad takes, or set an older take as current.

## One-Click Startup Does Not Open

macOS may require executable permission:

```bash
chmod +x scripts/*.sh scripts/*.command
scripts/ktv-start.command
```

To recreate the Desktop launcher:

```bash
scripts/install_macos_launcher.sh
```

## Web Server Port Already In Use

```bash
lsof -iTCP:8000 -sTCP:LISTEN -n -P
kill <PID>
ktv serve --host 127.0.0.1 --port 8000
```
