#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Flask API and single-page frontend for the DSP audio effects service."""

import atexit
import os
import re
import threading
import uuid
from collections import deque

import numpy as np
import soundfile as sf
from scipy.signal import resample
from flask import Flask, jsonify, make_response, request, send_file

from .config import (
    ALLOWED_AUDIO_EXTENSIONS,
    DEFAULT_STYLE,
    EFFECT_INTENSITY_MAX,
    EFFECT_INTENSITY_MIN,
    FLASK_DEBUG,
    FLASK_HOST,
    FLASK_PORT,
    MAX_CONCURRENT_TASKS,
    MAX_CONTENT_LENGTH,
    MAX_DURATION_SEC,
    OUTPUT_FOLDER,
    PITCH_SEMITONES_MAX,
    PITCH_SEMITONES_MIN,
    STYLE_PRESETS,
    TARGET_SAMPLE_RATE,
    UPLOAD_FOLDER,
)
from .database import add_history, get_history, get_upload, init_db, save_upload
from .inference import TimbreInference
from .neural import NeuralVoiceConverter
from .preprocessor import AudioPreprocessor
from .realtime import RealtimeVoiceChanger
from .reconstructor import AudioReconstructor

app = Flask(__name__)
app.config["MAX_CONTENT_LENGTH"] = MAX_CONTENT_LENGTH

preprocessor = AudioPreprocessor()
reconstructor = AudioReconstructor()
engine = TimbreInference()
neural_engine = NeuralVoiceConverter()
realtime_engine = RealtimeVoiceChanger()
atexit.register(neural_engine.shutdown)

_task_status = {}
_task_events = {}
_task_lock = threading.Lock()
_active_tasks = 0
_runtime_samples = deque(maxlen=100)

init_db()


class TaskCancelled(Exception):
    pass


def allowed_file(filename):
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_AUDIO_EXTENSIONS


def _safe_file_id(file_id):
    return bool(re.fullmatch(r"[0-9a-f]{32}\.[a-z0-9]{1,8}", file_id or ""))


def _safe_path(folder, filename):
    real_root = os.path.realpath(folder)
    real_path = os.path.realpath(os.path.join(folder, filename))
    return real_path.startswith(real_root + os.sep) and os.path.isfile(real_path)


def _set_status(task_id, **fields):
    with _task_lock:
        _task_status.setdefault(task_id, {}).update(fields)


@app.route("/api/health", methods=["GET"])
def health_check():
    return jsonify(
        {
            "status": "ok",
            "sample_rate": TARGET_SAMPLE_RATE,
            "max_duration_sec": MAX_DURATION_SEC,
            "max_file_mb": round(MAX_CONTENT_LENGTH / 1024 / 1024),
            "active_tasks": _active_tasks,
            "effects": [
                "phase-vocoder-pitch-shift",
                "stft-eq",
                "distortion",
                "compression",
                "convolution-reverb",
                "stereo-widening",
            ],
        }
    )


@app.route("/api/styles", methods=["GET"])
def get_styles():
    styles = [
        {
            "key": key,
            "name": info["name"],
            "description": info["desc"],
            "kind": info.get("kind", "timbre"),
            "pitch_semitones": info.get("pitch_semitones", 0),
        }
        for key, info in STYLE_PRESETS.items()
    ]
    return jsonify({"styles": styles})


@app.route("/api/upload", methods=["POST"])
def upload_audio():
    if "file" not in request.files:
        return jsonify({"error": "未选择文件"}), 400

    file = request.files["file"]
    if not file.filename or not allowed_file(file.filename):
        return jsonify(
            {
                "error": "不支持的格式，仅支持: "
                + ", ".join(sorted(ALLOWED_AUDIO_EXTENSIONS))
            }
        ), 400

    ext = file.filename.rsplit(".", 1)[1].lower()
    file_id = f"{uuid.uuid4().hex}.{ext}"
    save_path = os.path.join(UPLOAD_FOLDER, file_id)
    file.save(save_path)

    file_size_mb = os.path.getsize(save_path) / (1024 * 1024)
    try:
        duration_sec = sf.info(save_path).duration
    except Exception as exc:
        os.remove(save_path)
        return jsonify({"error": f"无法解析音频文件: {exc}"}), 400

    if duration_sec <= 0:
        os.remove(save_path)
        return jsonify({"error": "音频为空"}), 400
    if duration_sec > MAX_DURATION_SEC:
        os.remove(save_path)
        return jsonify(
            {"error": f"音频过长，上限为 {MAX_DURATION_SEC:.0f} 秒"}
        ), 400

    save_upload(file_id, file.filename, file_size_mb, duration_sec)
    return jsonify(
        {
            "file_id": file_id,
            "original_name": file.filename,
            "file_size_mb": round(file_size_mb, 2),
            "duration_sec": round(duration_sec, 2),
            "message": "上传成功",
        }
    )


