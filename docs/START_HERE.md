# Start Here / 快速开始

This is the practical entry point for running ktv-mux locally on macOS.

这是给日常使用准备的入口文档：先启动，再按你的场景选择一个模块单独跑。

## 1. First-Time Setup

Use Python 3.12. From the repository root:

```bash
cd /Users/hfu@amgen.com/Documents/MyGit/ktv-mux
scripts/bootstrap_mac.sh
```

The bootstrap script creates `.venv`, installs the Web UI, developer tools, and Demucs separation dependencies, then runs `ktv doctor`.

## 2. Start The App

```bash
scripts/ktv-start.command
```

Open:

```text
http://127.0.0.1:8000
```

If port `8000` is already running ktv-mux, the script opens it. If port `8000` is used by another app, it tries `8001` through `8010`.

Optional Desktop shortcut:

```bash
scripts/install_macos_launcher.sh
```

Then double-click `KTV Mux.command` on the Desktop.

## 3. First Test

Click **First Run Wizard**, then import the bundled sample:

```text
assets/朋友-周华健.mkv
```

The song page should show:

- 1 video track
- 2 audio tracks
- 1 embedded ASS subtitle track

## 4. Common Scenarios

### I Want To Check Track 1 And Track 2

Web:

1. Open the song.
2. Click **Read Tracks**.
3. Click **Build Previews**.
4. Listen to each track preview in **Source Tracks**.
5. Save a role for each track, for example guide vocal or instrumental.

CLI:

```bash
.venv/bin/ktv probe 朋友-周华健
.venv/bin/ktv preview-tracks 朋友-周华健 --preset chorus --count 2 --duration 12
.venv/bin/ktv track-role 朋友-周华健 --audio-index 0 --role guide-vocal --note "original guide"
.venv/bin/ktv track-role 朋友-周华健 --audio-index 1 --role instrumental --note "existing backing candidate"
```

Web `Track 1` is CLI `--audio-index 0`; Web `Track 2` is CLI `--audio-index 1`.

### I Want To Generate Only An Instrumental

Web:

1. Choose the source track in **Extract Audio**.
2. Click **Extract**.
3. Click **Try Segment** first if you only want a 30-second test.
4. Listen to `Sample Instrumental`.
5. Click **Make Stem** for the full song only if the sample is acceptable.
6. Listen to `Instrumental` in **Audio Preview**.

CLI:

```bash
.venv/bin/ktv extract 朋友-周华健 --audio-index 0
.venv/bin/ktv separate-sample 朋友-周华健 --audio-index 0 --start 45 --duration 30
.venv/bin/ktv separate 朋友-周华健 --preset balanced --device auto
.venv/bin/ktv preflight 朋友-周华健
```

Output:

```text
library/output/朋友-周华健/instrumental.wav
library/output/朋友-周华健/instrumental.sample.wav
library/output/朋友-周华健/takes/
```

### I Already Have A Good Instrumental

Web:

1. Use the **I Already Have Instrumental** task card, or open **Advanced Workbench**.
2. Upload the audio file.
3. If needed, set offset seconds, gain dB, fit-to-mix, or normalize.
4. The uploaded file becomes the current `instrumental.wav`.

CLI:

```bash
.venv/bin/ktv set-instrumental 朋友-周华健 /path/to/instrumental.wav --label "manual candidate" --fit-to-mix --offset 0.10 --gain-db -1.5
.venv/bin/ktv preflight 朋友-周华健
```

The imported accompaniment is rendered to `instrumental.wav` as WAV and checked against `mix.wav` when available.

### Track 2 Is Bad And I Want To Replace It

Web:

1. Use **Sample Separate** first.
2. If the sample is acceptable, use **Remake Track** or **Replace Track 2**.
3. Check **Mux Preview** before writing the MKV.
4. Check **Outputs** and play the audio-replaced MKV in the browser.

CLI:

```bash
.venv/bin/ktv remake-track 朋友-周华健 --audio-index 0 --keep-audio-index 0
.venv/bin/ktv replace-plan 朋友-周华健 --keep-audio-index 0
```

Output:

```text
library/output/朋友-周华健/朋友-周华健.audio-replaced.mkv
```

### I Already Have Lyrics

Plain text, LRC, SRT, and ASS are accepted.

Web:

1. Paste lyrics into **Subtitle Workbench**, or upload a lyrics file.
2. Click **Generate ASS**.
3. Use the timing editor to shift, stretch, or edit lines.

CLI:

```bash
.venv/bin/ktv lyrics 朋友-周华健 path/to/lyrics.lrc
.venv/bin/ktv align 朋友-周华健 --backend lrc
```

For plain text without timestamps:

```bash
.venv/bin/ktv align 朋友-周华健 --backend simple
```

### I Want To Use Embedded Subtitles

Web:

1. Run **Read Tracks**.
2. In **Source Tracks**, click **Use As Lyrics** on the embedded subtitle track.

CLI:

```bash
.venv/bin/ktv extract-subtitles 朋友-周华健 --subtitle-index 0
```

The bundled sample's embedded ASS is a watermark-style subtitle, not a trusted lyric source.

### I Want The Final KTV MKV

You need:

- source video
- `instrumental.wav`
- `mix.wav`
- `lyrics.ass`

CLI:

```bash
.venv/bin/ktv mux 朋友-周华健
.venv/bin/ktv preflight 朋友-周华健
.venv/bin/ktv mux-plan 朋友-周华健
```

Output:

```text
library/output/朋友-周华健/朋友-周华健.ktv.mkv
```

## 5. Where Files Go

```text
library/raw/{song_id}/       source media, lyrics.txt, song.json
library/work/{song_id}/      mix.wav, vocals.wav, logs, alignment.json
library/output/{song_id}/    instrumental.wav, lyrics.ass, report.json, final MKVs, takes/
```

Generated audio/MKV outputs keep timestamped copies under:

```text
library/output/{song_id}/takes/
```

## 6. Health Checks

```bash
.venv/bin/ktv doctor
.venv/bin/ktv doctor 朋友-周华健
.venv/bin/ktv status 朋友-周华健
```

For development verification:

```bash
.venv/bin/python -m ruff check .
.venv/bin/python -m pytest -q
scripts/smoke_e2e.sh
```

Batch dry-run before expensive work:

```bash
.venv/bin/ktv batch-recipe instrumental-review --dry-run
.venv/bin/ktv batch-stage separate-sample --dry-run
```

## 7. Product Boundary

Use only local files or URLs you have the right to process. The tool does not implement DRM bypass, access-control bypass, or copyright-evasion behavior.
