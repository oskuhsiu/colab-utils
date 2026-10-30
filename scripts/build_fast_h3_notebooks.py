#!/usr/bin/env python3
"""Embed the shared FastH3 toolkit into the legacy and dedicated Colab notebooks.

Run after changing any FastH3 module or lock file. Existing native H3 prompts,
references, helper functions, cell IDs, and setup/clip tags are retained.
"""
import argparse
import ast
import json
from pathlib import Path
import textwrap

ROOT = Path(__file__).resolve().parents[1]
BUNDLE_FILES = (
    "fast_h3_runtime.py", "fast_h3_workflow.py", "fast_h3_nodes.py",
    "fast_h3_client.py", "fast_h3_lock.json",
)
BUNDLE_START = "# BEGIN EMBEDDED FAST H3 TOOLKIT\n"
BUNDLE_END = "# END EMBEDDED FAST H3 TOOLKIT\n"
FAST_BACKEND = "FastH3 | ComfyUI L4 (T2VA)"
NATIVE_BACKEND = "DiffSynth | Original H3 (FL2VA / Ref2VA)"

FAST_HELPERS = '''
def using_fast_h3():
    if BACKEND not in ("FastH3 | ComfyUI L4 (T2VA)", "DiffSynth | Original H3 (FL2VA / Ref2VA)"):
        raise ValueError("請使用 BACKEND 選單中的引擎。")
    return BACKEND == "FastH3 | ComfyUI L4 (T2VA)"


def parse_fast_h3_loras():
    adapters = json.loads(FAST_H3_LORAS_JSON)
    if not isinstance(adapters, list) or not all(isinstance(item, dict) for item in adapters):
        raise ValueError("FAST_H3_LORAS_JSON 必須是 adapter 物件的 JSON 陣列。")
    return adapters


def parse_fast_h3_references():
    references = json.loads(FAST_H3_REFERENCES_JSON)
    if not isinstance(references, list) or not all(isinstance(item, str) for item in references):
        raise ValueError("FAST_H3_REFERENCES_JSON 必須是本機圖片路徑的 JSON 陣列。")
    return references


def get_fast_h3_runtime():
    # Literal sources make this notebook independent of a repository checkout.
    import sys
    toolkit = Path("/content/fast-h3-toolkit")
    toolkit.mkdir(parents=True, exist_ok=True)
    for filename, source in FAST_H3_SOURCES.items():
        destination = toolkit / filename
        if not destination.is_file() or destination.read_text() != source:
            destination.write_text(source)
    if str(toolkit) not in sys.path:
        sys.path.insert(0, str(toolkit))
    from fast_h3_runtime import FastH3Runtime
    global _FAST_H3_RUNTIME
    if globals().get("_FAST_H3_RUNTIME") is None:
        _FAST_H3_RUNTIME = FastH3Runtime(root="/content/fast-h3", port=8188)
    return _FAST_H3_RUNTIME

'''
FAST_LORAS_FORM = '''FAST_H3_LORAS_JSON = "[]" # @param {type:"string"}
# Optional compatible adapters only: [{"repo":"owner/repo","file":"adapter.safetensors","revision":"full_commit","strength":1.0}]
# Or an existing file: [{"path":"/content/adapter.safetensors","strength":1.0}]. Empty [] is the default; no speed LoRA is added.
'''
FAST_MODE_FORMS = '''FAST_H3_MODE = "t2va" # @param ["t2va", "experimental_ref2va_ood"]
FAST_H3_REFERENCES_JSON = "[]" # @param {type:"string"}
# Experimental Ref2VA accepts 1–3 /content image paths with the six-field reference prompt.
# This student was distilled for T2VA only; reference identity quality must be checked.
'''
FAST_CLIP_FORMS = '''# FastH3 inputs are independent of the native prompt and reference inputs below.
''' + FAST_MODE_FORMS + '''
FAST_H3_PROMPT = "integrated_multimodal_description: [Shot 1] A single red toy train moves steadily from left to right across a wooden tabletop, its wheels visibly turning. Static camera, soft daylight, clear continuous movement. overall_soundscape: Small wheels rattle and click softly against the wooden tabletop. non_diegetic_music: N/A." # @param {type:"string"}
FAST_H3_WIDTH = 864 # @param {type:"integer"}
FAST_H3_HEIGHT = 480 # @param {type:"integer"}
FAST_H3_DURATION_SECONDS = 5 # @param {type:"integer"}
FAST_H3_SEED = 123456662 # @param {type:"integer"}
FAST_H3_RUN_NAME = "fast_h3_notebook" # @param {type:"string"}
# FastH3 renders at 24 fps; use FAST_H3_REFERENCES_JSON for its experimental reference mode.
'''
FAST_GENERATE_HELPER = '''
def generate_fast_h3_clip():
    global OUTPUT_PATH, RUN_DIR, FAST_H3_RESULT
    runtime = get_fast_h3_runtime()
    adapters = parse_fast_h3_loras()
    runtime.ensure_ready(loras=adapters)
    FAST_H3_RESULT = runtime.generate(
        prompt=FAST_H3_PROMPT, width=FAST_H3_WIDTH, height=FAST_H3_HEIGHT,
        duration_seconds=FAST_H3_DURATION_SECONDS, seed=FAST_H3_SEED,
        loras=adapters, run_name=FAST_H3_RUN_NAME, timeout=1800,
        generation_mode=FAST_H3_MODE, reference_paths=parse_fast_h3_references())
    OUTPUT_PATH = Path(FAST_H3_RESULT["video_path"])
    RUN_DIR = Path(FAST_H3_RESULT["run_dir"])
    print(json.dumps(FAST_H3_RESULT, indent=2, ensure_ascii=False))
    from IPython.display import Video, display
    display(Video(str(OUTPUT_PATH), embed=True, width=720))
    return OUTPUT_PATH

'''


