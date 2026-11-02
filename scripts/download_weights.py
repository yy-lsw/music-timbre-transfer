#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Pre-download Seed-VC pretrained weights with resume support.

Run this ONCE from the Seed-VC directory (or from the wrapper .ps1).  It uses
the same cache directory as Seed-VC's own ``hf_utils.load_custom_model_from_hf``
(``./checkpoints``), so after it finishes, inference.py will find the files in
cache and will NOT download them again.

If the network drops mid-download, simply re-run this script; huggingface_hub
resumes the partial file instead of starting over.
"""

import os
import sys

os.environ.setdefault("HF_ENDPOINT", "https://hf-mirror.com")

from huggingface_hub import hf_hub_download  # noqa: E402


FILES = [
    ("Plachta/Seed-VC", "DiT_seed_v2_uvit_whisper_small_wavenet_bigvgan_pruned.pth"),
    ("Plachta/Seed-VC", "config_dit_mel_seed_uvit_whisper_small_wavenet.yml"),
    ("funasr/campplus", "campplus_cn_common.bin"),
    ("FunAudioLLM/CosyVoice-300M", "hift.pt"),
]


def main(cache_dir):
    cache_dir = os.path.abspath(cache_dir)
    os.makedirs(cache_dir, exist_ok=True)
    for repo_id, filename in FILES:
        print(f"[downloading] {repo_id} :: {filename}", flush=True)
        path = hf_hub_download(
            repo_id=repo_id,
            filename=filename,
            cache_dir=cache_dir,
        )
        print(f"[ok] {path}", flush=True)
    print("All weights are cached. Neural voice conversion is ready.", flush=True)


if __name__ == "__main__":
    cache = sys.argv[1] if len(sys.argv) > 1 else "./checkpoints"
    main(cache)
