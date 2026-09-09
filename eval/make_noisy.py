"""Build noisy copies of the golden-set audio at target SNRs, so the DSP A/B
has something to bite on — on the clean `say`-TTS wavs, noise suppression has
nothing to remove.

    python make_noisy.py               # SNR 20 / 10 / 5 dB
    python make_noisy.py --snr 10
    python make_noisy.py --check       # verify realised SNR is within ±1 dB

Noise = pink (1/f) broadband + a 60 Hz mains tone + DC offset — the broadband
part is what NS targets, the tone + DC is what the high-pass filter targets.
Deterministic across processes (crc32 seed per sample). Output:
dataset/audio_noisy/<snr>/<id>.wav (gitignored, like dataset/audio/).
"""

from __future__ import annotations

import argparse
import wave
import zlib
from pathlib import Path

import numpy as np

HERE = Path(__file__).parent
CLEAN = HERE / "dataset" / "audio"
OUT = HERE / "dataset" / "audio_noisy"
SNRS = (20, 10, 5)
SR = 16_000


def _pink(n: int, rng: np.random.Generator) -> np.ndarray:
    """Pink noise via 1/sqrt(f) shaping of white noise in the frequency domain."""
    white = rng.standard_normal(n)
    spec = np.fft.rfft(white)
    f = np.arange(spec.size)
    f[0] = 1
    spec /= np.sqrt(f)
    out = np.fft.irfft(spec, n)
    return out / (np.sqrt(np.mean(out ** 2)) + 1e-12)


def _noise_bed(n: int, seed: int) -> np.ndarray:
    rng = np.random.default_rng(seed)
    t = np.arange(n) / SR
    bed = _pink(n, rng)
    bed += 0.15 * np.sin(2 * np.pi * 60 * t)   # mains hum — HPF fodder
    bed += 0.05                                 # DC offset — HPF fodder
    return bed / (np.sqrt(np.mean(bed ** 2)) + 1e-12)


def _read(path: Path) -> np.ndarray:
    with wave.open(str(path)) as w:
        assert w.getframerate() == SR and w.getnchannels() == 1, path
        return np.frombuffer(w.readframes(w.getnframes()), dtype="<i2").astype(np.float64)


def _write(path: Path, sig: np.ndarray) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    clipped = np.clip(sig, -32768, 32767).astype("<i2")
    with wave.open(str(path), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(SR)
        w.writeframes(clipped.tobytes())


def _mix(clean: np.ndarray, snr_db: float, seed: int) -> np.ndarray:
    rms_clean = np.sqrt(np.mean(clean ** 2)) + 1e-12
    bed = _noise_bed(len(clean), seed)          # already unit-RMS
    target_rms_noise = rms_clean / (10 ** (snr_db / 20))
    return clean + bed * target_rms_noise


def realised_snr(clean: np.ndarray, noisy: np.ndarray) -> float:
    noise = noisy - clean
    return 20 * np.log10((np.sqrt(np.mean(clean ** 2)) + 1e-12) /
                         (np.sqrt(np.mean(noise ** 2)) + 1e-12))


def build(snrs=SNRS) -> int:
    wavs = sorted(CLEAN.glob("*.wav"))
    if not wavs:
        raise SystemExit("no clean audio — run make_dataset.py first")
    n = 0
    for snr in snrs:
        for wav in wavs:
            clean = _read(wav)
            noisy = _mix(clean, snr, seed=zlib.crc32(f"{wav.stem}:{snr}".encode()))
            _write(OUT / str(snr) / wav.name, noisy)
            n += 1
    print(f"wrote {n} files to {OUT}/{{{','.join(map(str, snrs))}}}/")
    return n


def check() -> None:
    wavs = sorted(CLEAN.glob("*.wav"))[:5]
    for snr in SNRS:
        for wav in wavs:
            clean = _read(wav)
            noisy_f = _mix(clean, snr, seed=zlib.crc32(f"{wav.stem}:{snr}".encode()))
            _write(OUT / "_check.wav", noisy_f)
            noisy = _read(OUT / "_check.wav")
            got = realised_snr(clean, noisy)
            assert abs(got - snr) <= 1.0, f"{wav.stem} @ {snr}dB -> realised {got:.2f}dB"
    (OUT / "_check.wav").unlink(missing_ok=True)
    # cross-process determinism: seed must not depend on PYTHONHASHSEED
    import subprocess
    import sys
    w = wavs[0]
    b1 = _mix(_read(w), 10, seed=zlib.crc32(f"{w.stem}:10".encode())).round().tobytes()
    b2 = subprocess.run(
        [sys.executable, "-c",
         f"import sys; sys.path.insert(0,{str(HERE)!r}); import make_noisy as m;"
         f"import zlib; print(m._mix(m._read({str(w)!r}),10,zlib.crc32(b'{w.stem}:10')).round().tobytes().hex())"],
        capture_output=True, text=True, env={"PYTHONHASHSEED": "1"}).stdout.strip()
    assert b1.hex() == b2, "noise bed is not reproducible across processes"
    print("make_noisy check ok — realised SNR within ±1 dB, reproducible across processes")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--snr", type=int, action="append", help="target SNR(s); default 20/10/5")
    ap.add_argument("--check", action="store_true")
    a = ap.parse_args()
    if a.check:
        check()
    else:
        build(tuple(a.snr) if a.snr else SNRS)