@app.route("/api/convert", methods=["POST"])
def convert_audio():
    global _active_tasks
    data = request.get_json(silent=True) or request.form
    file_id = data.get("file_id")
    style = data.get("style", DEFAULT_STYLE)
    raw_params = data.get("params", {}) or {}

    if not _safe_file_id(file_id):
        return jsonify({"error": "无效的 file_id"}), 400
    if style not in STYLE_PRESETS:
        return jsonify({"error": f"无效风格，可选: {list(STYLE_PRESETS.keys())}"}), 400
    if not _safe_path(UPLOAD_FOLDER, file_id):
        return jsonify({"error": "文件不存在或已过期"}), 404

    try:
        intensity = float(raw_params.get("intensity", 1.0))
        pitch_semitones = float(
            raw_params.get(
                "pitch_semitones",
                STYLE_PRESETS[style].get("pitch_semitones", 0),
            )
        )
    except (TypeError, ValueError):
        return jsonify({"error": "参数格式错误"}), 400

    if not EFFECT_INTENSITY_MIN <= intensity <= EFFECT_INTENSITY_MAX:
        return jsonify({"error": "效果强度超出范围"}), 400
    if not PITCH_SEMITONES_MIN <= pitch_semitones <= PITCH_SEMITONES_MAX:
        return jsonify({"error": "音高偏移超出范围"}), 400

    with _task_lock:
        if _active_tasks >= MAX_CONCURRENT_TASKS:
            return jsonify({"error": "已有任务正在处理，请稍后再试"}), 429
        _active_tasks += 1

    task_id = uuid.uuid4().hex
    event = threading.Event()
    with _task_lock:
        _task_status[task_id] = {
            "status": "processing",
            "progress": 0,
            "message": "正在加载音频...",
        }
        _task_events[task_id] = event

    def run_conversion():
        nonlocal task_id
        try:
            audio, info = preprocessor.load_audio(
                os.path.join(UPLOAD_FOLDER, file_id)
            )
            if event.is_set():
                raise TaskCancelled()

            def on_progress(percent, message):
                if event.is_set():
                    raise TaskCancelled()
                _set_status(
                    task_id,
                    progress=round(float(percent), 1),
                    message=message,
                )

            result = engine.infer(
                audio,
                info,
                style,
                params={"intensity": intensity, "pitch_semitones": pitch_semitones},
                progress_callback=on_progress,
            )
            if event.is_set():
                raise TaskCancelled()

            output_name = f"{task_id}.wav"
            output_path = os.path.join(OUTPUT_FOLDER, output_name)
            processed = reconstructor.normalize_peak(result["audio"])
            reconstructor.save_wav(processed, output_path)

            upload_meta = get_upload(file_id)
            original_name = (
                upload_meta["original_filename"] if upload_meta else file_id
            )
            add_history(
                original_filename=original_name,
                output_filename=output_name,
                style=style,
                style_label=STYLE_PRESETS[style]["name"],
                file_size_mb=os.path.getsize(output_path) / (1024 * 1024),
                duration_sec=result["duration_sec"],
                conversion_time_sec=result["total_time_sec"],
                rtf=result["rtf"],
            )
            _runtime_samples.append(
                {
                    "duration_sec": result["source_duration_sec"],
                    "total_time_sec": result["total_time_sec"],
                    "rtf": result["rtf"],
                }
            )
            _set_status(
                task_id,
                status="completed",
                progress=100,
                message="转换完成",
                output_file=output_name,
                result={
                    "style": result["style_label"],
                    "duration_sec": round(result["duration_sec"], 2),
                    "total_time_sec": round(result["total_time_sec"], 2),
                    "rtf": round(result["rtf"], 4),
                },
            )
        except TaskCancelled:
            _set_status(
                task_id,
                status="cancelled",
                message="任务已取消",
            )
        except Exception as exc:
            _set_status(
                task_id,
                status="error",
                message=str(exc),
            )
        finally:
            global _active_tasks
            with _task_lock:
                _active_tasks -= 1

    threading.Thread(target=run_conversion, daemon=True).start()
    return jsonify(
        {
            "task_id": task_id,
            "status": "started",
            "message": "转换任务已启动",
        }
    )


REFERENCE_PRESETS = {
    "female": "azuma_0.wav",
    "male": "dingzhen_0.wav",
}


