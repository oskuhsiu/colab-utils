#!/usr/bin/env python3
"""Build the standalone ComfyUI workspace notebook from current toolkit sources."""
import argparse
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BUNDLE_FILES = ("comfyui_workspace.py", "comfyui_workflows.py", "fast_h3_client.py", "comfyui_catalog.json")
BUNDLE_START = "# BEGIN EMBEDDED COMFYUI WORKSPACE TOOLKIT\n"
BUNDLE_END = "# END EMBEDDED COMFYUI WORKSPACE TOOLKIT\n"


def bundle_source(root=ROOT):
    sources = {name: (root / "scripts" / name).read_text() for name in BUNDLE_FILES}
    for name, source in sources.items():
        if name.endswith(".py"):
            compile(source, name, "exec")
        else:
            json.loads(source)
    return BUNDLE_START + "COMFYUI_SOURCES = " + repr(sources) + "\n" + BUNDLE_END


def markdown(cell_id, source):
    return {"cell_type": "markdown", "id": cell_id, "metadata": {},
            "source": source.splitlines(keepends=True)}


def code(cell_id, source, tag):
    compile(source, cell_id, "exec")
    return {"cell_type": "code", "id": cell_id, "metadata": {"tags": [tag]},
            "execution_count": None, "outputs": [], "source": source.splitlines(keepends=True)}


