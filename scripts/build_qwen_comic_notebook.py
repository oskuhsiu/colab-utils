#!/usr/bin/env python3
"""Build the persistent-kernel Colab notebook used by the comic pipeline."""

from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "notebooks" / "Qwen_Image_2_1_Comic_Colab.ipynb"

OVERVIEW = """# Qwen Image 2.1 — 被俘日記直式網漫流水線

本 notebook 在固定 Colab session/kernel 裡常駐一個 Qwen Image 2.1 pipeline instance。依序提交各章會沿用同一個 instance，不重新載入 Qwen。CLI 預設申請 A100 **標準系統記憶體**，不選 high-RAM。現行 Google Colab CLI 不支援 V100；輸入未知 GPU 名會默默映射到 A100，因此此流程會拒絕不支援的型號。

分鏡單位是單格 panel 與有語義的垂直留白，不是漫畫頁。預設 panel 寬度 768px；可以在下方控制項選 512–1536px。每格高度由 storyboard 的 peek/short/standard/tall/hero 構圖自動推算，並按手機視窗向下閱讀排列。所有字由 HTML reader 後製排版，避免 Qwen 把繁中畫錯。每一格使用固定且跨章不重複的 seed，manifest 會記錄 prompt、參照圖雜湊、seed、尺寸及模型 instance。

審稿時只產生小圖；核准後另用 [Webtoon 2× Upscaler notebook](Qwen_Webtoon_2x_Upscaler_Colab.ipynb) 與獨立 T4 工作階段放大，不重跑或替換 Qwen。`scripts/qwen_comic_colab.py` 會把小說、網漫 storyboard、參照和任務送到這個持續運作的 kernel，下載 panel 圖並組成手機直式 HTML reader。ComfyUI 操作不是必需步驟。Qwen Image 2.1 僅按非商業評估使用。"""

SIZE_CELL = r'''import os
import ipywidgets as widgets
from IPython.display import display

PANEL_WIDTH_OPTIONS = (512, 640, 768, 896, 1024, 1280, 1536)
PANEL_WIDTH_DEFAULT = int(os.environ.get("QWEN_PANEL_WIDTH", "768"))
if PANEL_WIDTH_DEFAULT not in PANEL_WIDTH_OPTIONS:
    raise ValueError(f"Choose panel width from {PANEL_WIDTH_OPTIONS}; got {PANEL_WIDTH_DEFAULT}.")
PANEL_WIDTH_SELECTOR = widgets.SelectionSlider(
    options=PANEL_WIDTH_OPTIONS,
    value=PANEL_WIDTH_DEFAULT,
    description="Panel 寬度",
    continuous_update=False,
    layout=widgets.Layout(width="480px"),
)
display(PANEL_WIDTH_SELECTOR)
print("目前 panel 寬度：", PANEL_WIDTH_SELECTOR.value, "px；高度由每格構圖比例推算。", flush=True)'''

