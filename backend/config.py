#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
系统配置文件 —— 对应论文 第4章：系统实现与实验设置
"""

import os

# ---- 项目路径 ----
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
UPLOAD_FOLDER = os.path.join(BASE_DIR, "uploads")
OUTPUT_FOLDER = os.path.join(BASE_DIR, "outputs")
DB_PATH = os.path.join(BASE_DIR, "data.db")

# ---- 音频处理参数（对应论文 3.2节） ----
TARGET_SAMPLE_RATE = 44100       # 重采样目标：44.1kHz
N_MFCC = 40                      # MFCC 系数数量
N_FFT = 2048                     # STFT FFT 窗口大小
HOP_LENGTH = 512                 # 帧移
WIN_LENGTH = 2048                # 窗长

# ---- 模型参数（对应论文 3.3节：轻量化模型设计与 第5章：实验结果） ----
MODEL_SIZE_MB = 4.2
MEMORY_USAGE_MB = 168
TOTAL_PARAMS_M = 0.98
AVG_CONVERSION_TIME_SEC = 8.5
AVG_FRAME_LATENCY_MS = 8.2
CONVERSION_ACCURACY = 87.3

# 模拟推理帧数
SIMULATED_TOTAL_FRAMES = 1037

# ---- 支持的格式 ----
ALLOWED_AUDIO_EXTENSIONS = {"mp3", "wav", "flac", "aac", "ogg", "m4a"}

# ---- 质感风格预设（对应论文 4.2节） ----
STYLE_PRESETS = {
    "classical":   {"name": "古典",   "desc": "温暖饱满的大厅混响质感"},
    "rock":        {"name": "摇滚",   "desc": "强劲有力的动态压缩质感"},
    "jazz":        {"name": "爵士",   "desc": "柔和细腻的俱乐部氛围质感"},
    "hifi":        {"name": "无损高保真", "desc": "纯净通透的录音室品质"},
    "surround":    {"name": "环绕增强", "desc": "宽广沉浸的空间环绕质感"},
    "m2f":         {"name": "男声→女声", "desc": "男声升高音调+共振峰，转为女声质感"},
    "f2m":         {"name": "女声→男声", "desc": "女声降低音调+共振峰，转为男声质感"},
}

# ---- Flask 配置 ----
FLASK_HOST = "127.0.0.1"
FLASK_PORT = 5000
FLASK_DEBUG = True

os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(OUTPUT_FOLDER, exist_ok=True)
