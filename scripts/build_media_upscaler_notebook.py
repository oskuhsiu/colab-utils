#!/usr/bin/env python3
"""Build a self-contained Colab image/video post-processing notebook."""

from __future__ import annotations

import argparse
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
BUNDLE_FILES = ("media_upscale.py", "media_upscale_models.json")
OUTPUT = ROOT / "notebooks/AI_Media_Upscaler_Colab.ipynb"

OVERVIEW = """# AI image and video enlarger

Post-process existing **FastH3, original H3, Wan, Qwen or uploaded media** using
Real-ESRGAN. The default is native **2×** (`RealESRGAN_x2plus`); the optional
4× anime model can produce either 4× or 2× with a final Lanczos downsample.

Select a T4 GPU for the notebook. Setup preserves the installed PyTorch stack,
loads only the small upscaler, and downloads only the selected weight with its
recorded SHA-256. The video path streams one frame at a time with tiled inference;
it keeps the source constant frame rate and audio. This is frame-wise super-resolution;
inspect the result in motion for flicker. See [the guide](../doc/AI_UPSCALER.md)
for validation scope and limitations.

Run **A once**, then edit and rerun **B** for each file. Upload through Colab's Files
panel or use an existing `/content/...` output. With B copied into an existing
generation notebook after A, an empty `INPUT_PATH` uses that notebook's `OUTPUT_PATH`.
The original file stays intact; each result receives a unique name and a JSON receipt.
Copy/download results before disconnecting the runtime. This notebook does not allocate
or release Colab sessions on your behalf.
"""

SETUP = '''# A — install the small inference dependency and restore the embedded toolkit
import importlib.util, json, shutil, subprocess, sys
from pathlib import Path

TOOLKIT = Path("/content/media-upscale-toolkit")
TOOLKIT.mkdir(parents=True, exist_ok=True)
for filename, source in AI_UPSCALER_SOURCES.items():
    path = TOOLKIT / filename
    if not path.is_file() or path.read_text(encoding="utf-8") != source:
        path.write_text(source, encoding="utf-8")

import torch
from importlib.metadata import version
torch_before = torch.__version__
torch_distribution_before = version("torch")
subprocess.run([sys.executable, "-m", "pip", "install", "spandrel==0.4.2", "Pillow>=10.0"], check=True)
if version("torch") != torch_distribution_before:
    raise RuntimeError("The PyTorch installation changed. Restart the runtime before continuing.")
import spandrel
if not shutil.which("ffmpeg") or not shutil.which("ffprobe"):
    raise RuntimeError("ffmpeg and ffprobe are required; use a standard Colab runtime.")
print(json.dumps({"torch": torch_before, "spandrel": version("spandrel"),
                  "gpu": torch.cuda.get_device_name(0) if torch.cuda.is_available() else None,
                  "toolkit": str(TOOLKIT)}, indent=2))
'''

JOB = '''# B — choose a generated file or an uploaded image/video
MEDIA_TYPE = "video" # @param ["image", "video"]
INPUT_PATH = "" # @param {type:"string"}
MODEL = "realesrgan-x2plus" # @param ["realesrgan-x2plus", "realesrgan-x4plus", "realesrgan-anime-x4"]
SCALE = 2 # @param [2, 4]
TILE = 192 # @param {type:"integer"}
TILE_PAD = 16 # @param {type:"integer"}
PRECISION = "auto" # @param ["auto", "fp32", "fp16"]
OUTPUT_DIR = "/content/ai-upscale-output" # @param {type:"string"}

from datetime import datetime, timezone
import uuid

source_value = INPUT_PATH.strip() or globals().get("OUTPUT_PATH")
if not source_value:
    raise ValueError("Set INPUT_PATH to an uploaded/generated file, or run generation to set OUTPUT_PATH.")
source = Path(source_value).resolve()
if not source.is_file():
    raise FileNotFoundError(source)
stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ") + "_" + uuid.uuid4().hex[:6]
suffix = ".mp4" if MEDIA_TYPE == "video" else ".png"
destination = Path(OUTPUT_DIR) / f"{source.stem}_{SCALE}x_{stamp}{suffix}"
subprocess.run([sys.executable, str(TOOLKIT / "media_upscale.py"), "download",
                "--model", MODEL, "--model-dir", "/content/ai-upscale-models"], check=True)
command = [sys.executable, str(TOOLKIT / "media_upscale.py"), MEDIA_TYPE,
           str(source), "--output", str(destination), "--model", MODEL,
           "--model-dir", "/content/ai-upscale-models", "--scale", str(SCALE),
           "--tile", str(TILE), "--tile-pad", str(TILE_PAD),
           "--device", "auto", "--precision", PRECISION]
subprocess.run(command, check=True)
receipt_path = Path(str(destination) + ".upscale.json")
receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
if receipt.get("status") != "complete":
    raise RuntimeError("Upscaling did not produce a complete receipt")
UPSCALED_OUTPUT_PATH = destination
print("UPSCALED_OUTPUT_PATH=", destination)
print("RECEIPT_PATH=", receipt_path)
from IPython.display import Image as DisplayImage, Video, display
display(Video(str(destination), embed=True, width=720) if MEDIA_TYPE == "video"
        else DisplayImage(filename=str(destination), width=720))
'''


def cell(kind: str, identity: str, source: str, tags: list[str] | None = None) -> dict:
    result = {"cell_type": kind, "id": identity, "metadata": {"tags": tags or []},
              "source": source.splitlines(keepends=True)}
    if kind == "code":
        compile(source, identity, "exec")
        result.update(execution_count=None, outputs=[])
    return result


def build(root: Path = ROOT) -> dict:
    sources = {name: (root / "scripts" / name).read_text(encoding="utf-8") for name in BUNDLE_FILES}
    compile(sources["media_upscale.py"], "media_upscale.py", "exec")
    json.loads(sources["media_upscale_models.json"])
    setup = "AI_UPSCALER_SOURCES = " + repr(sources) + "\n" + SETUP
    return {"cells": [cell("markdown", "ai-upscaler-overview", OVERVIEW),
                      cell("code", "ai-upscaler-setup", setup, ["setup"]),
                      cell("code", "ai-upscaler-job", JOB, ["upscale", "job"])],
            "metadata": {"colab": {"name": OUTPUT.name, "provenance": []}, "accelerator": "GPU",
                         "kernelspec": {"display_name": "Python 3", "name": "python3"},
                         "language_info": {"name": "python", "version": "3.13"}},
            "nbformat": 4, "nbformat_minor": 5}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=OUTPUT)
    args = parser.parse_args()
    notebook = build()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(notebook, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print(args.output)


if __name__ == "__main__":
    main()
