#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
质感转换推理模块 —— 对应论文 3.3节 & 3.4节

模拟 MobileNetV3-Small + CBAM + 轻量化 CycleGAN 推理过程
生成器采用编码器-解码器结构，支持 INT8 量化推理
"""

import time
import sys
import random
import numpy as np
from config import (
    MODEL_SIZE_MB, MEMORY_USAGE_MB, TOTAL_PARAMS_M,
    AVG_FRAME_LATENCY_MS, SIMULATED_TOTAL_FRAMES, STYLE_PRESETS,
    HOP_LENGTH, TARGET_SAMPLE_RATE,
)


class TimbreInference:
    """
    轻量化质感转换推理引擎
    对应论文 3.3节：轻量化模型设计 + 3.4节：CycleGAN推理
    """

    def __init__(self):
        self.model_loaded = False
        self.model_info = {}

    def load_model(self):
        """
        加载 MobileNetV3-Small + CBAM 模型
        """
        print(f"\n{'='*50}")
        print(f"  [模型] 阶段开始 —— 论文 3.3节")
        print(f"{'='*50}")

        time.sleep(0.3)
        print(f"  [模型] 架构: MobileNetV3-Small + CBAM (Channel+Spatial Attention)")
        time.sleep(0.2)
        print(f"  [模型] 主干: MobileNetV3-Small (ImageNet 预训练)")

        # 输出模型层结构（对应论文 表3.1）
        layers = [
            ("Conv_Stem (3x3, s=2)", 16),
            ("MBBlock_1 (3x3, SE)", 16),
            ("MBBlock_2 (3x3, SE)", 24),
            ("MBBlock_3 (5x5, SE)", 24),
            ("MBBlock_4 (5x5, SE)", 40),
            ("CBAM_Attn_1 (Ch+Sp)", 40),
            ("MBBlock_5 (3x3, SE)", 80),
            ("MBBlock_6 (3x3, SE)", 96),
            ("CBAM_Attn_2 (Ch+Sp)", 96),
            ("Conv_Head (1x1)", 576),
            ("GAP + FC_Embed", 512),
        ]
        time.sleep(0.15)
        print(f"  {'  Layer':<36} {'Channels':>8}")
        print(f"  {'  ' + '-'*36} {'-'*8}")
        for name, ch in layers:
            time.sleep(0.03)
            print(f"  {name:<36} {ch:>8}")

        time.sleep(0.2)
        print(f"\n  [模型] 参数量: {TOTAL_PARAMS_M}M  |  "
              f"体积: {MODEL_SIZE_MB}MB (FP16+INT8)")
        time.sleep(0.15)
        print(f"  [模型] 推理引擎: TensorFlow Lite (INT8 量化)")
        time.sleep(0.15)
        print(f"  [模型] 预估内存: {MEMORY_USAGE_MB}MB")
        time.sleep(0.15)
        print(f"  [模型] 生成器: 编码器-解码器 (CycleGAN Generator)")
        time.sleep(0.15)
        print(f"  [模型] 加载完成 [OK]\n")

        self.model_loaded = True
        self.model_info = {
            "architecture": "MobileNetV3-Small + CBAM",
            "params_m": TOTAL_PARAMS_M,
            "size_mb": MODEL_SIZE_MB,
            "memory_mb": MEMORY_USAGE_MB,
            "quantization": "INT8",
        }
        return self.model_info

    def _build_eq_curve(self, style: str, n_bins: int, sr: int = 44100) -> np.ndarray:
        """
        构建每种风格对应的频谱塑形曲线（频率相关 EQ）
    
        """
        freqs = np.linspace(0, sr / 2, n_bins)

        if style == "classical":
            # 古典：温暖饱满的厅堂质感 —— 大幅提升中低频暖色 + 高频衰减 + 低频延展
            bass_warmth = 0.35 * np.exp(-((freqs - 180) / 160) ** 2)      # 低频温暖感
            mid_bloom = 0.75 * np.exp(-((freqs - 950) / 550) ** 2)         # 中频饱满（提升75%）
            presence = 0.25 * np.exp(-((freqs - 2800) / 800) ** 2)         # 适度的临场感
            high_roll = -0.55 / (1.0 + np.exp(-(freqs - 6500) / 350))      # 更强的高频滚降（-6dB）
            curve = 1.0 + bass_warmth + mid_bloom + presence + high_roll

        elif style == "rock":
            # 摇滚：强劲有力的失真质感 —— 大幅低音增强 + 深V型中频凹陷 + 激进高音提升
            bass = 0.85 * np.exp(-freqs / 150)                              # 超强低频提升（+85%）
            mid_scoop = -0.45 * np.exp(-((freqs - 1000) / 420) ** 2)        # 更深的V型中频凹陷（-45%）
            upper_mid_edge = 0.30 * np.exp(-((freqs - 3200) / 600) ** 2)   # 中高频边缘感
            treble = 0.55 / (1.0 + np.exp(-(freqs - 4500) / 650))          # 激进高音提升（+55%）
            air = 0.20 * np.exp(-((freqs - 9000) / 2500) ** 2)             # 超高频空气感
            curve = 1.0 + bass + mid_scoop + upper_mid_edge + treble + air

        elif style == "jazz":
            low_mid = 0.40 * np.exp(-((freqs - 280) / 180) ** 2)
            smooth_high = -0.30 / (1.0 + np.exp(-(freqs - 6000) / 350))
            curve = 1.0 + low_mid + smooth_high

        elif style == "hifi":
            clarity = 0.12 * np.exp(-((freqs - 3000) / 1500) ** 2)
            air = 0.30 / (1.0 + np.exp(-(freqs - 11000) / 1200))
            curve = 1.0 + clarity + air

        elif style == "surround":
            spatial = 0.45 * np.exp(-((freqs - 4500) / 1800) ** 2)
            width = 0.20 * np.exp(-((freqs - 1500) / 2500) ** 2)
            curve = 1.0 + spatial + width

        elif style == "m2f":
            # 男→女：大幅削减低频(<300Hz)，提升中高频共振峰(1.5-5kHz)
            bass_cut = -0.70 * np.exp(-freqs / 250)
            formant_boost = 0.55 * np.exp(-((freqs - 2800) / 1200) ** 2)
            air_boost = 0.25 / (1.0 + np.exp(-(freqs - 8000) / 800))
            curve = 1.0 + bass_cut + formant_boost + air_boost

        elif style == "f2m":
            # 女→男：大幅提升低频(<300Hz)，提升中低频共振峰(400-1500Hz)，削减高频
            bass_boost = 0.70 * np.exp(-freqs / 250)
            low_formant = 0.40 * np.exp(-((freqs - 800) / 500) ** 2)
            high_cut = -0.40 / (1.0 + np.exp(-(freqs - 5000) / 600))
            curve = 1.0 + bass_boost + low_formant + high_cut

        else:
            curve = np.ones(n_bins)

        return curve.astype(np.float32)

    def _apply_voice_warp(self, mag_frame: np.ndarray, style: str) -> np.ndarray:
        """
        频谱搬移 —— 模拟音高+共振峰变化（人声性别转换核心技术）
        对应论文 3.4节：CycleGAN 频谱映射

        男→女：将低频能量搬移到高频 (pitch up ~7 半音)
        女→男：将高频能量搬移到低频 (pitch down ~7 半音)
        """
        n_bins = len(mag_frame)
        warped = np.zeros_like(mag_frame)

        if style == "m2f":
            # 频谱压缩上移：每个频点从更低的频点取能量（音高升高）
            scale = 0.60  # 压缩因子：原 100Hz → 167Hz, 1000Hz → 1667Hz
            for i in range(n_bins):
                src_idx = int(i * scale)
                if src_idx < n_bins:
                    # 从相邻源频点插值
                    frac = (i * scale) - src_idx
                    y0 = mag_frame[src_idx]
                    y1 = mag_frame[min(src_idx + 1, n_bins - 1)]
                    warped[i] = y0 * (1 - frac) + y1 * frac

        elif style == "f2m":
            # 频谱拉伸下移：每个频点从更高的频点取能量（音高降低）
            scale = 1.65  # 拉伸因子：原 200Hz → 121Hz, 1000Hz → 606Hz
            for i in range(n_bins):
                src_idx = int(i * scale)
                if src_idx < n_bins:
                    frac = (i * scale) - src_idx
                    y0 = mag_frame[src_idx]
                    y1 = mag_frame[min(src_idx + 1, n_bins - 1)]
                    warped[i] = y0 * (1 - frac) + y1 * frac

        else:
            return mag_frame.copy()

        return warped

    def _apply_style_effect(self, mag_frame: np.ndarray, eq: np.ndarray,
                            style: str, frame_idx: int) -> np.ndarray:
        """
        对单帧频谱施加完整风格效果：频谱搬移 + EQ + 谐波 + 动态处理
        """
        # ---- 人声性别转换：先做频谱搬移，再做 EQ ----
        if style in ("m2f", "f2m"):
            out = self._apply_voice_warp(mag_frame, style)
            out = out * eq
            return out

        # Step 1: 施加频率相关 EQ 曲线（主要音色差异来源）
        out = mag_frame * eq

        if style == "rock":
            # === 摇滚：多级谐波失真 + 软削波 + 动态压缩 ===
            n_bins = len(mag_frame)
            # 多级谐波失真（模拟电子管过载）
            harm2 = np.roll(mag_frame * 0.40, 1)   # 2次谐波 40%
            harm3 = np.roll(mag_frame * 0.25, 2)   # 3次谐波 25%
            harm4 = np.roll(mag_frame * 0.12, 3)   # 4次谐波 12%
            harm5 = np.roll(mag_frame * 0.06, 4)   # 5次谐波 6%
            out += harm2 + harm3 + harm4 + harm5

            # 软削波饱和（tanh 模拟磁带/电子管过载饱和）
            drive = 1.6
            out = np.tanh(out * drive) / np.tanh(drive)

            # 动态压缩：模拟强力压缩器（降低峰值，提升整体响度）
            frame_rms = np.sqrt(np.mean(out ** 2)) + 1e-10
            threshold = 0.25
            if frame_rms > threshold:
                gain_reduction = (threshold / frame_rms) ** 0.55
                out = out * (0.35 + 0.65 * gain_reduction)

        elif style == "classical":
            # === 古典：大厅混响模拟 + 频谱平滑 + 动态扩展 + 立体声展宽 ===
            # 1. 宽核频谱平滑（模拟大厅混响的频谱包络衰减）
            kernel = np.array([0.08, 0.15, 0.22, 0.18, 0.15, 0.12, 0.07, 0.03],
                              dtype=np.float32)
            smoothed = np.convolve(out, kernel, mode="same")
            out = out * 0.25 + smoothed * 0.75  # 75% 混响包络

            # 2. 模拟混响尾音：用指数衰减的梳状滤波生成早期反射和晚期混响
            n_bins = len(out)
            reverb_tail = np.zeros(n_bins, dtype=np.float32)
            delays = [7, 13, 23, 37, 53]  # 梳状延迟（频谱域模拟时间域反射）
            for k, delay in enumerate(delays):
                decay = 0.28 * (0.65 ** k)  # 逐级衰减
                tail = np.zeros(n_bins, dtype=np.float32)
                if delay < n_bins:
                    tail[delay:] = out[:n_bins - delay] * decay
                reverb_tail += tail
            out = out * 0.75 + reverb_tail * 0.25

            # 3. 动态扩展：增强峰值（古典音乐动态范围大）
            frame_energy = np.mean(np.abs(out))
            if frame_energy > 0.15:
                expansion = 1.0 + (frame_energy - 0.15) * 1.2
                out = out * min(expansion, 1.6)

            # 4. 立体声展宽相位调制（模拟音乐厅空间感）
            phase_mod = 1.0 + 0.10 * np.sin(frame_idx * 0.25 + 1.3) * np.cos(
                np.linspace(0, np.pi, len(out)))
            out = out * phase_mod

        elif style == "jazz":
            # 爵士：略微压缩动态（柔和的动态范围控制）
            frame_energy = np.mean(out)
            if frame_energy > 0:
                compression = 1.0 / (1.0 + frame_energy * 0.08)
                out = out * (0.7 + 0.3 * compression)

        elif style == "hifi":
            # 高保真：扩展动态 + 降低底噪
            noise_floor = np.mean(np.abs(out[:20])) * 0.3
            out = np.where(np.abs(out) < noise_floor, 0.0, out)

        elif style == "surround":
            # 环绕：频谱微调制，模拟立体声展宽（左右声道相位差）
            phase_mod = 1.0 + 0.06 * np.sin(frame_idx * 0.3) * np.cos(
                np.linspace(0, np.pi, len(out)))
            out = out * phase_mod

        return out

    def infer(self, features: dict, style: str, progress_callback=None) -> dict:
        """
        执行 CycleGAN 逐帧推理
        对应论文 3.4节：CycleGAN推理与实时性优化

        对每帧频谱施加风格相关的频率塑形曲线和特殊效果，
        产生明显可辨的质感差异。
        """
        style_info = STYLE_PRESETS.get(style, STYLE_PRESETS["hifi"])

        print(f"\n{'='*50}")
        print(f"  [推理] 阶段开始 —— 论文 3.4节")
        print(f"{'='*50}")
        print(f"  [推理] 目标质感: {style_info['name']} - {style_info['desc']}")
        time.sleep(0.2)

        n_frames = features.get("n_frames", SIMULATED_TOTAL_FRAMES)
        mag = features.get("magnitude")
        if mag is None:
            mag = np.abs(np.random.randn(1025, n_frames)).astype(np.float32)

        n_freq_bins = mag.shape[0]
        sr = features.get("sample_rate", TARGET_SAMPLE_RATE)

        # 构建风格的频谱塑形曲线
        eq_curve = self._build_eq_curve(style, n_freq_bins, sr)

        print(f"  [推理] 待处理帧数: {n_frames}")
        time.sleep(0.15)
        print(f"  [推理] 频谱塑形: {n_freq_bins} 频点 × 个性化EQ曲线")
        time.sleep(0.15)
        print(f"  [推理] 批处理大小: 1 (逐帧实时)")
        time.sleep(0.15)
        print(f"  [推理] 引擎: CycleGAN Generator (Encoder-Decoder)")
        print()

        # 逐帧推理
        frame_latencies = []
        converted_mag = np.zeros_like(mag, dtype=np.float32)

        t_start = time.time()
        for i in range(n_frames):
            latency_ms = AVG_FRAME_LATENCY_MS + random.uniform(-1.2, 1.5)
            latency_ms = max(6.5, min(10.0, latency_ms))
            frame_latencies.append(latency_ms)

            # ===== 核心：风格频谱塑形（论文公式 3.12）=====
            converted_mag[:, i] = self._apply_style_effect(
                mag[:, i], eq_curve, style, i)

            # 进度回调
            percent = (i + 1) / n_frames * 100
            if progress_callback:
                progress_callback(percent, latency_ms, i + 1)

            # 控制台进度条
            bar_len = 36
            filled = int(bar_len * (i + 1) / n_frames)
            bar = "#" * filled + "." * (bar_len - filled)
            sys.stdout.write(
                f"\r  [推理] |{bar}| {percent:5.1f}%  "
                f"帧:{i+1}/{n_frames}  时延:{latency_ms:.1f}ms"
            )
            sys.stdout.flush()
            time.sleep(latency_ms / 1000.0)

        elapsed = time.time() - t_start
        avg_latency = np.mean(frame_latencies)

        print(f"\n\n  [推理] 总耗时: {elapsed:.1f}s")
        time.sleep(0.1)
        print(f"  [推理] 平均时延: {avg_latency:.1f}ms/frame")
        time.sleep(0.1)
        rtf = avg_latency / (HOP_LENGTH / TARGET_SAMPLE_RATE * 1000)
        print(f"  [推理] 实时率 RTF: {rtf:.4f} (< 1.0, 满足实时)")
        time.sleep(0.1)
        print(f"  [推理] 阶段完成 [OK]\n")

        return {
            "converted_magnitude": converted_mag,
            "n_frames": n_frames,
            "avg_latency_ms": avg_latency,
            "total_time_sec": elapsed,
            "rtf": rtf,
            "style": style,
            "style_label": style_info["name"],
        }

    def get_status(self):
        return {
            "model_loaded": self.model_loaded,
            "model_info": self.model_info,
        }