def bundle_source(root=ROOT):
    """Read the current files at build time; do not maintain duplicate module code."""
    sources = {name: (root / "scripts" / name).read_text() for name in BUNDLE_FILES}
    for name, source in sources.items():
        if name.endswith(".py"):
            compile(source, name, "exec")
        else:
            json.loads(source)
    return BUNDLE_START + "FAST_H3_SOURCES = " + repr(sources) + "\n" + BUNDLE_END


def replace_bundle(source, bundle):
    before, marker, rest = source.partition(BUNDLE_START)
    if not marker:
        raise ValueError("Notebook is missing its embedded-toolkit marker")
    _, marker, after = rest.partition(BUNDLE_END)
    if not marker:
        raise ValueError("Notebook is missing its embedded-toolkit end marker")
    return before + bundle + after


def guard_native(source):
    """Guard top-level work, retaining all native helper definitions at module scope.

    AST-based notebook contract tests execute these actual helpers independently.
    Imports inside the guarded spans remain completely absent on the Fast branch.
    """
    lines = source.splitlines(keepends=True)
    functions = [node for node in ast.parse(source).body if isinstance(node, ast.FunctionDef)]
    cursor, result = 0, []
    for function in functions:
        start, end = function.lineno - 1, function.end_lineno
        span = "".join(lines[cursor:start])
        if span.strip():
            result.append("if not using_fast_h3():\n" + textwrap.indent(span, "    "))
        result.append("".join(lines[start:end]) + "\n\n")
        cursor = end
    span = "".join(lines[cursor:])
    if span.strip():
        result.append("if not using_fast_h3():\n" + textwrap.indent(span, "    "))
    return "".join(result)


def set_source(cell, source):
    compile(source, cell["id"], "exec")
    cell["source"] = source.splitlines(keepends=True)


