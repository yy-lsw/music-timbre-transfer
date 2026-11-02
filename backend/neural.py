#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Zero-shot neural voice conversion via Seed-VC.

This module always imports successfully even when Seed-VC, PyTorch and the
pretrained weights are missing, so the DSP pipeline keeps working without it.

Resolution order for the Seed-VC checkout and interpreter:
    1. ``SEEDVC_HOME`` / ``SEEDVC_PYTHON`` environment variables.
    2. ``<project>/third_party/Seed-VC`` and
       ``<project>/third_party/seedvc-venv/Scripts/python.exe``.
    3. System ``python`` on PATH.

Run ``scripts/setup_seedvc.ps1`` on a machine with internet access to clone
the repository, create the virtualenv and install its dependencies.  Pretrained
weights are downloaded automatically by Seed-VC on the first inference run.
"""

import glob
import json
import os
import shutil
import subprocess
import sys
import time
import urllib.request


PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _default_seedvc_home():
    return os.path.join(PROJECT_ROOT, "third_party", "Seed-VC")


def _default_python():
    venv_python = os.path.join(
        PROJECT_ROOT, "third_party", "seedvc-venv", "Scripts", "python.exe"
    )
    if os.path.isfile(venv_python):
        return venv_python
    return shutil.which("python") or sys.executable


class NeuralVoiceConverter:
    """Shell wrapper around Seed-VC's ``inference.py``."""

    def __init__(self, seedvc_home=None, seedvc_python=None):
        self.seedvc_home = seedvc_home or os.getenv(
            "SEEDVC_HOME", _default_seedvc_home()
        )
        self.seedvc_python = seedvc_python or os.getenv(
            "SEEDVC_PYTHON", _default_python()
        )
        self.worker_proc = None
        self._worker_log = None
        self.worker_port = int(os.getenv("SEEDVC_WORKER_PORT", "8765"))

    @property
    def inference_script(self):
        return os.path.join(self.seedvc_home, "inference.py")

    @property
    def available(self):
        return os.path.isfile(self.inference_script) and os.path.isfile(
            self.seedvc_python
        )

    def weights_cached(self):
        """Return True when the main Seed-VC weights are already on disk."""
        ckpt = os.path.join(self.seedvc_home, "checkpoints")
        hf_cache = os.path.join(ckpt, "hf_cache")

        def has_weights(base, prefix):
            if not os.path.isdir(base):
                return False
            for name in os.listdir(base):
                if not name.startswith(prefix):
                    continue
                for root, _, files in os.walk(os.path.join(base, name)):
                    if any(
                        os.path.getsize(os.path.join(root, f)) > 5 * 1024 * 1024
                        for f in files
                    ):
                        return True
            return False

        return (
            has_weights(ckpt, "models--Plachta--Seed-VC")
            and has_weights(ckpt, "models--funasr--campplus")
            and has_weights(hf_cache, "models--openai--whisper-small")
            and has_weights(hf_cache, "models--nvidia--bigvgan")
        )

    def example_reference(self, name):
        """Return the path of a bundled Seed-VC example reference audio."""
        return os.path.join(
            self.seedvc_home, "examples", "reference", name
        )

    @property
    def worker_script(self):
        return os.path.join(PROJECT_ROOT, "backend", "seedvc_worker.py")

    def _worker_ready(self, timeout=1.5):
        url = "http://127.0.0.1:%d/health" % self.worker_port
        deadline = time.time() + timeout
        while time.time() < deadline:
            try:
                with urllib.request.urlopen(url, timeout=1.5) as resp:
                    if resp.status == 200:
                        return True
            except Exception:
                pass
            time.sleep(0.3)
        return False

    def _subprocess_env(self):
        """Environment for the worker / CLI subprocess.

        When the weights are already cached we run HuggingFace and transformers
        in offline mode, which skips the per-startup HEAD requests that
        otherwise add long delays (and retry storms) on slow networks.
        """
        env = os.environ.copy()
        if not env.get("HF_ENDPOINT"):
            env["HF_ENDPOINT"] = env.get(
                "SEEDVC_HF_ENDPOINT", "https://huggingface.co"
            )
        env.setdefault(
            "HF_HUB_CACHE",
            os.path.join(self.seedvc_home, "checkpoints", "hf_cache"),
        )
        if self.weights_cached():
            env["HF_HUB_OFFLINE"] = "1"
            env["TRANSFORMERS_OFFLINE"] = "1"
        return env

    def _start_worker(self):
        if not os.path.isfile(self.worker_script):
            raise RuntimeError("找不到 Seed-VC worker.py: " + self.worker_script)
        env = self._subprocess_env()
        log_path = os.path.join(self.seedvc_home, "worker.log")
        self._worker_log = open(log_path, "a", encoding="utf-8")
        self.worker_proc = subprocess.Popen(
            [self.seedvc_python, self.worker_script, "--port", str(self.worker_port)],
            cwd=self.seedvc_home,
            env=env,
            stdout=self._worker_log,
            stderr=subprocess.STDOUT,
        )

    def _ensure_worker(self, timeout=900):
        if self.worker_proc is not None and self.worker_proc.poll() is None:
            if self._worker_ready(1.5) or self._worker_ready(timeout):
                return
            self.worker_proc = None
        if self.worker_proc is None or self.worker_proc.poll() is not None:
            self._start_worker()
        if not self._worker_ready(timeout):
            self.worker_proc = None
            raise RuntimeError(
                "Seed-VC worker 启动超时，请查看 "
                + os.path.join(self.seedvc_home, "worker.log")
            )

    def _post_json(self, path, obj):
        url = "http://127.0.0.1:%d%s" % (self.worker_port, path)
        data = json.dumps(obj).encode("utf-8")
        req = urllib.request.Request(
            url, data=data, headers={"Content-Type": "application/json"}
        )
        with urllib.request.urlopen(req, timeout=1800) as resp:
            return json.loads(resp.read().decode("utf-8"))

    def shutdown(self):
        if self.worker_proc is not None and self.worker_proc.poll() is None:
            try:
                self.worker_proc.terminate()
                self.worker_proc.wait(timeout=10)
            except Exception:
                try:
                    self.worker_proc.kill()
                except Exception:
                    pass
        self.worker_proc = None
        if self._worker_log is not None:
            try:
                self._worker_log.close()
            except Exception:
                pass
            self._worker_log = None

    def worker_warm(self):
        """True when the worker is already running and has models loaded."""
        if self.worker_proc is None or self.worker_proc.poll() is not None:
            return False
        return self._worker_ready(0.5)

    def diagnose(self):
        findings = {
            "available": self.available,
            "seedvc_home": self.seedvc_home,
            "seedvc_python": self.seedvc_python,
            "repo_cloned": os.path.isfile(self.inference_script),
            "python_found": os.path.isfile(self.seedvc_python),
        }
        findings["deps_ready"] = False
        findings["deps_detail"] = ""
        if not findings["repo_cloned"]:
            findings["hint"] = (
                "请运行 scripts/setup_seedvc.ps1 克隆 Seed-VC 并安装依赖。"
            )
        elif not findings["python_found"]:
            findings["hint"] = (
                "Seed-VC 已克隆，但找不到虚拟环境解释器；请重新运行"
                " scripts/setup_seedvc.ps1。"
            )
        else:
            findings["deps_ready"], findings["deps_detail"] = (
                self._check_dependencies()
            )
            if findings["deps_ready"]:
                findings["hint"] = "就绪，首次推理会自动下载预训练权重。"
            else:
                findings["hint"] = (
                    "依赖未就绪：" + findings["deps_detail"]
                )
        return findings

    def _check_dependencies(self):
        if not os.path.isfile(self.seedvc_python):
            return False, "找不到 Seed-VC 的 Python 解释器"
        try:
            completed = subprocess.run(
                [
                    self.seedvc_python,
                    "-c",
                    "import torch, torchaudio, dac, transformers, munch, einops",
                ],
                capture_output=True,
                text=True,
                timeout=120,
            )
        except Exception as exc:
            return False, f"依赖检查失败: {exc}"
        if completed.returncode == 0:
            return True, ""
        return False, "缺少 PyTorch/torchaudio，请重新运行安装脚本"

    def convert(
        self,
        source_path,
        reference_path,
        output_dir,
        diffusion_steps=25,
        length_adjust=1.0,
        f0_condition=False,
        auto_f0_adjust=False,
        semi_tone_shift=0,
    ):
        if not self.available:
            raise RuntimeError(
                "Seed-VC 未就绪：" + self.diagnose()["hint"]
            )
        if not os.path.isfile(source_path):
            raise FileNotFoundError("找不到源音频: " + source_path)
        if not os.path.isfile(reference_path):
            raise FileNotFoundError("找不到参考音频: " + reference_path)
        os.makedirs(output_dir, exist_ok=True)

        try:
            self._ensure_worker()
        except Exception:
            return self._convert_subprocess(
                source_path,
                reference_path,
                output_dir,
                diffusion_steps,
                length_adjust,
                f0_condition,
                auto_f0_adjust,
                semi_tone_shift,
            )

        result = self._post_json(
            "/convert",
            {
                "source": source_path,
                "target": reference_path,
                "output_dir": output_dir,
                "diffusion_steps": diffusion_steps,
                "length_adjust": length_adjust,
                "f0_condition": f0_condition,
                "auto_f0_adjust": auto_f0_adjust,
                "semi_tone_shift": semi_tone_shift,
            },
        )
        if "error" in result:
            raise RuntimeError(result["error"])
        return result["output_path"]

    def _convert_subprocess(
        self,
        source_path,
        reference_path,
        output_dir,
        diffusion_steps,
        length_adjust,
        f0_condition,
        auto_f0_adjust,
        semi_tone_shift,
    ):
        command = [
            self.seedvc_python,
            self.inference_script,
            "--source",
            source_path,
            "--target",
            reference_path,
            "--output",
            output_dir,
            "--diffusion-steps",
            str(int(diffusion_steps)),
            "--length-adjust",
            str(float(length_adjust)),
            "--f0-condition",
            str(bool(f0_condition)),
            "--auto-f0-adjust",
            str(bool(auto_f0_adjust)),
            "--semi-tone-shift",
            str(int(semi_tone_shift)),
        ]

        env = self._subprocess_env()

        subprocess.run(
            command,
            check=True,
            cwd=self.seedvc_home,
            env=env,
            capture_output=True,
            text=True,
        )

        candidates = sorted(
            glob.glob(os.path.join(output_dir, "*.wav")),
            key=os.path.getmtime,
            reverse=True,
        )
        if not candidates:
            raise RuntimeError("Seed-VC 没有在输出目录生成 WAV 文件")
        return candidates[0]