RUNTIME_CELL = r'''import glob, json, os, platform, subprocess, sys, time, uuid, zipfile
from pathlib import Path

ACTION = os.environ.get("QWEN_ACTION", "status")
MODEL_ID = os.environ.get("QWEN_MODEL_ID", "Qwen/Qwen-Image-2.1")
SESSION_NAME = os.environ.get("QWEN_SESSION_NAME", "")
if ACTION not in {"start", "submit", "status"}:
    raise ValueError(f"Unsupported QWEN_ACTION: {ACTION}")

# This dictionary belongs to the persistent Colab Jupyter kernel. Notebook
# executions may redefine helpers, but must never replace a loaded pipeline.
QWEN_RUNTIME = globals().setdefault("QWEN_RUNTIME", {})
_QWEN_PIPELINE_LOADED_THIS_CALL = False
RUNTIME_DIR = Path("/content/qwen-image-2.1-runtime")
VENV_DIR = Path("/content/qwen-image-2.1-venv")
HF_HOME = Path("/content/qwen-image-2.1-cache")
RUNTIME_DIR.mkdir(parents=True, exist_ok=True)
HF_HOME.mkdir(parents=True, exist_ok=True)
os.environ["HF_HOME"] = str(HF_HOME)
os.environ["HF_HUB_DISABLE_TELEMETRY"] = "1"


def _run_logged(command, log_path):
    result = subprocess.run(
        command, text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT
    )
    Path(log_path).parent.mkdir(parents=True, exist_ok=True)
    Path(log_path).write_text(result.stdout, encoding="utf-8")
    if result.returncode:
        print("\n".join(result.stdout.splitlines()[-100:]), flush=True)
        raise subprocess.CalledProcessError(result.returncode, command)
    return result.stdout


def _ensure_venv():
    install_log = RUNTIME_DIR / "environment-install.log"
    venv_python = VENV_DIR / "bin" / "python"
    if not venv_python.exists():
        _run_logged(
            [sys.executable, "-m", "venv", "--system-site-packages", "--without-pip", str(VENV_DIR)],
            install_log,
        )
    pip_check = subprocess.run(
        [str(venv_python), "-m", "pip", "--version"],
        text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
    )
    if pip_check.returncode:
        _run_logged(
            [sys.executable, "-m", "venv", "--clear", "--system-site-packages", "--without-pip", str(VENV_DIR)],
            install_log,
        )
        venv_python = VENV_DIR / "bin" / "python"
        pip_check = subprocess.run(
            [str(venv_python), "-m", "pip", "--version"],
            text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
        )
    if pip_check.returncode:
        raise RuntimeError(f"pip is unavailable in the isolated venv: {pip_check.stdout}")

    import_check = subprocess.run(
        [str(venv_python), "-c", "from diffusers import QwenImage21Pipeline; import transformers; print(transformers.__version__)"],
        text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
    )
    if import_check.returncode:
        _run_logged(
            [str(venv_python), "-m", "pip", "install",
             "transformers>=5.17", "accelerate>=1.0", "safetensors>=0.4.5",
             "Pillow>=10", "huggingface_hub>=0.32", "torchao==0.17.0",
             "git+https://github.com/huggingface/diffusers.git"],
            install_log,
        )
    import_check = subprocess.run(
        [str(venv_python), "-c", "from diffusers import QwenImage21Pipeline; import torch, transformers, diffusers; print({'torch':torch.__version__,'transformers':transformers.__version__,'diffusers':diffusers.__version__,'cuda':torch.cuda.is_available()})"],
        text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
    )
    if import_check.returncode:
        install_log.write_text(
            install_log.read_text(encoding="utf-8") + "\n\nIMPORT CHECK FAILED\n" + import_check.stdout,
            encoding="utf-8",
        )
        raise RuntimeError(f"QwenImage21Pipeline import failed:\n{import_check.stdout}")
    site_packages = glob.glob(str(VENV_DIR / "lib" / "python*" / "site-packages"))
    if not site_packages:
        raise RuntimeError(f"No venv site-packages found under {VENV_DIR}")
    for path in reversed(site_packages):
        if path not in sys.path:
            sys.path.insert(0, path)
    versions = subprocess.run(
        [str(venv_python), "-m", "pip", "freeze"],
        text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, check=True,
    ).stdout
    (RUNTIME_DIR / "python-packages.txt").write_text(versions, encoding="utf-8")
    print("Qwen runtime environment:", import_check.stdout.strip(), flush=True)


if QWEN_RUNTIME.get("pipeline") is not None:
    if QWEN_RUNTIME.get("model_id") != MODEL_ID:
        raise RuntimeError(
            "This fixed Colab kernel already holds a different model. Stop/restart the session before changing QWEN_MODEL_ID."
        )
    print(
        f"MODEL_REUSED model={MODEL_ID} instance={QWEN_RUNTIME['instance_id']} session={SESSION_NAME or 'unknown'}",
        flush=True,
    )
elif ACTION in {"start", "submit"}:
    _ensure_venv()
    import torch
    from diffusers import QwenImage21Pipeline

    if not torch.cuda.is_available():
        raise RuntimeError("CUDA is unavailable; this Colab session must have a GPU runtime.")
    _model_started = time.perf_counter()
    _pipeline = QwenImage21Pipeline.from_pretrained(
        MODEL_ID, torch_dtype=torch.bfloat16, cache_dir=str(HF_HOME)
    )
    _pipeline.enable_model_cpu_offload()
    QWEN_RUNTIME.update({
        "pipeline": _pipeline,
        "model_id": MODEL_ID,
        "instance_id": str(uuid.uuid4()),
        "model_load_seconds": round(time.perf_counter() - _model_started, 2),
        "loaded_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "session_name": SESSION_NAME,
    })
    _QWEN_PIPELINE_LOADED_THIS_CALL = True
    print(
        f"MODEL_LOADED model={MODEL_ID} instance={QWEN_RUNTIME['instance_id']} "
        f"load_seconds={QWEN_RUNTIME['model_load_seconds']} session={SESSION_NAME or 'unknown'}",
        flush=True,
    )
_runtime_status = {
    "status": "ready" if QWEN_RUNTIME.get("pipeline") is not None else "not_loaded",
    "action": ACTION,
    "model_id": QWEN_RUNTIME.get("model_id", MODEL_ID),
    "model_instance_id": QWEN_RUNTIME.get("instance_id"),
    "model_load_seconds": QWEN_RUNTIME.get("model_load_seconds"),
    "loaded_utc": QWEN_RUNTIME.get("loaded_utc"),
    "session_name": SESSION_NAME or QWEN_RUNTIME.get("session_name"),
    "python": platform.python_version(),
}
(RUNTIME_DIR / "runtime-status.json").write_text(
    json.dumps(_runtime_status, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
)
print(json.dumps(_runtime_status, ensure_ascii=False), flush=True)'''

