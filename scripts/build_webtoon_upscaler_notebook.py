#!/usr/bin/env python3
"""Build the standalone, low-memory 2x webtoon panel upscaler notebook."""

from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "notebooks" / "Qwen_Webtoon_2x_Upscaler_Colab.ipynb"

OVERVIEW = """# 被俘日記・網漫 panel 2× 放大器

這是獨立後製 notebook，只在小說／分鏡／768px 草稿圖通過審稿後執行；不載入 Qwen、也不改動任何原圖。預設用 CAIDAS 的 `swin2SR-classical-sr-x2-64`，直接做 2× 超解析，Apache-2.0。放大後影像依來源 panel 的實際尺寸裁回精確 2×，保留其原有長寬比。

VRAM 已在一格最大草稿尺寸 768×1152 上量測：T4（15 GiB）峰值 allocated 10.11 GiB、reserved 10.67 GiB，單格約 22.66 秒。CLI 使用 T4 標準記憶體，不選 high-RAM；模型僅 48.5 MB，逐格推論不會同時載入整章圖片到 GPU。輸入／輸出仍保存 seed 與來源 SHA-256。

開始前由本機 `scripts/qwen_comic_colab.py upscale <章節資料夾>` 封裝已審核的 panel，啟動一個暫時 T4，執行本 notebook，下載 2× PNG 並重建 `reader-upscaled.html`，完成後關閉該 T4。這個 upscaler 不需要也不會中斷 Qwen runtime。

此模型偏保守的通用超解析，不是生成式重繪器。官方 anime 專用候選 Real-ESRGAN anime 在 Colab Python 3.13 的 BasicSR 安裝檢查失敗；其 NCNN Vulkan binary 在目前 runtime 又沒有可用 Vulkan ICD。候選比較與證據記在 [OSS Scout 報告](../plan/qwen-image-acceleration-and-upscaler-oss-scout.md)。"""

