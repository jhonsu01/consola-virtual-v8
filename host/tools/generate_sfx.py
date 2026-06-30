"""Genera 12 efectos WAV de marcador de posicion (placeholder).

Estos sonidos son tonos sinteticos cortos y libres de derechos para que la
consola funcione de inmediato. Reemplaza los archivos en ``consola_v8/sfx/``
por tus propios efectos manteniendo los mismos nombres.

Uso:
    python tools/generate_sfx.py
"""

from __future__ import annotations

import math
import os
import struct
import wave

SAMPLE_RATE = 44100

# Cada efecto: (frecuencia_base_hz, duracion_seg, forma)
# forma: 'tone' senoidal, 'noise' ruido, 'sweep' barrido, 'pulse' tren de pulsos.
SPECS = {
    "despise":    (180, 0.45, "pulse"),
    "shot":       (90,  0.30, "noise"),
    "beatings":   (110, 0.60, "pulse"),
    "coldfield":  (300, 0.90, "sweep"),
    "songs":      (523, 0.70, "tone"),
    "dogbarking": (240, 0.40, "pulse"),
    "laughter":   (440, 0.80, "sweep"),
    "applause":   (1000, 0.90, "noise"),
    "kiss":       (660, 0.25, "tone"),
    "awkward":    (1500, 0.50, "tone"),
    "minions":    (880, 0.55, "sweep"),
    "time":       (784, 0.50, "pulse"),
}


def _sample(shape: str, freq: float, t: float, dur: float) -> float:
    import random

    env = math.sin(math.pi * t / dur)  # envolvente suave (fade in/out)
    if shape == "tone":
        val = math.sin(2 * math.pi * freq * t)
    elif shape == "noise":
        val = (random.random() * 2 - 1) * 0.8
    elif shape == "sweep":
        f = freq * (1 + t / dur)
        val = math.sin(2 * math.pi * f * t)
    else:  # pulse
        val = 1.0 if int(t * freq) % 2 == 0 else -1.0
        val *= 0.6
    return max(-1.0, min(1.0, val * env * 0.7))


def write_wav(path: str, freq: float, dur: float, shape: str) -> None:
    n = int(SAMPLE_RATE * dur)
    frames = bytearray()
    for i in range(n):
        t = i / SAMPLE_RATE
        amp = int(_sample(shape, freq, t, dur) * 32767)
        frames += struct.pack("<h", amp)
    with wave.open(path, "w") as wav:
        wav.setnchannels(1)
        wav.setsampwidth(2)
        wav.setframerate(SAMPLE_RATE)
        wav.writeframes(bytes(frames))


def main() -> None:
    here = os.path.dirname(os.path.abspath(__file__))
    out_dir = os.path.join(here, "..", "consola_v8", "sfx")
    out_dir = os.path.abspath(out_dir)
    os.makedirs(out_dir, exist_ok=True)
    for name, (freq, dur, shape) in SPECS.items():
        path = os.path.join(out_dir, f"{name}.wav")
        write_wav(path, freq, dur, shape)
        print(f"  generado: {path}")
    print(f"Total: {len(SPECS)} efectos en {out_dir}")


if __name__ == "__main__":
    main()
