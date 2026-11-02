#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Audio output normalization and file export."""

import numpy as np
import soundfile as sf

from .config import TARGET_SAMPLE_RATE


class AudioReconstructor:
    """Writes processed audio without regenerating lost phase."""

    def __init__(self):
        self.sample_rate = TARGET_SAMPLE_RATE

    @staticmethod
    def normalize_peak(audio, target_peak=0.95):
        peak = float(np.max(np.abs(audio)))
        if peak <= 0:
            return audio
        return (audio / peak * target_peak).astype(np.float32)

    def save_wav(self, audio, filepath):
        if audio.ndim == 1:
            audio = audio[np.newaxis, :]
        sf.write(
            filepath,
            audio.T,
            self.sample_rate,
            subtype="PCM_16",
        )
        return filepath
