# Bundled Sample Workflow

This is the shortest repeatable check from `assets/朋友-周华健.mkv` to a playable KTV-style MKV.

For a scenario-oriented Chinese/English guide, see [Start Here / 快速开始](START_HERE.md).

## 1. Start

```bash
cd /Users/hfu@amgen.com/Documents/MyGit/ktv-mux
scripts/bootstrap_mac.sh
scripts/ktv-start.command
```

Open `http://127.0.0.1:8000`.

## 2. Import

Use `Choose File` and select:

```text
assets/朋友-周华健.mkv
```

The song ID defaults to `朋友-周华健`.

The song page opens with Task Modes. Use those shortcuts when you only want an instrumental, want to replace a bad Track 2, already have lyrics, or already have an external accompaniment.

## 3. Inspect Tracks

Open the song page and run:

```text
Probe
Preview Tracks
```

Listen to the generated track previews before choosing the source audio track. Web `Track 1` is CLI `--audio-index 0`.

## 4. Generate Instrumental

Run:

```text
Extract Audio
Separate
```

Then listen to:

```text
library/output/朋友-周华健/instrumental.wav
```

If the level is wrong, use `Normalize` and compare `instrumental.normalized.wav`.

If you do not want to wait for the full song yet, run `Sample Separate` first. It creates:

```text
library/output/朋友-周华健/instrumental.sample.wav
```

## 5. Add Lyrics

Paste lyrics into the Lyrics panel or upload a `.txt` / `.lrc` file. For `.lrc`, choose `lrc` in the Generate ASS backend dropdown to use the timestamps directly.

After generating ASS, use the timing table to edit individual lines, shift a line range, stretch a section, or click the waveform to fill a focused time input.

## 6. Build Output

For replacing Track 2 while keeping original Track 1:

```text
Replace Track 2
```

For a full KTV MKV with generated ASS:

```text
Build KTV MKV
```

The final outputs are under:

```text
library/output/朋友-周华健/
```

Each generated audio/MKV also gets a versioned copy under `takes/`, and `report.json` includes stream audits plus quality warnings.

Before treating the file as finished, check the Preflight panel or run:

```bash
.venv/bin/ktv preflight 朋友-周华健
```

## CLI Smoke

For CI-style validation without a full Demucs run:

```bash
scripts/smoke_e2e.sh
```