@app.route("/api/neural/status", methods=["GET"])
def neural_status():
    return jsonify(neural_engine.diagnose())


@app.route("/api/realtime/status", methods=["GET"])
def realtime_status():
    return jsonify(realtime_engine.status())


@app.route("/api/realtime/start", methods=["POST"])
def realtime_start():
    data = request.get_json(silent=True) or request.form
    preset = data.get("preset", "female")
    try:
        pitch = (
            float(data["pitch_semitones"])
            if data.get("pitch_semitones") not in (None, "")
            else None
        )
        formant = (
            float(data["formant_ratio"])
            if data.get("formant_ratio") not in (None, "")
            else None
        )
    except (TypeError, ValueError):
        return jsonify({"error": "参数格式错误"}), 400

    if not realtime_engine.available:
        return jsonify(
            {
                "error": (
                    "实时变声需要 sounddevice 库。请先运行 "
                    "pip install sounddevice 后重启后端。"
                )
            }
        ), 503

    try:
        status = realtime_engine.start(preset, pitch_semitones=pitch, formant_ratio=formant)
    except Exception as exc:
        return jsonify({"error": f"无法启动音频设备：{exc}"}), 500
    return jsonify(status)


@app.route("/api/realtime/stop", methods=["POST"])
def realtime_stop():
    return jsonify(realtime_engine.stop())


@app.route("/api/neural/convert", methods=["POST"])
def neural_convert_audio():
    global _active_tasks
    data = request.get_json(silent=True) or request.form
    file_id = data.get("file_id")
    reference_file_id = data.get("reference_file_id")
    reference_key = data.get("reference_key")

    if not _safe_file_id(file_id):
        return jsonify({"error": "无效的 file_id"}), 400
    if not _safe_path(UPLOAD_FOLDER, file_id):
        return jsonify({"error": "源文件不存在或已过期"}), 404
    if not neural_engine.available:
        return jsonify(
            {"error": "Seed-VC 未就绪：" + neural_engine.diagnose()["hint"]}
        ), 503

    if reference_file_id:
        if not _safe_file_id(reference_file_id):
            return jsonify({"error": "无效的 reference_file_id"}), 400
        if not _safe_path(UPLOAD_FOLDER, reference_file_id):
            return jsonify({"error": "参考音频不存在或已过期"}), 404
        reference_path = os.path.join(UPLOAD_FOLDER, reference_file_id)
    elif reference_key in REFERENCE_PRESETS:
        reference_path = neural_engine.example_reference(
            REFERENCE_PRESETS[reference_key]
        )
        if not os.path.isfile(reference_path):
            return jsonify(
                {
                    "error": (
                        "未找到内置示例参考音色，请确认 Seed-VC 仓库的"
                        " examples/reference 目录存在，或改为上传参考音频。"
                    )
                }
            ), 404
    else:
        return jsonify(
            {"error": "请上传参考音频，或指定内置参考音色 reference_key"}
        ), 400

    with _task_lock:
        if _active_tasks >= MAX_CONCURRENT_TASKS:
            return jsonify({"error": "已有任务正在处理，请稍后再试"}), 429
        _active_tasks += 1

    task_id = uuid.uuid4().hex
    event = threading.Event()
    with _task_lock:
        _task_status[task_id] = {
            "status": "processing",
            "progress": 0,
            "message": "正在初始化 Seed-VC...",
        }
        _task_events[task_id] = event

    def run_neural_conversion():
        nonlocal task_id
        try:
            if event.is_set():
                raise TaskCancelled()
            source_path = os.path.join(UPLOAD_FOLDER, file_id)
            raw_dir = os.path.join(OUTPUT_FOLDER, "neural", task_id)
            if not neural_engine.weights_cached():
                _set_status(
                    task_id,
                    progress=10,
                    message="Seed-VC 首次运行，正在下载权重（约1.8GB），请耐心等待...",
                )
            elif neural_engine.worker_warm():
                _set_status(
                    task_id,
                    progress=10,
                    message="Seed-VC 推理中，正在转换...",
                )
            else:
                _set_status(
                    task_id,
                    progress=10,
                    message="Seed-VC 正在加载模型（首次约1-2分钟），之后会快很多...",
                )
            if event.is_set():
                raise TaskCancelled()
            generated = neural_engine.convert(
                source_path, reference_path, raw_dir
            )
            _set_status(task_id, progress=82, message="正在整理结果...")
            audio, sample_rate = sf.read(
                generated, dtype="float32", always_2d=True
            )
            audio = audio.T
            if sample_rate != TARGET_SAMPLE_RATE:
                target_len = int(
                    round(audio.shape[1] * TARGET_SAMPLE_RATE / sample_rate)
                )
                audio = resample(audio, target_len, axis=1).astype(np.float32)
            processed = reconstructor.normalize_peak(audio)
            output_name = f"{task_id}.wav"
            output_path = os.path.join(OUTPUT_FOLDER, output_name)
            reconstructor.save_wav(processed, output_path)

            upload_meta = get_upload(file_id)
            original_name = (
                upload_meta["original_filename"] if upload_meta else file_id
            )
            add_history(
                original_filename=original_name,
                output_filename=output_name,
                style="neural",
                style_label="智能变声 (Seed-VC)",
                file_size_mb=os.path.getsize(output_path) / (1024 * 1024),
                duration_sec=processed.shape[1] / TARGET_SAMPLE_RATE,
                conversion_time_sec=0.0,
                rtf=0.0,
            )
            _set_status(
                task_id,
                status="completed",
                progress=100,
                message="转换完成",
                output_file=output_name,
                result={
                    "style": "智能变声 (Seed-VC)",
                    "duration_sec": round(
                        processed.shape[1] / TARGET_SAMPLE_RATE, 2
                    ),
                },
            )
        except TaskCancelled:
            _set_status(task_id, status="cancelled", message="任务已取消")
        except Exception as exc:
            _set_status(task_id, status="error", message=str(exc))
        finally:
            global _active_tasks
            with _task_lock:
                _active_tasks -= 1

    threading.Thread(target=run_neural_conversion, daemon=True).start()
    return jsonify(
        {
            "task_id": task_id,
            "status": "started",
            "message": "神经变声任务已启动",
        }
    )