RUNTIME_CELL = r'''import importlib.util, json, os, platform, subprocess, sys, uuid, zipfile
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path

ACTION = os.environ.get("QWEN_ACTION", "status")
PROJECT_ID = os.environ.get("QWEN_PROJECT_ID", "")
CHAPTER_ID = os.environ.get("QWEN_CHAPTER_ID", "")
JOB_ARCHIVE = Path(os.environ.get("QWEN_JOB_ARCHIVE", "/content/webtoon-upscale-job.zip"))
PROJECTS_DIR = Path("/content/webtoon-upscale-projects")
if ACTION not in {"upscale", "status"}:
    raise ValueError(f"Unsupported QWEN_ACTION: {ACTION}")

if ACTION == "upscale":
    import re
    if not re.fullmatch(r"[a-zA-Z0-9_-]+", PROJECT_ID) or not re.fullmatch(r"ch[0-9]+", CHAPTER_ID):
        raise ValueError("Project/chapter ids are invalid.")
    if not JOB_ARCHIVE.is_file():
        raise FileNotFoundError(f"Upload the panel bundle first: {JOB_ARCHIVE}")
    PROJECT_DIR = PROJECTS_DIR / PROJECT_ID / CHAPTER_ID
    PROJECT_DIR.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(JOB_ARCHIVE) as archive:
        base = PROJECT_DIR.resolve()
        for member in archive.infolist():
            target = (base / member.filename).resolve()
            if not target.is_relative_to(base):
                raise ValueError(f"Unsafe path in project bundle: {member.filename}")
        archive.extractall(PROJECT_DIR)
    project = json.loads((PROJECT_DIR / "project.json").read_text(encoding="utf-8"))
    if project.get("project_id") != PROJECT_ID or project.get("chapter_id") != CHAPTER_ID:
        raise ValueError("Uploaded project identity does not match the requested job ids.")
    tasks = json.loads((PROJECT_DIR / "webtoon_tasks.json").read_text(encoding="utf-8"))
    if tasks.get("schema") != "webtoon-tasks.v1":
        raise ValueError("This notebook accepts webtoon panel tasks only.")
    missing = [task["output_path"] for task in tasks["panels"] if not (PROJECT_DIR / task["output_path"]).is_file()]
    if missing:
        raise FileNotFoundError("Missing original draft panels:\n" + "\n".join(missing))
    if not __import__("torch").cuda.is_available():
        raise RuntimeError("A CUDA GPU is required. The CLI default is a standard-memory T4.")
    try:
        installed_transformers = version("transformers")
    except PackageNotFoundError:
        installed_transformers = "0"
    version_tuple = tuple(int(part) for part in installed_transformers.split(".")[:2] if part.isdigit())
    if version_tuple < (5, 17):
        subprocess.run(
            [sys.executable, "-m", "pip", "install", "--upgrade", "transformers>=5.17", "safetensors"],
            check=True,
        )

    worker_path = PROJECT_DIR / "scripts" / "qwen_image21_worker.py"
    spec = importlib.util.spec_from_file_location(f"webtoon_worker_{uuid.uuid4().hex}", worker_path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Cannot load upscaler worker: {worker_path}")
    worker = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(worker)
    UPSCALE_RUNTIME = globals().setdefault("UPSCALE_RUNTIME", {})
    manifest = worker.run_webtoon_upscale(
        PROJECT_DIR,
        runtime_cache=UPSCALE_RUNTIME,
        factor=2,
        qwen_model_instance_id=None,
        session_name=os.environ.get("QWEN_SESSION_NAME"),
    )
    if manifest["status"] != "complete":
        raise RuntimeError(f"Upscaling did not complete: {manifest['status']}")
    results_bundle = Path(f"/content/{PROJECT_ID}-{CHAPTER_ID}-results.zip")
    with zipfile.ZipFile(results_bundle, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=3) as bundle:
        for path in PROJECT_DIR.rglob("*"):
            if path.is_file():
                bundle.write(path, path.relative_to(PROJECT_DIR))
    print(f"UPSCALED_RESULTS_BUNDLE={results_bundle} bytes={results_bundle.stat().st_size}", flush=True)
    print(json.dumps({
        "status": manifest["status"],
        "upscaler": manifest["upscaler_model_id"],
        "gpu": manifest["runtime"]["gpu"],
        "gpu_memory_gib": manifest["runtime"]["gpu_memory_gib"],
        "panels": len(manifest["panels"]),
        "total_seconds": manifest["total_seconds"],
    }, ensure_ascii=False), flush=True)
elif ACTION == "status":
    import torch
    print(json.dumps({
        "action": ACTION,
        "cuda_available": torch.cuda.is_available(),
        "gpu": torch.cuda.get_device_name(0) if torch.cuda.is_available() else None,
        "python": platform.python_version(),
    }, ensure_ascii=False), flush=True)'''


def cell(cell_type: str, cell_id: str, source: str, tags: list[str] | None = None) -> dict:
    result = {
        "cell_type": cell_type,
        "id": cell_id,
        "metadata": {"tags": tags or []},
        "source": source.splitlines(keepends=True),
    }
    if cell_type == "code":
        result["execution_count"] = None
        result["outputs"] = []
    return result


def main() -> None:
    notebook = {
        "cells": [
            cell("markdown", "webtoon-upscaler-overview", OVERVIEW),
            cell("code", "webtoon-upscaler-job", RUNTIME_CELL, ["job"]),
        ],
        "metadata": {
            "colab": {"name": OUTPUT.name, "provenance": [], "accelerator": "GPU"},
            "kernelspec": {"display_name": "Python 3", "name": "python3"},
            "language_info": {"name": "python", "version": "3.13"},
        },
        "nbformat": 4,
        "nbformat_minor": 5,
    }
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(json.dumps(notebook, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print(f"Wrote {OUTPUT}")


if __name__ == "__main__":
    main()
