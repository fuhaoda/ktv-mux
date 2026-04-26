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
```

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

Run probe first and choose another track:

```bash
ktv probe SONG_ID
ktv extract SONG_ID --audio-index 1
ktv separate SONG_ID
```

In the Web UI, this is `Track 2`.

## Web Server Port Already In Use

```bash
lsof -iTCP:8000 -sTCP:LISTEN -n -P
kill <PID>
ktv serve --host 127.0.0.1 --port 8000
```

