# Installation And First Run

For the shortest user-facing guide, start with [Start Here / 快速开始](START_HERE.md).

## macOS

```bash
scripts/bootstrap_mac.sh
scripts/ktv-start.command
```

The launcher starts the local FastAPI UI and opens Doctor first. From there, use **First Run Wizard** to import the bundled sample without typing a path.

If port `8000` is already running ktv-mux, the launcher opens that existing app. If `8000` is occupied by another process, it automatically tries `8001` through `8010`.

Optional Desktop launcher:

```bash
scripts/install_macos_launcher.sh
```

This creates:

```text
~/Desktop/KTV Mux.command
```

## Manual Setup

```bash
python3.12 -m venv .venv
.venv/bin/python -m pip install --upgrade pip
.venv/bin/python -m pip install -e ".[web,dev,separation]"
.venv/bin/ktv --library library doctor
.venv/bin/ktv --library library serve --host 127.0.0.1 --port 8000
```

Open:

```text
http://127.0.0.1:8000
```

## Optional Extras

```bash
pip install -e ".[web,separation,alignment]"
pip install -e ".[browser]"
playwright install chromium
```

`browser` is only needed for Playwright UI smoke tests. Demucs and FunASR remain optional because they can be slow and model-heavy.

## Product Safety

URL imports require a confirmation page in the Web UI. The tool is intended only for local files or URLs that the user has the right to process.
