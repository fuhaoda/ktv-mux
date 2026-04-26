import importlib.util
import os
from pathlib import Path

import pytest

from ktv_mux.commands import require_command, run_command
from ktv_mux.library import import_source
from ktv_mux.paths import LibraryPaths
from ktv_mux.pipeline import Pipeline

pytestmark = pytest.mark.slow

ASSET = Path("assets/朋友-周华健.mkv")


def test_demucs_separation_smoke_on_short_sample(tmp_path):
    if os.environ.get("KTV_RUN_SLOW") != "1":
        pytest.skip("set KTV_RUN_SLOW=1 to run Demucs smoke test")
    if importlib.util.find_spec("demucs") is None:
        pytest.skip("demucs is not installed")
    if not ASSET.exists():
        pytest.skip("sample asset not present")
    require_command("ffmpeg")

    library = LibraryPaths(tmp_path / "library")
    import_source(str(ASSET), library=library)
    mix = library.mix_wav("朋友-周华健")
    mix.parent.mkdir(parents=True, exist_ok=True)
    run_command(
        [
            "ffmpeg",
            "-y",
            "-hide_banner",
            "-t",
            "5",
            "-i",
            str(library.source_path("朋友-周华健")),
            "-map",
            "0:a:0",
            "-vn",
            "-ac",
            "2",
            "-ar",
            "44100",
            "-c:a",
            "pcm_s16le",
            str(mix),
        ]
    )

    Pipeline(library).separate("朋友-周华健")

    assert library.instrumental_wav("朋友-周华健").exists()
    assert library.vocals_wav("朋友-周华健").exists()
