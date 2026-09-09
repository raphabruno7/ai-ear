"""WebRTC audio pre-processing for the STT feed — shared by the live listener
and the eval harness so both measure the *same* pipeline.

Spec is a comma list in the `AUDIO_APM` env (or `--apm` in eval):
    ns   noise suppression
    hpf  high-pass filter (removes rumble / DC)
    agc  automatic gain control
Empty / unset = passthrough (default). Echo cancellation is deliberately absent:
it needs a far-end reference stream, and this listener is passive (one track per
speaker, nothing played back) — there is no echo to cancel.

APM requires 10 ms frames. Callers must feed 10 ms of 16 kHz mono PCM per call.
"""

from __future__ import annotations

FRAME_MS = 10


def build_apm(spec: str | None):
    """`AudioProcessingModule` for the spec, or None for passthrough."""
    flags = {s.strip() for s in (spec or "").split(",") if s.strip()}
    if not flags:
        return None
    unknown = flags - {"ns", "hpf", "agc"}
    if unknown:
        raise ValueError(f"unknown AUDIO_APM flags: {sorted(unknown)}")
    from livekit import rtc
    return rtc.AudioProcessingModule(
        noise_suppression="ns" in flags,
        high_pass_filter="hpf" in flags,
        auto_gain_control="agc" in flags,
        echo_cancellation=False,
    )


def process_pcm(apm, pcm: bytes, sample_rate: int = 16_000) -> bytes:
    """Run one 10 ms PCM frame through the APM. Passthrough if apm is None or the
    chunk isn't exactly 10 ms (a short track-end tail goes through untouched —
    same behaviour in the live listener and the eval)."""
    want = sample_rate * FRAME_MS // 1000 * 2  # bytes in a 10 ms s16le mono frame
    if apm is None or len(pcm) != want:
        return pcm
    from livekit import rtc
    frame = rtc.AudioFrame(pcm, sample_rate, 1, len(pcm) // 2)
    apm.process_stream(frame)
    return bytes(frame.data)


def demo() -> None:
    import numpy as np

    assert build_apm("") is None and build_apm(None) is None
    try:
        build_apm("ns,bogus"); raise AssertionError("should reject bogus flag")
    except ValueError:
        pass
    apm = build_apm("ns,hpf")
    n = 16_000 * FRAME_MS // 1000
    rng = np.random.default_rng(0)
    loud = (rng.standard_normal(n) * 3000).astype("<i2").tobytes()
    for _ in range(30):
        out = process_pcm(apm, (rng.standard_normal(n) * 3000).astype("<i2").tobytes())
    rms_in = float(np.sqrt(np.mean(np.frombuffer(loud, "<i2").astype(float) ** 2)))
    rms_out = float(np.sqrt(np.mean(np.frombuffer(out, "<i2").astype(float) ** 2)))
    assert rms_out < rms_in * 0.6, (rms_in, rms_out)  # NS knocks down pure noise
    assert process_pcm(None, loud) == loud
    print("audio_apm demo ok")


if __name__ == "__main__":
    demo()
