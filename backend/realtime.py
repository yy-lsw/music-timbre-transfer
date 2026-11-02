#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Real-time (live microphone) voice changer.

Unlike Seed-VC, which converts an uploaded file in high quality, this module
processes the microphone stream on the fly so you can hear the changed voice
almost instantly.  It is DSP based (pitch + formant + effects) and runs on the
CPU, so it also works on the 4GB laptop GPU without loading the big model.

The stream is processed in short overlapping blocks with a Hann-window
overlap-add, which keeps latency low (~50 ms) and avoids clicks between blocks.
"""

import threading

import numpy as np
from scipy.signal import istft, resample, stft

try:
    import sounddevice as sd
    HAS_SOUNDDEVICE = True
except Exception:  # pragma: no cover - hardware/OS dependent
    sd = None
    HAS_SOUNDDEVICE = False

from .config import TARGET_SAMPLE_RATE
from .effects import AudioEffects


BLOCK_SIZE = 2048
HOP_SIZE = 1024
N_FFT = 2048
STFT_HOP = 512


REALTIME_PRESETS = {
    "female": {"label": "女声", "pitch_semitones": 5.0, "formant_ratio": 1.18},
    "male": {"label": "男声", "pitch_semitones": -5.0, "formant_ratio": 0.85},
    "child": {"label": "童声", "pitch_semitones": 8.0, "formant_ratio": 1.25},
    "deep": {"label": "低沉", "pitch_semitones": -8.0, "formant_ratio": 0.78},
    "robot": {"label": "机器人", "pitch_semitones": 0.0, "formant_ratio": 1.0, "robot": True},
    "bypass": {"label": "原声直通", "pitch_semitones": 0.0, "formant_ratio": 1.0},
}


def fast_pitch_shift(x, sr, semitones, n_fft=N_FFT, hop=STFT_HOP):
    """Vectorized phase-vocoder pitch shift for a mono float32 signal.

    Mirrors ``AudioEffects._pitch_shift`` but replaces the per-frame Python
    loop with vectorized NumPy gathers and a cumulative sum, which is fast
    enough for real-time use.  Returns a signal of the same length as ``x``.
    """
    x = np.asarray(x, dtype=np.float32)
    if abs(float(semitones)) < 1e-4 or len(x) < n_fft:
        return x.copy()

    rate = 2.0 ** (float(semitones) / 12.0)
    _, _, spectrum = stft(
        x,
        fs=sr,
        window="hann",
        nperseg=n_fft,
        noverlap=n_fft - hop,
        boundary="zeros",
        padded=True,
    )
    n_freq = spectrum.shape[0]
    n_frames = spectrum.shape[1]

    phase_advance = 2.0 * np.pi * hop * np.arange(n_freq) / n_fft
    time_steps = np.arange(0.0, float(n_frames), rate)
    frames = np.minimum(time_steps.astype(np.int64), n_frames - 1)
    next_frames = np.minimum(frames + 1, n_frames - 1)
    alpha = (time_steps - frames).astype(np.float32)

    magnitude = (
        (1.0 - alpha)[None, :] * np.abs(spectrum[:, frames])
        + alpha[None, :] * np.abs(spectrum[:, next_frames])
    )
    delta_phase = (
        np.angle(spectrum[:, next_frames])
        - np.angle(spectrum[:, frames])
        - phase_advance[:, None]
    )
    delta_phase = delta_phase - 2.0 * np.pi * np.round(delta_phase / (2.0 * np.pi))
    phase_acc = np.angle(spectrum[:, 0])[:, None] + np.cumsum(
        phase_advance[:, None] + delta_phase, axis=1
    )
    stretched = (magnitude * np.exp(1j * phase_acc)).astype(np.complex64)

    # Envelope correction keeps the spectral tilt natural after time-stretch.
    source_env = _spectral_envelope(np.abs(spectrum), n_fft)
    shifted_env = _spectral_envelope(np.abs(stretched), n_fft)
    correction = np.exp(
        np.mean(source_env, axis=1) - np.mean(shifted_env, axis=1)
    ).astype(np.float32)
    stretched = stretched * correction[:, None]

    _, stretched_audio = istft(
        stretched,
        fs=sr,
        window="hann",
        nperseg=n_fft,
        noverlap=n_fft - hop,
        boundary=True,
    )
    ratio = 2.0 ** (-float(semitones) / 12.0)
    target_len = int(round(len(stretched_audio) * ratio))
    shifted = resample(stretched_audio, target_len).astype(np.float32)
    if shifted.shape[0] >= len(x):
        return shifted[: len(x)]
    return np.pad(shifted, (0, len(x) - shifted.shape[0])).astype(np.float32)


def _spectral_envelope(magnitude, n_fft):
    lifter_cutoff = 24
    log_magnitude = np.log(np.maximum(magnitude, 1e-8))
    cepstrum = np.fft.irfft(log_magnitude, n=n_fft, axis=0)
    cepstrum[lifter_cutoff:] = 0.0
    envelope = np.fft.rfft(cepstrum, n=n_fft, axis=0).real
    return envelope.astype(np.float32)


class RealtimeVoiceChanger:
    def __init__(
        self,
        sample_rate=TARGET_SAMPLE_RATE,
        block=BLOCK_SIZE,
        hop=HOP_SIZE,
    ):
        self.sample_rate = sample_rate
        self.block = block
        self.hop = hop
        self.effects = AudioEffects()
        self._window = np.hanning(block).astype(np.float32)
        self._lock = threading.Lock()
        self._stream = None
        self._active = False
        self._preset = "bypass"
        self._pitch = 0.0
        self._formant = 1.0
        self._robot = False
        self._in_buf = np.zeros(block, dtype=np.float32)
        self._out_tail = np.zeros(hop, dtype=np.float32)

    @property
    def available(self):
        return HAS_SOUNDDEVICE

    def _process_block(self, mono):
        out = mono.astype(np.float32)
        if abs(self._pitch) > 1e-4:
            out = fast_pitch_shift(out, self.sample_rate, self._pitch)
        if abs(self._formant - 1.0) > 1e-4:
            out = self.effects._formant_shift(out[None, :], self._formant)[0]
        if self._robot:
            t = np.arange(len(out), dtype=np.float32) / self.sample_rate
            crushed = np.round(out * 6.0) / 6.0
            out = (0.45 * out + 0.55 * crushed * np.sin(2.0 * np.pi * 55.0 * t))
        return out.astype(np.float32)

    def _callback(self, indata, outdata, frames, time_info, status):
        mono_in = indata[:, 0] if indata.ndim > 1 and indata.shape[1] > 1 else indata[:, 0]
        mono_in = mono_in.astype(np.float32)

        self._in_buf = np.roll(self._in_buf, -len(mono_in))
        self._in_buf[-len(mono_in):] = mono_in

        processed = self._process_block(self._in_buf)
        windowed = processed * self._window
        out_mono = windowed[: self.hop] + self._out_tail
        self._out_tail = windowed[self.hop:].copy()

        out_mono = np.clip(out_mono, -1.0, 1.0)
        outdata[:] = out_mono[:, None]

    def start(self, preset="female", pitch_semitones=None, formant_ratio=None):
        if not HAS_SOUNDDEVICE:
            raise RuntimeError("sounddevice 未安装，请先运行 pip install sounddevice")
        with self._lock:
            if self._active:
                return self.status()
            conf = REALTIME_PRESETS.get(preset, REALTIME_PRESETS["female"])
            self._preset = preset
            self._pitch = float(
                conf["pitch_semitones"] if pitch_semitones is None else pitch_semitones
            )
            self._formant = float(
                conf["formant_ratio"] if formant_ratio is None else formant_ratio
            )
            self._robot = bool(conf.get("robot", False))
            self._in_buf = np.zeros(self.block, dtype=np.float32)
            self._out_tail = np.zeros(self.hop, dtype=np.float32)
            self._stream = sd.Stream(
                samplerate=self.sample_rate,
                blocksize=self.hop,
                channels=1,
                dtype="float32",
                callback=self._callback,
            )
            self._stream.start()
            self._active = True
            return self.status()

    def stop(self):
        with self._lock:
            if self._stream is not None:
                try:
                    self._stream.stop()
                    self._stream.close()
                except Exception:
                    pass
                self._stream = None
            self._active = False
            return self.status()

    def status(self):
        return {
            "available": HAS_SOUNDDEVICE,
            "active": self._active,
            "preset": self._preset,
            "pitch_semitones": self._pitch,
            "formant_ratio": self._formant,
            "presets": REALTIME_PRESETS,
        }
