#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Runtime configuration for the DSP audio effects service."""

import os

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
UPLOAD_FOLDER = os.path.join(BASE_DIR, "uploads")
OUTPUT_FOLDER = os.path.join(BASE_DIR, "outputs")
DB_PATH = os.path.join(BASE_DIR, "data.db")

TARGET_SAMPLE_RATE = 44100
N_FFT = 2048
HOP_LENGTH = 512
WIN_LENGTH = 2048

MAX_CONTENT_LENGTH = 100 * 1024 * 1024
MAX_DURATION_SEC = 600.0
MAX_CONCURRENT_TASKS = 3

ALLOWED_AUDIO_EXTENSIONS = {"mp3", "wav", "flac", "ogg"}

STYLE_PRESETS = {
    "classical": {
        "name": "古典",
        "desc": "温暖饱满，带厅堂混响",
        "kind": "timbre",
        "reverb_wet": 0.46,
    },
    "rock": {
        "name": "摇滚",
        "desc": "强力失真与动态压缩",
        "kind": "timbre",
        "drive": 3.0,
    },
    "jazz": {
        "name": "爵士",
        "desc": "柔和低频与俱乐部混响",
        "kind": "timbre",
        "reverb_wet": 0.40,
    },
    "hifi": {
        "name": "无损高保真",
        "desc": "清晰透亮并抑制底噪",
        "kind": "timbre",
    },
    "surround": {
        "name": "环绕增强",
        "desc": "扩展声场宽度与空间感",
        "kind": "timbre",
        "reverb_wet": 0.30,
    },
    "m2f": {
        "name": "男声转女声",
        "desc": "整体音高上移并提亮",
        "kind": "voice",
        "pitch_semitones": 5.0,
        "formant_ratio": 1.18,
    },
    "f2m": {
        "name": "女声转男声",
        "desc": "整体音高下移并压低",
        "kind": "voice",
        "pitch_semitones": -5.0,
        "formant_ratio": 0.85,
    },
}

DEFAULT_STYLE = "hifi"
PITCH_SEMITONES_MIN = -12.0
PITCH_SEMITONES_MAX = 12.0
EFFECT_INTENSITY_MIN = 0.5
EFFECT_INTENSITY_MAX = 1.5

FLASK_HOST = "127.0.0.1"
FLASK_PORT = 5000
FLASK_DEBUG = os.getenv("FLASK_DEBUG", "0") == "1"

os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(OUTPUT_FOLDER, exist_ok=True)
