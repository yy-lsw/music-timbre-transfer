#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Long-running Seed-VC worker.

The Flask backend starts this process once and keeps it alive so the heavy
PyTorch models (whisper, bigvgan, DiT) are loaded a single time instead of on
every conversion.  It serves a tiny local HTTP API:

    GET  /health    -> {"ready": true} once the models are loaded
    POST /convert   -> JSON body {source, target, output_dir, ...}

This file lives inside the project (not inside the Seed-VC checkout) and imports
Seed-VC's ``inference`` module from the ``third_party/Seed-VC`` directory at
runtime.  The conversion below is the same logic as Seed-VC's ``inference.main``,
extracted so it can run against preloaded models without re-importing them.
"""

import argparse
import json
import os
import sys
import threading
import traceback

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SEEDVC_HOME = os.environ.get(
    "SEEDVC_HOME", os.path.join(PROJECT_ROOT, "third_party", "Seed-VC")
)

sys.path.insert(0, SEEDVC_HOME)
os.environ.setdefault(
    "HF_HUB_CACHE", os.path.join(SEEDVC_HOME, "checkpoints", "hf_cache")
)
# Seed-VC resolves its cache/config paths relative to the current directory,
# so anchor the process there no matter how the worker was launched.
os.chdir(SEEDVC_HOME)

from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer  # noqa: E402

import librosa  # noqa: E402
import numpy as np  # noqa: E402
import time  # noqa: E402
import torch  # noqa: E402
import torchaudio  # noqa: E402

import inference as vc  # noqa: E402


@torch.no_grad()
def run_conversion(
    models,
    source_path,
    target_path,
    output_dir,
    diffusion_steps=25,
    length_adjust=1.0,
    inference_cfg_rate=0.7,
    f0_condition=False,
    auto_f0_adjust=False,
    semi_tone_shift=0,
):
    model, semantic_fn, f0_fn, vocoder_fn, campplus_model, mel_fn, mel_fn_args = models
    sr = mel_fn_args["sampling_rate"]
    pitch_shift = semi_tone_shift

    source = source_path
    target_name = target_path
    source_audio = librosa.load(source, sr=sr)[0]
    ref_audio = librosa.load(target_name, sr=sr)[0]

    sr = 22050 if not f0_condition else 44100
    hop_length = 256 if not f0_condition else 512
    max_context_window = sr // hop_length * 30
    overlap_frame_len = 16
    overlap_wave_len = overlap_frame_len * hop_length

    source_audio = torch.tensor(source_audio).unsqueeze(0).float().to(vc.device)
    ref_audio = torch.tensor(ref_audio[: sr * 25]).unsqueeze(0).float().to(vc.device)

    time_vc_start = time.time()
    converted_waves_16k = torchaudio.functional.resample(source_audio, sr, 16000)
    if converted_waves_16k.size(-1) <= 16000 * 30:
        S_alt = semantic_fn(converted_waves_16k)
    else:
        overlapping_time = 5
        S_alt_list = []
        buffer = None
        traversed_time = 0
        while traversed_time < converted_waves_16k.size(-1):
            if buffer is None:
                chunk = converted_waves_16k[:, traversed_time : traversed_time + 16000 * 30]
            else:
                chunk = torch.cat(
                    [
                        buffer,
                        converted_waves_16k[
                            :, traversed_time : traversed_time + 16000 * (30 - overlapping_time)
                        ],
                    ],
                    dim=-1,
                )
            S_alt = semantic_fn(chunk)
            if traversed_time == 0:
                S_alt_list.append(S_alt)
            else:
                S_alt_list.append(S_alt[:, 50 * overlapping_time :])
            buffer = chunk[:, -16000 * overlapping_time :]
            traversed_time += (
                30 * 16000 if traversed_time == 0 else chunk.size(-1) - 16000 * overlapping_time
            )
        S_alt = torch.cat(S_alt_list, dim=1)

    ori_waves_16k = torchaudio.functional.resample(ref_audio, sr, 16000)
    S_ori = semantic_fn(ori_waves_16k)

    mel = mel_fn(source_audio.to(vc.device).float())
    mel2 = mel_fn(ref_audio.to(vc.device).float())

    target_lengths = torch.LongTensor([int(mel.size(2) * length_adjust)]).to(mel.device)
    target2_lengths = torch.LongTensor([mel2.size(2)]).to(mel2.device)

    feat2 = torchaudio.compliance.kaldi.fbank(
        ori_waves_16k, num_mel_bins=80, dither=0, sample_frequency=16000
    )
    feat2 = feat2 - feat2.mean(dim=0, keepdim=True)
    style2 = campplus_model(feat2.unsqueeze(0))

    if f0_condition:
        F0_ori = f0_fn(ori_waves_16k[0], thred=0.03)
        F0_alt = f0_fn(converted_waves_16k[0], thred=0.03)
        F0_ori = torch.from_numpy(F0_ori).to(vc.device)[None]
        F0_alt = torch.from_numpy(F0_alt).to(vc.device)[None]
        voiced_F0_ori = F0_ori[F0_ori > 1]
        voiced_F0_alt = F0_alt[F0_alt > 1]
        log_f0_alt = torch.log(F0_alt + 1e-5)
        voiced_log_f0_ori = torch.log(voiced_F0_ori + 1e-5)
        voiced_log_f0_alt = torch.log(voiced_F0_alt + 1e-5)
        median_log_f0_ori = torch.median(voiced_log_f0_ori)
        median_log_f0_alt = torch.median(voiced_log_f0_alt)
        shifted_log_f0_alt = log_f0_alt.clone()
        if auto_f0_adjust:
            shifted_log_f0_alt[F0_alt > 1] = (
                log_f0_alt[F0_alt > 1] - median_log_f0_alt + median_log_f0_ori
            )
        shifted_f0_alt = torch.exp(shifted_log_f0_alt)
        if pitch_shift != 0:
            shifted_f0_alt[F0_alt > 1] = vc.adjust_f0_semitones(
                shifted_f0_alt[F0_alt > 1], pitch_shift
            )
    else:
        F0_ori = None
        F0_alt = None
        shifted_f0_alt = None

    cond, _, codes, commitment_loss, codebook_loss = model.length_regulator(
        S_alt, ylens=target_lengths, n_quantizers=3, f0=shifted_f0_alt
    )
    prompt_condition, _, codes, commitment_loss, codebook_loss = model.length_regulator(
        S_ori, ylens=target2_lengths, n_quantizers=3, f0=F0_ori
    )

    max_source_window = max_context_window - mel2.size(2)
    processed_frames = 0
    generated_wave_chunks = []
    while processed_frames < cond.size(1):
        chunk_cond = cond[:, processed_frames : processed_frames + max_source_window]
        is_last_chunk = processed_frames + max_source_window >= cond.size(1)
        cat_condition = torch.cat([prompt_condition, chunk_cond], dim=1)
        with torch.autocast(
            device_type=vc.device.type,
            dtype=torch.float16 if vc.fp16 else torch.float32,
        ):
            vc_target = model.cfm.inference(
                cat_condition,
                torch.LongTensor([cat_condition.size(1)]).to(mel2.device),
                mel2,
                style2,
                None,
                diffusion_steps,
                inference_cfg_rate=inference_cfg_rate,
            )
            vc_target = vc_target[:, :, mel2.size(-1) :]
        vc_wave = vocoder_fn(vc_target.float()).squeeze()
        vc_wave = vc_wave[None, :]
        if processed_frames == 0:
            if is_last_chunk:
                generated_wave_chunks.append(vc_wave[0].cpu().numpy())
                break
            generated_wave_chunks.append(vc_wave[0, :-overlap_wave_len].cpu().numpy())
            previous_chunk = vc_wave[0, -overlap_wave_len:]
            processed_frames += vc_target.size(2) - overlap_frame_len
        elif is_last_chunk:
            generated_wave_chunks.append(
                vc.crossfade(previous_chunk.cpu().numpy(), vc_wave[0].cpu().numpy(), overlap_wave_len)
            )
            processed_frames += vc_target.size(2) - overlap_frame_len
            break
        else:
            generated_wave_chunks.append(
                vc.crossfade(
                    previous_chunk.cpu().numpy(),
                    vc_wave[0, :-overlap_wave_len].cpu().numpy(),
                    overlap_wave_len,
                )
            )
            previous_chunk = vc_wave[0, -overlap_wave_len:]
            processed_frames += vc_target.size(2) - overlap_frame_len

    vc_wave = torch.tensor(np.concatenate(generated_wave_chunks))[None, :].float()
    time_vc_end = time.time()
    print(f"RTF: {(time_vc_end - time_vc_start) / vc_wave.size(-1) * sr}", flush=True)

    source_name = os.path.basename(source).split(".")[0]
    target_name = os.path.basename(target_name).split(".")[0]
    os.makedirs(output_dir, exist_ok=True)
    output_path = os.path.join(
        output_dir,
        f"vc_{source_name}_{target_name}_{length_adjust}_{diffusion_steps}_{inference_cfg_rate}.wav",
    )
    torchaudio.save(output_path, vc_wave.cpu(), sr)
    return output_path


class Worker:
    def __init__(self):
        self._models = None
        self._lock = threading.Lock()

    def load(self):
        args = argparse.Namespace(
            f0_condition=False,
            checkpoint=None,
            config=None,
            fp16=True,
        )
        self._models = vc.load_models(args)

    @property
    def ready(self):
        return self._models is not None

    def convert(self, payload):
        source = payload["source"]
        target = payload["target"]
        output_dir = payload["output_dir"]
        if not os.path.isfile(source):
            return {"error": "source not found: %s" % source}
        if not os.path.isfile(target):
            return {"error": "target not found: %s" % target}
        if bool(payload.get("f0_condition", False)):
            return {"error": "worker only supports f0_condition=False"}

        output_path = run_conversion(
            models=self._models,
            source_path=source,
            target_path=target,
            output_dir=output_dir,
            diffusion_steps=int(payload.get("diffusion_steps", 25)),
            length_adjust=float(payload.get("length_adjust", 1.0)),
            inference_cfg_rate=float(payload.get("inference_cfg_rate", 0.7)),
            f0_condition=False,
            auto_f0_adjust=bool(payload.get("auto_f0_adjust", False)),
            semi_tone_shift=int(payload.get("semi_tone_shift", 0)),
        )
        return {"output_path": output_path}


WORKER = Worker()


class Handler(BaseHTTPRequestHandler):
    def _json(self, code, obj):
        body = json.dumps(obj, ensure_ascii=False).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, fmt, *args):
        return

    def do_GET(self):
        if self.path.startswith("/health"):
            if WORKER.ready:
                self._json(200, {"ready": True})
            else:
                self._json(503, {"ready": False})
        else:
            self._json(404, {"error": "not found"})

    def do_POST(self):
        if not self.path.startswith("/convert"):
            self._json(404, {"error": "not found"})
            return
        try:
            length = int(self.headers.get("Content-Length", 0))
            payload = json.loads(self.rfile.read(length) or b"{}")
        except Exception:
            self._json(400, {"error": "bad json body"})
            return
        if not WORKER.ready:
            self._json(503, {"error": "models not loaded yet"})
            return
        with WORKER._lock:
            try:
                result = WORKER.convert(payload)
            except Exception:
                traceback.print_exc()
                self._json(500, {"error": traceback.format_exc()})
                return
        if "error" in result:
            self._json(400, result)
        else:
            self._json(200, result)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8765)
    args = parser.parse_args()

    print("loading Seed-VC models...", flush=True)
    try:
        WORKER.load()
    except Exception:
        traceback.print_exc()
        sys.exit(1)
    print("MODELS_READY", flush=True)

    server = ThreadingHTTPServer((args.host, args.port), Handler)
    server.daemon_threads = True
    print("worker listening on %s:%d" % (args.host, args.port), flush=True)
    server.serve_forever()


if __name__ == "__main__":
    main()