JOB_CELL = r'''if ACTION == "submit":
    import importlib.util, re

    PROJECT_ID = os.environ["QWEN_PROJECT_ID"]
    CHAPTER_ID = os.environ["QWEN_CHAPTER_ID"]
    if not re.fullmatch(r"[a-zA-Z0-9_-]+", PROJECT_ID) or not re.fullmatch(r"[a-zA-Z0-9_-]+", CHAPTER_ID):
        raise ValueError("Project and chapter IDs may contain only letters, digits, underscore, and hyphen.")
    PHASE = os.environ.get("QWEN_PHASE", "all")
    FORCE_PAGES = {item.strip() for item in os.environ.get("QWEN_FORCE_PAGES", "").split(",") if item.strip()}
    FORCE_PANELS = {item.strip() for item in os.environ.get("QWEN_FORCE_PANELS", "").split(",") if item.strip()}
    if "PANEL_WIDTH_SELECTOR" in globals():
        PANEL_WIDTH_PX = int(PANEL_WIDTH_SELECTOR.value)
    else:
        PANEL_WIDTH_PX = int(os.environ.get("QWEN_PANEL_WIDTH", "768"))
    JOB_ARCHIVE = Path(os.environ.get("QWEN_JOB_ARCHIVE", f"/content/{PROJECT_ID}-{CHAPTER_ID}-job.zip"))
    PROJECT_DIR = Path("/content/comic-projects") / PROJECT_ID / CHAPTER_ID
    if not JOB_ARCHIVE.is_file():
        raise FileNotFoundError(f"Upload the job archive first: {JOB_ARCHIVE}")
    PROJECT_DIR.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(JOB_ARCHIVE) as _archive:
        _base = PROJECT_DIR.resolve()
        for _member in _archive.infolist():
            _target = (_base / _member.filename).resolve()
            if not _target.is_relative_to(_base):
                raise ValueError(f"Unsafe path in project archive: {_member.filename}")
        _archive.extractall(PROJECT_DIR)

    _project = json.loads((PROJECT_DIR / "project.json").read_text(encoding="utf-8"))
    if _project["project_id"] != PROJECT_ID or _project["chapter_id"] != CHAPTER_ID:
        raise ValueError("Uploaded project identity does not match the requested job IDs.")
    IS_WEBTOON = (PROJECT_DIR / "webtoon_tasks.json").is_file()
    _worker_path = PROJECT_DIR / "scripts" / "qwen_image21_worker.py"
    _spec = importlib.util.spec_from_file_location(f"qwen_worker_{uuid.uuid4().hex}", _worker_path)
    if _spec is None or _spec.loader is None:
        raise RuntimeError(f"Cannot load page worker: {_worker_path}")
    _worker = importlib.util.module_from_spec(_spec)
    _spec.loader.exec_module(_worker)
    if IS_WEBTOON:
        _tasks = json.loads((PROJECT_DIR / "webtoon_tasks.json").read_text(encoding="utf-8"))
        if _tasks["generation"]["model_id"] != MODEL_ID:
            raise ValueError("This job requests a different model than the one configured in the fixed runtime.")
        _manifest = _worker.run_webtoon_project(
            QWEN_RUNTIME["pipeline"],
            PROJECT_DIR,
            phase=PHASE,
            force_panels=FORCE_PANELS,
            model_instance_id=QWEN_RUNTIME["instance_id"],
            model_load_seconds=QWEN_RUNTIME["model_load_seconds"],
            model_reused=not _QWEN_PIPELINE_LOADED_THIS_CALL,
            session_name=SESSION_NAME or QWEN_RUNTIME.get("session_name"),
            panel_width=PANEL_WIDTH_PX,
        )
    else:
        _tasks = json.loads((PROJECT_DIR / "page_tasks.json").read_text(encoding="utf-8"))
        if _tasks["generation"]["model_id"] != QWEN_RUNTIME["model_id"]:
            raise ValueError("This job requests a different model than the one loaded in the persistent runtime.")
        _manifest = _worker.run_project(
            QWEN_RUNTIME["pipeline"],
            PROJECT_DIR,
            phase=PHASE,
            force_pages=FORCE_PAGES,
            model_instance_id=QWEN_RUNTIME["instance_id"],
            model_load_seconds=QWEN_RUNTIME["model_load_seconds"],
            model_reused=not _QWEN_PIPELINE_LOADED_THIS_CALL,
            session_name=SESSION_NAME or QWEN_RUNTIME.get("session_name"),
        )
    RESULTS_BUNDLE = Path(f"/content/{PROJECT_ID}-{CHAPTER_ID}-results.zip")
    with zipfile.ZipFile(RESULTS_BUNDLE, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=3) as _bundle:
        for _path in PROJECT_DIR.rglob("*"):
            if _path.is_file():
                _bundle.write(_path, _path.relative_to(PROJECT_DIR))
    print(f"RESULTS_BUNDLE {RESULTS_BUNDLE} bytes={RESULTS_BUNDLE.stat().st_size}", flush=True)
    print(f"MODEL_INSTANCE_ID {QWEN_RUNTIME.get('instance_id')} MODEL_REUSED {not _QWEN_PIPELINE_LOADED_THIS_CALL}", flush=True)
elif ACTION == "status":
    print(json.dumps({
        "persistent_model_loaded": QWEN_RUNTIME.get("pipeline") is not None,
        "model_instance_id": QWEN_RUNTIME.get("instance_id"),
        "session_name": SESSION_NAME or QWEN_RUNTIME.get("session_name"),
    }, ensure_ascii=False), flush=True)
else:
    print("Persistent Qwen pipeline is ready; upload a job and submit a chapter when ready.", flush=True)'''


def _cell(cell_type: str, cell_id: str, source: str, tags: list[str] | None = None) -> dict:
    cell = {
        "cell_type": cell_type,
        "id": cell_id,
        "metadata": {"tags": tags or []},
        "source": source.splitlines(keepends=True),
    }
    if cell_type == "code":
        cell["execution_count"] = None
        cell["outputs"] = []
    return cell


def main() -> None:
    notebook = {
        "cells": [
            _cell("markdown", "qwen-comic-overview", OVERVIEW),
            _cell("code", "webtoon-panel-size-controls", SIZE_CELL, ["settings"]),
            _cell("code", "qwen-comic-persistent-runtime", RUNTIME_CELL, ["runtime"]),
            _cell("code", "qwen-comic-submit-or-status", JOB_CELL, ["job"]),
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
