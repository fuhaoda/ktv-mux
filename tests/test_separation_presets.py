import pytest

from ktv_mux.errors import KtvError
from ktv_mux.separation_presets import preset_options, resolve_separation_preset


def test_resolve_separation_preset_defaults_and_overrides():
    preset = resolve_separation_preset("quality", device="cpu")

    assert preset["id"] == "quality"
    assert preset["model"] == "htdemucs_ft"
    assert preset["device"] == "cpu"
    assert preset_options()


def test_resolve_separation_preset_rejects_unknown():
    with pytest.raises(KtvError):
        resolve_separation_preset("unknown")