def extend_legacy(notebook, bundle):
    cells = {cell["id"]: cell for cell in notebook["cells"]}
    settings = "".join(cells["model-settings"]["source"])
    if BUNDLE_START in settings:
        settings = replace_bundle(settings, bundle)
        if "def parse_fast_h3_references(" not in settings:
            helper_start = FAST_HELPERS.index("def parse_fast_h3_references(")
            helper_end = FAST_HELPERS.index("def get_fast_h3_runtime(", helper_start)
            settings = settings.replace("DIFFSYNTH_COMMIT =", FAST_HELPERS[helper_start:helper_end] + "DIFFSYNTH_COMMIT =", 1)
        set_source(cells["model-settings"], settings)
        clip = "".join(cells["clip-settings"]["source"])
        if "FAST_H3_MODE =" not in clip:
            clip = clip.splitlines(keepends=True)[0] + FAST_MODE_FORMS + "".join(clip.splitlines(keepends=True)[1:])
        set_source(cells["clip-settings"], clip)
        generate = "".join(cells["generate-video"]["source"])
        old_function = next(node for node in ast.parse(generate).body
                            if isinstance(node, ast.FunctionDef) and node.name == "generate_fast_h3_clip")
        lines = generate.splitlines(keepends=True)
        generate = ("".join(lines[:old_function.lineno - 1]) + FAST_GENERATE_HELPER.lstrip("\n").rstrip() + "\n\n"
                    + "".join(lines[old_function.end_lineno:]).lstrip("\n"))
        set_source(cells["generate-video"], generate)
        repeat = "".join(cells["repeat-section"]["source"])
        repeat = repeat.replace("FastH3 僅支援 T2VA；", "FastH3 預設 T2VA；可選未蒸餾的 experimental_ref2va_ood 圖片參照，須驗人物效果。")
        cells["repeat-section"]["source"] = repeat.splitlines(keepends=True)
        return notebook
    lines = settings.splitlines(keepends=True)
    lines.insert(1, f"BACKEND = {FAST_BACKEND!r} # @param {json.dumps([FAST_BACKEND, NATIVE_BACKEND], ensure_ascii=False)}\n" + FAST_LORAS_FORM)
    settings = "".join(lines)
    settings = settings.replace("DIFFSYNTH_COMMIT =", bundle + FAST_HELPERS + "DIFFSYNTH_COMMIT =", 1)
    native_tail = 'SETUP_DIR.mkdir(parents=True, exist_ok=True)'
    before, marker, tail = settings.partition(native_tail)
    if not marker:
        raise ValueError("Native settings setup boundary changed")
    settings = before + "if using_fast_h3():\n    print(\"FastH3 T2VA：請選 L4 GPU、標準 RAM；原生 H3 設定保留但不套用。\")\nelse:\n" + textwrap.indent(marker + tail, "    ")
    set_source(cells["model-settings"], settings)
    branches = {
        "hardware-check": 'hardware = get_fast_h3_runtime().check_hardware()\nprint(json.dumps(hardware, indent=2))\n',
        "install-inference": 'FAST_H3_SETUP = get_fast_h3_runtime().setup(loras=parse_fast_h3_loras())\nprint(json.dumps(FAST_H3_SETUP, indent=2, ensure_ascii=False))\n',
        "download-models": 'print("FastH3 權重由上一格 setup 下載並快取；不執行原生 H3 下載。")\n',
        "load-model": 'get_fast_h3_runtime().ensure_ready(loras=parse_fast_h3_loras())\nprint(json.dumps(get_fast_h3_runtime().status(), indent=2, ensure_ascii=False))\n',
    }
    for cell_id, branch in branches.items():
        original = "".join(cells[cell_id]["source"])
        title, original = original.split("\n", 1)
        set_source(cells[cell_id], title + "\nif using_fast_h3():\n" + textwrap.indent(branch, "    ") + "\n" + guard_native(original))
    clip = "".join(cells["clip-settings"]["source"])
    set_source(cells["clip-settings"], clip.splitlines(keepends=True)[0] + FAST_CLIP_FORMS + "".join(clip.splitlines(keepends=True)[1:]))
    generate = "".join(cells["generate-video"]["source"])
    title, generate = generate.split("\n", 1)
    # Keep extension constants as literal module-level assignments for existing tests.
    for line in ('IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".webp"}\n', 'VIDEO_EXTENSIONS = {".mp4", ".mov"}\n'):
        generate = generate.replace(line, "", 1)
    guarded = guard_native(generate)
    set_source(cells["generate-video"], title + "\n" + 'IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".webp"}\nVIDEO_EXTENSIONS = {".mp4", ".mov"}\n' + FAST_GENERATE_HELPER + "if using_fast_h3():\n    generate_fast_h3_clip()\n\n" + guarded)
    intro = cells["introduction"]
    intro["source"] = ("# MiniMax-H3：FastH3 L4 或原版 DiffSynth\n\n"
        "預設 **FastH3 | ComfyUI L4 (T2VA)**，請手動選 Colab **L4 GPU、標準 RAM**。"
        "FastH3 使用獨立文字／音效提示，預設 5 秒、864×480、24 fps；不需要外部素材，"
        "不自動加入 Turbo 或其他 speed LoRA。`FAST_H3_LORAS_JSON` 可選填相容 adapter。"
        "A 區啟動一次本機 ComfyUI；B 區沿用 server 與磁碟快取，ComfyUI 依需求載入／offload，並不保證全部權重常駐 VRAM。\n\n"
        "選 **DiffSynth | Original H3 (FL2VA / Ref2VA)** 可使用下列既有原版功能。"
        "切換引擎請先重新啟動 runtime；更換 adapter 後重新執行 A 區。FastH3 不會執行原版安裝、下載或載入。\n\n" + "".join(intro["source"][2:])).splitlines(keepends=True)
    repeat = cells["repeat-section"]
    repeat["source"] = ("## B. 每片只執行這一區\n\n"
        "FastH3：修改 `FAST_H3_PROMPT`、尺寸、秒數、seed 與 run name，再執行 6–7。"
        "FastH3 預設 T2VA；experimental_ref2va_ood 用獨立照片與六欄提示，人物效果須驗。下方原生 prompt／references 保留給 DiffSynth 使用。"
        "每片會先確認本機 server 就緒，再送出共同 API graph。\n\n" + "".join(repeat["source"][2:])).splitlines(keepends=True)
    return notebook


def markdown(cell_id, source):
    return {"cell_type": "markdown", "id": cell_id, "metadata": {}, "source": source.splitlines(keepends=True)}


