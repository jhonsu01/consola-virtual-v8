"""Pruebas de logica del motor de audio (no requieren dispositivo de audio)."""

import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from consola_v8.audio_engine import AudioEngine  # noqa: E402


def test_effects_count():
    assert len(AudioEngine.EFFECTS) == 12


def test_effect_names():
    expected = {
        "Despise", "Shot", "Beatings", "Coldfield", "Songs", "DogBarking",
        "Laughter", "Applause", "Kiss", "Awkward", "Minions", "Time",
    }
    assert set(AudioEngine.EFFECTS.keys()) == expected


def test_knob_set_get_clamp():
    eng = AudioEngine()
    eng.set_knob("MUSIC", 0.5)
    assert eng.get_knob("MUSIC") == 0.5
    eng.set_knob("MUSIC", 5.0)  # se almacena el valor crudo; el motor no recorta aqui
    assert eng.get_knob("MUSIC") == 5.0


def test_unknown_knob_ignored():
    eng = AudioEngine()
    eng.set_knob("NOPE", 0.3)
    assert "NOPE" not in eng.snapshot()["knobs"]


def test_dodge_ducking_state():
    eng = AudioEngine()
    eng.set_knob("MUSIC", 1.0)
    eng.set_mode("Dodge", True)
    eng.simulate_mic_activity(True)
    snap = eng.snapshot()
    assert snap["modes"]["Dodge"] is True
    assert snap["mic_active"] is True


def test_snapshot_structure():
    eng = AudioEngine()
    snap = eng.snapshot()
    assert set(snap.keys()) == {"knobs", "modes", "mic_active"}
    assert set(snap["knobs"].keys()) == set(AudioEngine.KNOBS)
