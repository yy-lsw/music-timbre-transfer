#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Audio loading and validation for the DSP effect pipeline."""

import os

import numpy as np
import soundfile as sf
from scipy.signal import resample

from .config import MAX_DURATION_SEC, TARGET_SAMPLE_RATE


class AudioPreprocessor:
    """Loads and validates input audio in a channel-first layout."""

    def __init__(self):
        self.sample_rate = TARGET_SAMPLE_RATE

    def load_audio(self, filepath):
        if not os.path.isfile(filepath):
            raise FileNotFoundError(f"音频文件不存在: {filepath}")

        info = sf.info(filepath)
        audio, sample_rate = sf.read(
            filepath, dtype="float32", always_2d=True
        )
        audio = audio.T
        if sample_rate != self.sample_rate:
            target_len = int(
                round(audio.shape[1] * self.sample_rate / sample_rate)
            )
            audio = resample(audio, target_len, axis=1).astype(np.float32)

        duration_sec = audio.shape[1] / self.sample_rate
        if duration_sec <= 0:
            raise ValueError("音频为空")
        if duration_sec > MAX_DURATION_SEC:
            raise ValueError(
                f"音频过长: {duration_sec:.1f}s，上限为 {MAX_DURATION_SEC:.0f}s"
            )

        info = {
            "channels": audio.shape[0],
            "samples": audio.shape[1],
            "sample_rate": self.sample_rate,
            "original_sample_rate": sample_rate,
            "duration_sec": duration_sec,
            "max_amplitude": float(np.max(np.abs(audio))),
        }
        return audio.astype(np.float32), info