def code(cell_id, source, tag):
    compile(source, cell_id, "exec")
    return {"cell_type": "code", "id": cell_id, "metadata": {"tags": [tag]},
            "execution_count": None, "outputs": [], "source": source.splitlines(keepends=True)}


def dedicated_notebook(bundle):
    setup_settings = ('# @title 1. FastH3 L4 設定（新的 runtime 執行一次）\n'
        + f'BACKEND = {FAST_BACKEND!r}\n' + FAST_LORAS_FORM
        + 'import json\nfrom pathlib import Path\n' + bundle + FAST_HELPERS)
    return {
        "nbformat": 4, "nbformat_minor": 5,
        "metadata": {"kernelspec": {"display_name": "Python 3", "language": "python", "name": "python3"},
                     "language_info": {"name": "python"}, "colab": {"name": "FastH3_ComfyUI_L4.ipynb"}},
        "cells": [
            markdown("introduction", '# FastH3 · ComfyUI · Colab L4\n\n'
                '手動選擇 **L4 GPU、標準 RAM**。首次執行 A 區，之後每片只執行 B 區。'
                '預設文字生成有聲影片 (T2VA)，5 秒、864×480、24 fps；示範不需外部素材。'
                '可選 experimental_ref2va_ood 圖片參照；四步 student 未蒸餾此模式，須實際驗收人物效果。\n\n'
                '使用內嵌固定版本工具與共同 ComfyUI API graph。預設不加 LoRA；可在 JSON '
                '填相容 adapter 的固定 revision 或本地 path 與 strength，不會自動套用 Turbo。'
                'A 區沿用已啟動 server、安裝與磁碟快取；ComfyUI 依需要載入／offload，不保證全部權重常駐 VRAM。\n\n'
                '## A. 初始化一次\n'),
            code("fast-h3-settings", setup_settings, "setup"),
            code("fast-h3-hardware", '# @title 2. 確認 L4 與實際資源\n'
                 'hardware = get_fast_h3_runtime().check_hardware()\nprint(json.dumps(hardware, indent=2))\n', "setup"),
            code("fast-h3-setup", '# @title 3. 安裝、下載與啟動本機 ComfyUI\n'
                 'FAST_H3_SETUP = get_fast_h3_runtime().setup(loras=parse_fast_h3_loras())\n'
                 'print(json.dumps(FAST_H3_SETUP, indent=2, ensure_ascii=False))\n', "setup"),
            code("fast-h3-local-preview", '# @title 4. 可選：Colab 本機連接埠預覽\n'
                 'SHOW_LOCAL_COMFYUI = False # @param {type:"boolean"}\n'
                 'if SHOW_LOCAL_COMFYUI:\n'
                 '    from google.colab import output\n'
                 '    output.serve_kernel_port_as_iframe(8188, height=700)\n', "setup"),
            markdown("repeat-section", '## B. 每片只執行這一區\n\n'
                '改提示詞、尺寸、秒數與 seed，再產片。輸出資料夾與 metrics 由共用 runtime 記錄；'
                '檔案驗證通過後仍需觀看動作與聆聽音訊。\n'),
            code("fast-h3-clip-settings", '# @title 5. 本片內容\n' + FAST_CLIP_FORMS, "clip"),
            code("fast-h3-generate", '# @title 6. 沿用 server 產片、驗證與預覽\n'
                 'import json\nfrom pathlib import Path\n' + FAST_GENERATE_HELPER + 'generate_fast_h3_clip()\n', "clip"),
            markdown("save-and-stop", '下載 `OUTPUT_PATH` 與 `RUN_DIR` 中要保留的紀錄，再停止 Colab runtime。\n\n'
                '```python\nfrom google.colab import files\nfiles.download(str(OUTPUT_PATH))\n```\n'),
        ],
    }


def build(root=ROOT):
    bundle = bundle_source(root)
    legacy_path = root / "notebooks" / "MiniMax_H3_A100.ipynb"
    notebook = extend_legacy(json.loads(legacy_path.read_text()), bundle)
    legacy_path.write_text(json.dumps(notebook, ensure_ascii=False, indent=1) + "\n")
    dedicated_path = root / "notebooks" / "FastH3_ComfyUI_L4.ipynb"
    if dedicated_path.is_file():
        dedicated = json.loads(dedicated_path.read_text())
        settings = next(cell for cell in dedicated["cells"] if cell["id"] == "fast-h3-settings")
        set_source(settings, replace_bundle("".join(settings["source"]), bundle))
    else:
        dedicated = dedicated_notebook(bundle)
    dedicated_path.write_text(json.dumps(dedicated, ensure_ascii=False, indent=1) + "\n")
    return legacy_path, dedicated_path


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=ROOT)
    args = parser.parse_args()
    for path in build(args.root):
        print(path)


if __name__ == "__main__":
    main()