@app.route("/api/status/<task_id>", methods=["GET"])
def task_status(task_id):
    with _task_lock:
        status = _task_status.get(task_id)
    if not status:
        return jsonify({"error": "任务不存在"}), 404
    return jsonify(status)


@app.route("/api/cancel/<task_id>", methods=["POST"])
def cancel_task(task_id):
    event = _task_events.get(task_id)
    if not event:
        return jsonify({"error": "任务不存在"}), 404
    event.set()
    return jsonify({"status": "cancelling"})


@app.route("/api/download/<filename>", methods=["GET"])
def download_file(filename):
    if not _safe_path(OUTPUT_FOLDER, filename):
        return jsonify({"error": "文件不存在"}), 404
    return send_file(
        os.path.join(OUTPUT_FOLDER, filename),
        as_attachment=True,
        download_name=filename,
    )


@app.route("/api/history", methods=["GET"])
def conversion_history():
    try:
        limit = int(request.args.get("limit", 20))
    except ValueError:
        limit = 20
    rows = get_history(limit=limit)
    return jsonify({"history": rows, "total": len(rows)})


@app.route("/api/report", methods=["GET"])
def performance_report():
    samples = list(_runtime_samples)
    if samples:
        avg_duration = np.mean([s["duration_sec"] for s in samples])
        avg_time = np.mean([s["total_time_sec"] for s in samples])
        avg_rtf = np.mean([s["rtf"] for s in samples])
        metrics = [
            {"name": "已处理任务", "value": str(len(samples)), "target": "本机实测"},
            {"name": "平均音频时长", "value": f"{avg_duration:.1f} 秒", "target": "-"},
            {"name": "平均处理耗时", "value": f"{avg_time:.2f} 秒", "target": "-"},
            {"name": "平均实时率 RTF", "value": f"{avg_rtf:.2f}", "target": "低于 1 表示快于实时"},
        ]
    else:
        metrics = [
            {"name": "已处理任务", "value": "0", "target": "完成一次转换后生成"},
        ]

    return jsonify(
        {
            "title": "本机运行统计",
            "metrics": metrics,
            "baseline_comparison": [],
            "conclusion": "以上指标来自本机实际运行统计，不包含模型训练或离线评估。",
        }
    )


@app.after_request
def add_cors_headers(response):
    response.headers["Access-Control-Allow-Origin"] = "*"
    response.headers["Access-Control-Allow-Headers"] = "Content-Type"
    response.headers["Access-Control-Allow-Methods"] = "GET, POST, OPTIONS"
    return response


@app.errorhandler(413)
def too_large(_error):
    return jsonify({"error": "文件超过 100MB 上限"}), 413


def main():
    print("=" * 52)
    print("  DSP Audio Effects API")
    print("=" * 52)
    print(f"  地址: http://{FLASK_HOST}:{FLASK_PORT}")
    app.run(
        host=FLASK_HOST,
        port=FLASK_PORT,
        debug=FLASK_DEBUG,
        threaded=True,
    )


if __name__ == "__main__":
    main()
