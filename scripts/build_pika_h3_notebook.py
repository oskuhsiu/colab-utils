#!/usr/bin/env python3
"""Build a standalone Pika H3 Flex Colab notebook with embedded local tooling."""
import argparse
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BUNDLE_FILES = ("pika_h3.py", "pika_h3_lock.json")


def cell(kind, identity, source, tag=None):
    result = dict(cell_type=kind, id=identity, metadata={}, source=source.splitlines(keepends=True))
    if kind == "code":
        compile(source, identity, "exec")
        result.update(execution_count=None, outputs=[], metadata={"tags": [tag]})
    return result


def notebook(root=ROOT):
    sources = {name: (root / "scripts" / name).read_text() for name in BUNDLE_FILES}
    compile(sources["pika_h3.py"], "pika_h3.py", "exec")
    json.loads(sources["pika_h3_lock.json"])
    setup = '''# @title 1. 還原工具與離線計畫（不下載權重）
import json
import sys
from pathlib import Path
WORKSPACE_ROOT = "/content/pika-h3" # @param {type:"string"}
TOOLKIT_ROOT = "/content/pika-h3-toolkit" # @param {type:"string"}
''' + "PIKA_SOURCES = " + repr(sources) + '''
toolkit = Path(TOOLKIT_ROOT)
toolkit.mkdir(parents=True, exist_ok=True)
for filename, source in PIKA_SOURCES.items():
    (toolkit / filename).write_text(source)
if str(toolkit) not in sys.path:
    sys.path.insert(0, str(toolkit))
from pika_h3 import PikaWorkspace
workspace = PikaWorkspace(WORKSPACE_ROOT)
print(json.dumps(workspace.plan(), indent=2, ensure_ascii=False))
'''
    cells = [
        cell("markdown", "introduction", """# Pika H3 Flex · 官方六步影音生成

指定 `pika` 使用此入口；`omni` 使用 [ComfyUI notebook](ComfyUI_Colab.ipynb) 的 `h3-omni-int8`。工具已內嵌，不需 clone colab-utils。依固定版本安裝官方 `pika-h3-pro`，保留專用採樣流程。

**預設不安裝、不下載權重、不生成。** 先核對 GPU／host RAM／磁碟，再明確執行。官方以 H100 80GB 測試，此接入尚未做 GPU 實測。兩種 task 家族合計約 210 GB base＋5.5 GB adapters，另留依賴與暫存空間；只在生成時下載所選模式。CPU offload 不卸載 encoder／VAEs，也需要大量 host RAM。安裝使用 Python 3.12 隔離 venv，需要 NVIDIA runtime、git、patch、FFmpeg 與 C compiler，不配置付費資源。

原生 480p／768p、24fps、5–15 整數秒（實際依 17n+5 對齊）、32kHz stereo。4K 與分離 audio stems 是另外的 hosted API，未接入。[工具說明與限制](../skills/minimax-h3-colab/references/pika-h3-flex.md)。

## A. 設定與安裝
"""),
        cell("code", "pika-settings", setup, "setup"),
        cell("code", "pika-install", '''# @title 2. 明確開啟安裝（不下載模型權重）
INSTALL_PIKA = False # @param {type:"boolean"}
PYTHON_312 = "" # @param {type:"string"}
if INSTALL_PIKA:
    print(json.dumps(workspace.install(python=PYTHON_312 or None), indent=2, ensure_ascii=False))
else:
    print("INSTALL_PIKA=False；未安裝。安裝日誌：<root>/install.log。")
''', "setup"),
        cell("markdown", "generation-guide", """## B. 每支影片的設定與生成

素材放到本 runtime，填實際路徑。`t2va` 不帶素材；`i2va` 填首圖；`l2va` 填尾圖；`fl2va` 填首尾兩圖。`ref2va` 填有序 JSON，例如 `["image:/content/actor.png", "video:/content/motion.mp4", "audio:/content/voice.wav"]`，至少一張圖或一段影片，與首尾圖欄位互斥。Prompt 原文傳入官方工具。

先執行設定格看實際尺寸／模型幀數與命令。每次生成建立新 run，不自動重試或換模型；官方 CLI 每次重新載入 pipeline。可從 Files 追蹤 `runs/<id>/generation.log`／`receipt.json`，執行期間配合外部 runtime watcher。
"""),
        cell("code", "pika-job-settings", '''# @title 3. 工作設定與離線預覽
PIKA_JOB = None
TASK = "t2va" # @param ["t2va", "i2va", "l2va", "fl2va", "ref2va"]
PROMPT = "A small red toy train rolls steadily across a wooden table. Static wide camera, soft daylight. Sound: wheels rattle softly. Music: none." # @param {type:"string"}
RESOLUTION = "480p" # @param ["480p", "768p"]
ASPECT = "16:9" # @param ["21:9", "16:9", "3:2", "4:3", "5:4", "1:1", "4:5", "3:4", "2:3", "9:16", "9:21"]
DURATION = 5 # @param {type:"integer"}
SEED = 0 # @param {type:"integer"}
FIRST_IMAGE = "" # @param {type:"string"}
LAST_IMAGE = "" # @param {type:"string"}
REFERENCES_JSON = "[]" # @param {type:"string"}
CPU_OFFLOAD = False # @param {type:"boolean"}
_pika_job = dict(prompt=PROMPT, task=TASK, resolution=RESOLUTION, aspect=ASPECT,
                 duration=DURATION, seed=SEED, first_image=FIRST_IMAGE or None,
                 last_image=LAST_IMAGE or None, refs=json.loads(REFERENCES_JSON),
                 cpu_offload=CPU_OFFLOAD)
print(json.dumps(workspace.prepare(**_pika_job), indent=2, ensure_ascii=False))
PIKA_JOB = _pika_job
''', "clip"),
        cell("code", "pika-generate", '''# @title 4. 明確開啟生成（每次執行是新的 take）
RUN_GENERATION = False # @param {type:"boolean"}
if RUN_GENERATION:
    if globals().get("PIKA_JOB") is None:
        raise RuntimeError("請先成功執行第 3 格工作設定，再開啟生成。")
    PIKA_RESULT = workspace.generate(**PIKA_JOB)
    print(json.dumps(PIKA_RESULT, indent=2, ensure_ascii=False))
else:
    print("RUN_GENERATION=False；未下載權重或生成。")
''', "clip"),
        cell("markdown", "save-and-stop", """## 保存與釋放

保存整個 `<root>/runs/<id>/`：prompt、request、generation log、官方 `video.mp4`／`video.json` 與 receipt。`technically_valid` 只表示影音完整性與尺寸／幀數檢查通過；仍需播放、聽音訊與內容驗收。`/content` 會隨 runtime 刪除，請及時下載。斷線後先查原 run／PID／日誌再決定新的 take。

本工具沒有常駐 server，不管理付費 runtime。保存後另用 Colab 選單或既有管理工具停止／刪除 runtime 並核實釋放。
"""),
        cell("code", "pika-status", '''# @title 5. 讀取已記錄狀態（不重送生成）
print(json.dumps(workspace.status(), indent=2, ensure_ascii=False))
''', "status"),
    ]
    return dict(nbformat=4, nbformat_minor=5, cells=cells,
                metadata={"kernelspec": {"display_name": "Python 3", "language": "python", "name": "python3"},
                          "language_info": {"name": "python"}, "colab": {"name": "Pika_H3_Flex_Colab.ipynb"}})


def build(root=ROOT):
    path = root / "notebooks/Pika_H3_Flex_Colab.ipynb"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(notebook(root), ensure_ascii=False, indent=1) + "\n")
    return path


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=ROOT)
    args = parser.parse_args()
    print(build(args.root))