def notebook(bundle):
    settings = '''# @title 1. 設定與還原工具（不安裝、不下載模型）
import json
import sys
from pathlib import Path
WORKSPACE_ROOT = "/content/comfyui-workspace" # @param {type:"string"}
COMFYUI_PORT = 8190 # @param {type:"integer"}
TOOLKIT_ROOT = "/content/comfyui-workspace-toolkit" # @param {type:"string"}
ENABLE_CONTINUUM = True # @param {type:"boolean"}
ENABLE_REF2VA_VSA = True # @param {type:"boolean"}
MODEL_BUNDLE = "none" # @param ["none", "h3-continuum", "h3-ref2va-vsa", "h3-omni-int8"]
INSTALL_COMFYUI = True # @param {type:"boolean"}
START_COMFYUI = True # @param {type:"boolean"}
SHOW_COMFYUI = True # @param {type:"boolean"}
''' + bundle + '''
toolkit = Path(TOOLKIT_ROOT)
toolkit.mkdir(parents=True, exist_ok=True)
for filename, source in COMFYUI_SOURCES.items():
    destination = toolkit / filename
    if not destination.is_file() or destination.read_text() != source:
        destination.write_text(source)
if str(toolkit) not in sys.path:
    sys.path.insert(0, str(toolkit))
from comfyui_workspace import ComfyWorkspace
extensions = [name for name, enabled in (
    ("continuum", ENABLE_CONTINUUM), ("ref2va-vsa", ENABLE_REF2VA_VSA)) if enabled]
workspace = ComfyWorkspace(root=WORKSPACE_ROOT, port=COMFYUI_PORT, extensions=extensions)
print("Workspace:", workspace.root, "Port:", COMFYUI_PORT, "Extensions:", extensions)
'''
    return {
        "nbformat": 4, "nbformat_minor": 5,
        "metadata": {"kernelspec": {"display_name": "Python 3", "language": "python", "name": "python3"},
                     "language_info": {"name": "python"}, "colab": {"name": "ComfyUI_Colab.ipynb"}},
        "cells": [
            markdown("introduction", """# ComfyUI workspace · H3 Continuum / Ref2VA-VSA / FastH3 Omni

獨立的 ComfyUI 操作入口：內嵌工具，不需 clone 本專案。預設勾選安裝 Continuum 與 Ref2VA-VSA 擴充；A 區會安裝並啟動 server；模型預設不下載，B 區預設不生成。先跑 1–2 檢視版本與磁碟下載 GiB，再執行 3–5；要下載時明確選 MODEL_BUNDLE 並重跑設定、計畫與下載格。

這裡沒有 GPU 實測或效能保證。請自行選擇合適 Colab GPU；模型下載量不等於 VRAM。Ref2VA-VSA 是實驗性原生 Ref2VA，需專用 Ref2VA 模型、Turbo 與 gate，不沿用 FastH3 T2VA student。兩者是分開的 starter，沒有宣稱可組合。Veda 本次暫不實作，僅保留[研究](../research/comfy_h3_extensions_20261019.md)。

新增 `h3-omni-int8`：[FastVideo FastH3 Omni](https://huggingface.co/FastVideo/FastH3-Omni-Comfy) 的原生 Ref2VA INT8 模型，使用 8 步、guidance 1、shift 12/3，不疊 Turbo LoRA 或 VSA gate transplant。搭配含 vision tower 的 INT8 Qwen3-VL encoder、INT8 video VAE 與 FP32 audio VAE；不需要額外 custom node。模型 bundle 約 49.15 GiB，並非 VRAM 需求或容量保證。

使用獨立 root `/content/comfyui-workspace`、port `8190`，與 FastH3 的 root/8188 分開。安裝使用隔離 venv 並保留 Colab 現有 Torch/CUDA。模型受各自授權條款限制。詳細步驟見[操作說明](../doc/COMFYUI_WORKSPACE.md)。

## A. 預覽、安裝與開啟 UI
"""),
            code("workspace-settings", settings, "setup"),
            code("workspace-plan", '''# @title 2. 離線預覽版本與模型磁碟下載量（GiB；不是 VRAM）
WORKSPACE_PLAN = workspace.plan(bundle=MODEL_BUNDLE)
print(json.dumps(WORKSPACE_PLAN, indent=2, ensure_ascii=False, default=str))
''', "setup"),
            code("workspace-install", '''# @title 3. 安裝並準備 API starter（可關閉 INSTALL_COMFYUI）
if INSTALL_COMFYUI:
    print(json.dumps(workspace.install(), indent=2, ensure_ascii=False, default=str))
    print(json.dumps(workspace.stage_workflows(), indent=2, ensure_ascii=False, default=str))
else:
    print("略過安裝；先檢視第 2 格計畫，再將 INSTALL_COMFYUI 設為 True 並重跑設定。")
''', "setup"),
            code("workspace-models", '''# @title 4. 可選模型下載（先查看第 2 格 GiB）
if MODEL_BUNDLE != "none":
    print(json.dumps(workspace.download_models(bundle=MODEL_BUNDLE), indent=2, ensure_ascii=False, default=str))
else:
    print("略過模型下載；明確選擇 MODEL_BUNDLE 才下載。")
''', "setup"),
            code("workspace-start", '''# @title 5. 啟動 ComfyUI 與 Colab 原生 port iframe
if START_COMFYUI:
    print(json.dumps(workspace.start(timeout=180), indent=2, ensure_ascii=False, default=str))
    if SHOW_COMFYUI:
        try:
            from google.colab import output
        except ImportError:
            print(f"非 Colab 環境：請開啟 http://127.0.0.1:{COMFYUI_PORT}")
        else:
            output.serve_kernel_port_as_iframe(COMFYUI_PORT, height=900)
else:
    print("略過啟動；安裝完成後，將 START_COMFYUI 設為 True 並重跑設定。")
''', "setup"),
            markdown("api-introduction", """## B. 可選 API 執行（預設不生成）

可在 UI 建立工作流並匯出 **API 格式 JSON**，放入 `API_WORKFLOW_PATH`；或選擇下方 starter。安裝格會把 starter 放在 `<root>/workflows/`。API 執行是此工具驗證的接線方式；未驗證這些 API JSON 能直接拖入 UI 編輯器。

圖片先上傳至 `<root>/ComfyUI/input/`，`REFERENCE_IMAGE` 填相對檔名。Ref2VA 需使用原生 Ref2VA 的六欄提示與對應 reference 編號。Continuum starter 使用 Core attention，沒有上游範本額外 KJ、Spectrum、rgthree 依賴。Continuum starter 使用原生 20-step res_multistep，未加 Turbo；Ref2VA-VSA 使用對應 Ref2VA Turbo4 / Euler。非 Continuum 的原生 H3 影格需對齊 17n+5，因此輸入 5 秒可產生 124 幀（約 5.167 秒），不保證恰為 5 秒。PROMPT 留空會使用所選 preset 對應的提示範例；自填 Ref2VA 提示必須有六欄及 `<Picture 1>`。先下載所選 preset 的模型，再開啟 RUN_API。server 啟動後更換模型 bundle，需先停止 ComfyUI、下載，再啟動以更新 loader 清單。工作流或擴充改動後需重新確認相容性。

Omni starter 使用原生 Ref2VA、8-step Euler/simple 與 dense attention。`REF_IMAGE_SIZE` 適用 Ref2VA-VSA 與 Omni：`max` 保留最高 2048px 短邊的參考圖細節（不放大小圖）；`match` 按輸出像素面積縮小，較快省記憶體。表單預設 `max`，可能慢數倍、增加記憶體，不能保證身份一致；這不是 FL2VA + Ref2VA hybrid 權重。此 starter 接一張圖片；多圖／影片／音訊 references 可使用自訂 API graph。
"""),
            code("workspace-job-settings", '''# @title 6. 可選 API 工作設定
RUN_API = False # @param {type:"boolean"}
API_WORKFLOW_PATH = "" # @param {type:"string"}
PRESET = "h3-continuum" # @param ["h3-continuum", "h3-ref2va-vsa", "h3-omni-int8"]
PROMPT = "" # @param {type:"string"}
# Empty uses the selected preset task-matched example; Ref2VA custom text needs all six fields and <Picture 1>.
WIDTH = 864 # @param {type:"integer"}
HEIGHT = 480 # @param {type:"integer"}
DURATION_SECONDS = 5 # @param {type:"integer"}
SEED = 42 # @param {type:"integer"}
REFERENCE_IMAGE = "reference.png" # @param {type:"string"}
REF_IMAGE_SIZE = "max" # @param ["max", "match"]
CHUNKS = 2 # @param {type:"integer"}
RUN_NAME = "comfy_h3" # @param {type:"string"}
API_TIMEOUT = 1800 # @param {type:"integer"}
''', "clip"),
            code("workspace-run", '''# @title 7. 明確開啟 RUN_API 後送出 API 工作流
if RUN_API:
    workflow_path = Path(API_WORKFLOW_PATH) if API_WORKFLOW_PATH else workspace.root / "workflows" / "notebook_job.json"
    if not API_WORKFLOW_PATH:
        from comfyui_workflows import build_graph
        graph = build_graph(PRESET, prompt=PROMPT, width=WIDTH, height=HEIGHT,
                            duration_seconds=DURATION_SECONDS, seed=SEED,
                            reference_image=REFERENCE_IMAGE, chunks=CHUNKS, run_name=RUN_NAME,
                            ref_image_size=REF_IMAGE_SIZE)
        workflow_path.parent.mkdir(parents=True, exist_ok=True)
        workflow_path.write_text(json.dumps(graph, indent=2, ensure_ascii=False) + "\\n")
    API_RESULT = workspace.run_api(workflow_path, timeout=API_TIMEOUT)
    print(json.dumps(API_RESULT, indent=2, ensure_ascii=False, default=str))
else:
    print("RUN_API=False：未建立或執行生成工作。")
''', "clip"),
            markdown("save-outputs", """## 狀態、下載與關閉

結果通常在 `<root>/ComfyUI/output/`；API 回傳資訊會列出輸出。先播放影片、檢查音訊，再下載需要的檔案。在 Colab 左側 Files 選檔下載，或另開一格執行 `from google.colab import files; files.download('/content/comfyui-workspace/ComfyUI/output/你的檔名.mp4')`。

Continuum 的 Take/session 資料需與輸出一起保存；依所選 `run_storage` 確認實際路徑，離開前備份，不要只下載最終 MP4。`/content` 會隨 runtime 消失。下方只停止此工具管理的 ComfyUI 程序；**另從 Colab 選單停止／刪除 runtime 才能釋放配額**。
"""),
            code("workspace-status", '''# @title 8. 查看狀態（不啟動或下載）
print(json.dumps(workspace.status(), indent=2, ensure_ascii=False, default=str))
''', "status"),
            code("workspace-stop", '''# @title 9. 可選：只停止 ComfyUI 程序（不停止 Colab runtime）
STOP_COMFYUI = False # @param {type:"boolean"}
if STOP_COMFYUI:
    print(json.dumps(workspace.stop(), indent=2, ensure_ascii=False, default=str))
else:
    print("STOP_COMFYUI=False：保留 server。完成下載後請另行停止 Colab runtime。")
''', "stop"),
        ],
    }


def build(root=ROOT):
    path = root / "notebooks" / "ComfyUI_Colab.ipynb"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(notebook(bundle_source(root)), ensure_ascii=False, indent=1) + "\n")
    return path


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=ROOT)
    args = parser.parse_args()
    print(build(args.root))


if __name__ == "__main__":
    main()
