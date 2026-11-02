#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Effect orchestration with measured, real timings."""

import time

from .config import STYLE_PRESETS, TARGET_SAMPLE_RATE
from .effects import AudioEffects


class TimbreInference:
    def __init__(self):
        self.effects = AudioEffects()

    def infer(self, audio, info, style, params=None, progress_callback=None):
        started = time.perf_counter()
        processed = self.effects.process(
            audio,
            style,
            params=params,
            progress_callback=progress_callback,
        )
        total_time_sec = time.perf_counter() - started
        source_duration_sec = info["duration_sec"]
        duration_sec = processed.shape[1] / TARGET_SAMPLE_RATE
        rtf = (
            total_time_sec / source_duration_sec
            if source_duration_sec > 0
            else 0.0
        )
        if progress_callback:
            progress_callback(100, "转换完成")

        return {
            "audio": processed,
            "sample_rate": TARGET_SAMPLE_RATE,
            "duration_sec": duration_sec,
            "source_duration_sec": source_duration_sec,
            "total_time_sec": total_time_sec,
            "rtf": rtf,
            "style": style,
            "style_label": STYLE_PRESETS[style]["name"],
        }
