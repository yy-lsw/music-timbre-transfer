#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Real DSP effects: phase vocoder, EQ, distortion, reverb, stereo width."""

import numpy as np
from scipy.signal import fftconvolve, istft, resample, stft

try:
    import parselmouth
    HAS_PARSELMOUTH = True
except Exception:
    HAS_PARSELMOUTH = False

from .config import (
    HOP_LENGTH,
    N_FFT,
    STYLE_PRESETS,
    TARGET_SAMPLE_RATE,
    WIN_LENGTH,
)


def _gauss(freqs, center, width):
    return np.exp(-(((freqs - center) / width) ** 2))


def _shelf(freqs, edge, gain, slope=400):
    return gain / (1.0 + np.exp(-(freqs - edge) / slope))


class AudioEffects:
    def __init__(self):
        self.sample_rate = TARGET_SAMPLE_RATE
        self.n_fft = N_FFT
        self.hop_length = HOP_LENGTH
        self.win_length = WIN_LENGTH

    def _freqs(self):
        return np.fft.rfftfreq(self.n_fft, 1.0 / self.sample_rate)

    def _eq_curve(self, style, freqs, intensity):
        scale = intensity - 1.0
        curve = np.ones_like(freqs, dtype=np.float32)

        if style == "classical":
            curve += 0.55 * _gauss(freqs, 160, 180) * intensity
            curve += 0.80 * _gauss(freqs, 900, 520) * intensity
            curve += 0.30 * _gauss(freqs, 2800, 800) * intensity
            curve += _shelf(freqs, 6000, -0.85 * intensity)
        elif style == "rock":
            curve += 0.95 * np.exp(-freqs / 180) * intensity
            curve -= 0.60 * _gauss(freqs, 1000, 420) * intensity
            curve += 0.45 * _gauss(freqs, 3200, 700) * intensity
            curve += _shelf(freqs, 4500, 0.85 * intensity)
        elif style == "jazz":
            curve += 0.60 * _gauss(freqs, 260, 180) * intensity
            curve += _shelf(freqs, 5200, -0.70 * intensity)
        elif style == "hifi":
            curve -= 0.25 * _gauss(freqs, 160, 180) * intensity
            curve += 0.28 * _gauss(freqs, 3000, 1500) * intensity
            curve += _shelf(freqs, 10500, 0.55 * intensity)
        elif style == "surround":
            curve += 0.35 * _gauss(freqs, 4500, 1800) * intensity
            curve += _shelf(freqs, 9000, 0.35 * intensity)
        elif style == "m2f":
            curve += _shelf(freqs, 300, -0.55 * intensity)
            curve += 0.25 * _gauss(freqs, 2800, 1400) * intensity
            curve += _shelf(freqs, 8000, 0.18 * intensity)
        elif style == "f2m":
            curve += _shelf(freqs, 300, 0.65 * intensity)
            curve += 0.30 * _gauss(freqs, 800, 500) * intensity
            curve += _shelf(freqs, 4800, -0.55 * intensity)

        curve += scale * 0.15 * _gauss(freqs, 2500, 1800)
        return np.clip(curve, 0.0, 4.0).astype(np.float32)

    def _stft(self, channel):
        _, _, spectrum = stft(
            channel,
            fs=self.sample_rate,
            window="hann",
            nperseg=self.n_fft,
            noverlap=self.n_fft - self.hop_length,
            boundary="zeros",
            padded=True,
        )
        return spectrum

    def _istft(self, spectrum, length):
        _, signal = istft(
            spectrum,
            fs=self.sample_rate,
            window="hann",
            nperseg=self.n_fft,
            noverlap=self.n_fft - self.hop_length,
            boundary=True,
        )
        if signal.shape[0] >= length:
            return signal[:length]
        return np.pad(signal, (0, length - signal.shape[0]))

    def _apply_eq(self, audio, style, intensity):
        freqs = self._freqs()
        curve = self._eq_curve(style, freqs, intensity)
        out = np.zeros_like(audio, dtype=np.float32)
        for channel in range(audio.shape[0]):
            spectrum = self._stft(audio[channel])
            out[channel] = self._istft(
                spectrum * curve[:, None], audio.shape[1]
            )
        return out

    def _phase_vocoder(self, spectrum, rate):
        n_freq = spectrum.shape[0]
        phase_advance = (
            2.0 * np.pi * self.hop_length * np.arange(n_freq) / self.n_fft
        )
        time_steps = np.arange(0, spectrum.shape[1], rate, dtype=float)
        stretched = np.zeros(
            (n_freq, len(time_steps)), dtype=np.complex64
        )
        phase_acc = np.angle(spectrum[:, 0]).astype(np.float32)

        for index, step in enumerate(time_steps):
            frame = int(step)
            next_frame = min(frame + 1, spectrum.shape[1] - 1)
            alpha = step - frame
            magnitude = (1.0 - alpha) * np.abs(
                spectrum[:, frame]
            ) + alpha * np.abs(spectrum[:, next_frame])
            delta_phase = (
                np.angle(spectrum[:, next_frame])
                - np.angle(spectrum[:, frame])
                - phase_advance
            )
            delta_phase = (
                delta_phase
                - 2.0 * np.pi * np.round(delta_phase / (2.0 * np.pi))
            )
            phase_acc = phase_acc + phase_advance + delta_phase
            stretched[:, index] = magnitude * np.exp(1j * phase_acc)

        return stretched

    def _spectral_envelope(self, magnitude):
        lifter_cutoff = 24
        log_magnitude = np.log(np.maximum(magnitude, 1e-8))
        cepstrum = np.fft.irfft(log_magnitude, n=self.n_fft, axis=0)
        cepstrum[lifter_cutoff:] = 0.0
        envelope = np.fft.rfft(cepstrum, n=self.n_fft, axis=0).real
        return envelope.astype(np.float32)

    def _pitch_shift(self, audio, semitones):
        channels = []
        for channel in audio:
            rate = 2.0 ** (float(semitones) / 12.0)
            spectrum = self._stft(channel)
            source_envelope = self._spectral_envelope(np.abs(spectrum))
            source_envelope_mean = np.mean(source_envelope, axis=1)
            stretched = self._phase_vocoder(spectrum, rate)
            shifted_envelope = self._spectral_envelope(np.abs(stretched))
            shifted_envelope_mean = np.mean(shifted_envelope, axis=1)
            envelope_correction = np.exp(
                source_envelope_mean - shifted_envelope_mean
            ).astype(np.float32)
            stretched = stretched * envelope_correction[:, None]
            stretched_audio = self._istft(
                stretched, stretched.shape[1] * self.hop_length + self.n_fft
            )
            ratio = 2.0 ** (-float(semitones) / 12.0)
            target_len = int(round(len(stretched_audio) * ratio))
            shifted = resample(stretched_audio, target_len).astype(np.float32)
            if shifted.shape[0] >= len(channel):
                shifted = shifted[: len(channel)]
            else:
                shifted = np.pad(shifted, (0, len(channel) - shifted.shape[0]))
            channels.append(shifted)
        return np.stack(channels).astype(np.float32)

    def _gender_shift(self, audio, style, semitones, formant_ratio=None):
        if formant_ratio is None:
            formant_ratio = 1.1 if style == "m2f" else 1.0 / 1.1
        pitch_median = 165.0 * (2.0 ** (float(semitones) / 12.0))
        channels = []
        for channel in audio:
            sound = parselmouth.Sound(
                channel, sampling_frequency=self.sample_rate
            )
            changed = sound.change_gender(
                formant_shift_ratio=formant_ratio,
                new_pitch_median=pitch_median,
                pitch_range_factor=1.0,
                duration_factor=1.0,
            )
            values = changed.values
            channels.append(
                values[0].astype(np.float32)
                if values.ndim > 1
                else values.astype(np.float32)
            )
        return np.stack(channels)

    def _formant_shift(self, audio, ratio):
        """Move spectral formants without changing the fundamental pitch."""
        if abs(float(ratio) - 1.0) < 1e-4:
            return audio
        n_freq = self.n_fft // 2 + 1
        bins = np.arange(n_freq, dtype=np.float32)
        query = np.clip(bins / float(ratio), 0.0, float(n_freq - 1))
        lo = np.clip(np.floor(query).astype(np.int64), 0, n_freq - 2)
        hi = np.clip(lo + 1, 0, n_freq - 1)
        frac = (query - lo)[:, None].astype(np.float32)

        channels = []
        for channel in audio:
            spectrum = self._stft(channel)
            magnitude = np.abs(spectrum)
            phase = np.angle(spectrum)
            log_envelope = self._spectral_envelope(magnitude)
            detail = magnitude / np.maximum(np.exp(log_envelope), 1e-8)
            warped = (
                log_envelope[lo, :] * (1.0 - frac)
                + log_envelope[hi, :] * frac
            )
            new_magnitude = np.exp(warped) * detail
            new_spectrum = new_magnitude.astype(np.complex64) * np.exp(
                1j * phase
            )
            channels.append(self._istft(new_spectrum, len(channel)))
        return np.stack(channels).astype(np.float32)

    def _distort(self, audio, drive):
        scale = max(1.0, float(drive))
        out = np.tanh(audio * scale) / np.tanh(scale)
        return (out * 0.9).astype(np.float32)

    @staticmethod
    def _compress(audio, threshold=0.25, ratio=3.0):
        out = np.zeros_like(audio)
        attack = 0.001
        release = 0.08
        for channel in range(audio.shape[0]):
            prev = 0.0
            envelope = np.empty(audio.shape[1], dtype=np.float32)
            for sample in range(audio.shape[1]):
                target = abs(audio[channel, sample])
                if target > prev:
                    prev += attack * (target - prev)
                else:
                    prev += release * (target - prev)
                envelope[sample] = prev

            gain = np.ones(audio.shape[1], dtype=np.float32)
            above = envelope > threshold
            gain[above] = (
                threshold + (envelope[above] - threshold) / ratio
            ) / envelope[above]
            out[channel] = audio[channel] * gain
        return out

    def _reverb(self, audio, wet):
        if wet <= 0:
            return audio
        tail_len = int(self.sample_rate * 1.1)
        decay = np.exp(-np.linspace(0, 5, tail_len))
        channels = []
        for channel in range(audio.shape[0]):
            rng = np.random.default_rng(100 + channel)
            impulse = rng.normal(0, 1, tail_len) * decay
            wet_signal = fftconvolve(audio[channel], impulse, mode="full")
            length = max(audio.shape[1], wet_signal.shape[0])
            dry = np.pad(
                audio[channel], (0, length - audio.shape[1])
            ).astype(np.float32)
            wet_signal = np.pad(
                wet_signal, (0, length - wet_signal.shape[0])
            ).astype(np.float32)
            mixed = (1.0 - wet) * dry + wet * wet_signal
            channels.append(mixed)
        return np.stack(channels).astype(np.float32)

    def _widen(self, audio, intensity):
        if audio.shape[0] < 2:
            delay = int(self.sample_rate * 0.012 * intensity)
            left = audio[0]
            right = np.zeros_like(left)
            if delay < left.shape[0]:
                right[delay:] = left[:-delay]
            return np.stack([left, right]).astype(np.float32)
        mid = (audio[0] + audio[1]) * 0.5
        side = (audio[0] - audio[1]) * 0.5
        width = 0.35 + 1.2 * intensity
        left = mid + width * side
        right = mid - width * side
        return np.stack([left, right]).astype(np.float32)

    def _gate(self, audio):
        floor = np.mean(np.abs(audio[:, :512])) * 0.35
        out = np.where(np.abs(audio) < floor, 0.0, audio)
        return out.astype(np.float32)

    def process(self, audio, style, params=None, progress_callback=None):
        params = params or {}
        preset = STYLE_PRESETS.get(style, STYLE_PRESETS["hifi"])
        intensity = float(params.get("intensity", 1.0))
        pitch_semitones = float(
            params.get("pitch_semitones", preset.get("pitch_semitones", 0))
        )

        if progress_callback:
            progress_callback(8, "正在处理音高...")

        if preset.get("kind") == "voice":
            if HAS_PARSELMOUTH:
                formant_target = float(preset.get("formant_ratio", 0.0))
                if abs(formant_target) < 1e-4:
                    formant_target = 1.1 if style == "m2f" else 1.0 / 1.1
                audio = self._gender_shift(
                    audio, style, pitch_semitones, formant_target
                )
            else:
                audio = self._pitch_shift(audio, pitch_semitones)
                formant_target = float(preset.get("formant_ratio", 0.0))
                if abs(formant_target - 1.0) > 1e-4:
                    pitch_ratio = 2.0 ** (pitch_semitones / 12.0)
                    formant_shift = formant_target / pitch_ratio
                    audio = self._formant_shift(audio, formant_shift)

        if progress_callback:
            progress_callback(30, "正在应用频响塑形...")
        audio = self._apply_eq(audio, style, intensity)

        if style == "rock":
            if progress_callback:
                progress_callback(55, "正在生成失真与压缩...")
            audio = self._distort(audio, preset.get("drive", 2.0) * intensity)
            audio = self._compress(audio, threshold=0.15, ratio=4.0)
        elif style == "hifi":
            if progress_callback:
                progress_callback(55, "正在清理底噪...")
            audio = self._gate(audio)

        reverb_wet = float(preset.get("reverb_wet", 0))
        if reverb_wet > 0:
            if progress_callback:
                progress_callback(72, "正在合成混响...")
            audio = self._reverb(audio, reverb_wet * intensity)

        if style == "surround":
            if progress_callback:
                progress_callback(86, "正在扩展声场...")
            audio = self._widen(audio, intensity)

        if progress_callback:
            progress_callback(96, "处理完成，正在保存...")
        return audio
