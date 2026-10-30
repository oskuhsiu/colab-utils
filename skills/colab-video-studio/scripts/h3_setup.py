"""Pinned H3 setup exported from this repository notebook; no project/story defaults.
Called by backends.py with H3_TASK_MODE, H3_PRESET, H3_PRECISION.
Ref Turbo8 uses publisher video/audio shifts12/3, unlike FL6/3.
"""

# Source notebook cell: model-settings
# @title 1. 任務、模型與量化選單（選好後，後續產片不用重跑）
TASK_MODE = {"fl2va": "FL2VA | 文字／首尾幀（Turbo）", "ref2va": "Ref2VA | 多張圖片／多段影片參考"}[H3_TASK_MODE]
MODEL_PRESET = ({"original50": "Original 50-step | 原版品質對照", "turbo8": "Ref2VA Turbo 8-step v1.0 768p | 多圖參考快速產片"} if H3_TASK_MODE == "ref2va" else {"original50": "Original 50-step | 原版品質對照", "turbo8": "Turbo 8-step v1.0 768p | 品質與速度平衡", "turbo4": "Turbo 4-step v1.2 768p | 快速預覽、音訊更新"})[H3_PRESET]
WEIGHT_PRESET = {"bf16": "BF16 original | 80GB 建議", "nf4_pruned": "NF4 pruned | 40GB 候選、最省容量"}[H3_PRECISION]

import json, fnmatch, math, re
from pathlib import Path

DIFFSYNTH_COMMIT = "7686e54d41d25c0e8ed5f1318acc23b6bb832654"
REVISIONS = {
    "MiniMaxAI/MiniMax-H3": "42ed227ee7df40d41602854ae760620d6eb651fe",
    "DiffSynth-Studio/MiniMax-H3-NF4": "363fdc8fbd7ae55f5b9e7fb87cf3d508df28ee0d",
    "Comfy-Org/MiniMax-H3": "1c41cfca8ebba91d0af792a05c5761fb2c3a7975",
    "lightx2v/Minimax-h3-Turbo": "3ec17a324ced54151364f24f8b5fb6bf7e26414f",
}
TASK_MODES = {
    "FL2VA | 文字／首尾幀（Turbo）": "fl2va",
    "Ref2VA | 多張圖片／多段影片參考": "ref2va",
}
TASK_PROCESSOR_DIRS = {"fl2va": "FL2VA", "ref2va": "Ref2VA"}
MODELS = {
    "Turbo 8-step v1.0 768p | 品質與速度平衡": {
        "id": "turbo8_v1_768p", "lora_scale": 0.0625, "steps": 8, "video_shift": 6.0, "audio_shift": 3.0,
        "lora": "minimax_h3_fl2v_turbo_8step_v1.0_768p_bf16.safetensors"},
    "Turbo 4-step v1.2 768p | 快速預覽、音訊更新": {
        "id": "turbo4_v1_2_768p", "lora_scale": 0.0625, "steps": 4, "video_shift": 6.0, "audio_shift": 3.0,
        "lora": "minimax_h3_fl2v_turbo_4step_v1.2_768p_bf16.safetensors"},
    "Turbo 4-step v1.0 768p | 上游範例基準": {
        "id": "turbo4_v1_0_768p", "lora_scale": 1.0, "steps": 4, "video_shift": 6.0, "audio_shift": 3.0,
        "lora": "minimax_h3_fl2v_turbo_4step_v1.0_768p_bf16.safetensors"},
    "Original 50-step | 原版品質對照": {
        "id": "original50", "lora_scale": None, "steps": 50, "video_shift": 12.0, "audio_shift": 3.0, "lora": None},
    "Ref2VA Turbo 8-step v1.0 768p | 多圖參考快速產片": {
        "id": "ref2va_turbo8_v1_768p", "lora_scale": 0.0625, "steps": 8, "video_shift": 6.0, "audio_shift": 3.0,
        "lora": "minimax_h3_ref2v_turbo_8step_v1.0_768p_bf16.safetensors"},
}
WEIGHTS = {
    "BF16 original | 80GB 建議": "bf16",
    "INT8 ConvRot pruned | 40GB 候選": "int8_pruned",
    "NF4 pruned | 40GB 候選、最省容量": "nf4_pruned",
    "NF4 original | 40GB 候選、未剪枝": "nf4",
}


def selected_config():
    if TASK_MODE not in TASK_MODES or MODEL_PRESET not in MODELS or WEIGHT_PRESET not in WEIGHTS:
        raise ValueError("請使用選單中的任務、模型與量化版本。")
    task_mode = TASK_MODES[TASK_MODE]
    precision = WEIGHTS[WEIGHT_PRESET]
    model = dict(MODELS[MODEL_PRESET])
    if task_mode == "ref2va":
        if MODEL_PRESET not in ("Original 50-step | 原版品質對照", "Ref2VA Turbo 8-step v1.0 768p | 多圖參考快速產片"):
            raise ValueError("Ref2VA 請選原版 50-step 或專用 Ref2VA Turbo 8-step；不能套用 FL2VA LoRA。")
        if precision not in ("bf16", "nf4", "nf4_pruned"):
            raise ValueError("Ref2VA 請選 BF16 original、NF4 pruned 或 NF4 original；INT8 尚未接入此模式。")
    elif MODEL_PRESET == "Ref2VA Turbo 8-step v1.0 768p | 多圖參考快速產片":
        raise ValueError("Ref2VA Turbo 8-step LoRA 只能搭配 Ref2VA 任務模式。")
    return dict(model, precision=precision, task_mode=task_mode,
                model_label=MODEL_PRESET, weight_label=WEIGHT_PRESET, task_label=TASK_MODE)


def component_specs(config):
    base, quant, comfy = "MiniMaxAI/MiniMax-H3", "DiffSynth-Studio/MiniMax-H3-NF4", "Comfy-Org/MiniMax-H3"
    task_mode, precision = config["task_mode"], config["precision"]
    if precision in ("nf4", "nf4_pruned"):
        dit = f"minimax-h3-{task_mode}-{'pruned-' if precision == 'nf4_pruned' else ''}nf4.safetensors"
        return [(quant, f) for f in (dit, "minimax-h3-text-encoder-nf4.safetensors", "video_vae_nf4.safetensors", "audio_vae_nf4.safetensors")]
    if precision == "bf16":
        folder = TASK_PROCESSOR_DIRS[task_mode]
        return [(base, f"{folder}/{p}") for p in ("transformer/model*.safetensors", "text_encoder/model*.safetensors",
                                                  "video_vae/source/model.safetensors", "audio_vae/model.safetensors")]
    if task_mode != "fl2va":
        raise ValueError("Ref2VA 尚未接入 INT8 權重。")
    if precision == "int8_pruned":
        return [(comfy, "diffusion_models/minimax_h3_fl2va_pruned_int8_convrot.safetensors"),
                (comfy, "text_encoders/qwen3vl_32b_minimax_h3_int8_convrot.safetensors"),
                (base, "FL2VA/video_vae/source/model.safetensors"), (base, "FL2VA/audio_vae/model.safetensors")]
    raise ValueError(precision)


def asset_specs(config):
    processor_path = f"{TASK_PROCESSOR_DIRS[config['task_mode']]}/processor/*"
    specs = component_specs(config) + [("MiniMaxAI/MiniMax-H3", processor_path)]
    if config["lora"]:
        specs.append(("lightx2v/Minimax-h3-Turbo", config["lora"]))
    return specs


def config_key(config):
    return json.dumps({"config": config, "diffsynth": DIFFSYNTH_COMMIT, "revisions": REVISIONS}, sort_keys=True)

if H3_TASK_MODE == "ref2va" and H3_PRESET == "turbo8":
    MODELS[MODEL_PRESET]["video_shift"] = 12.0

MODEL_ROOT = Path("/content/h3-models")
SETUP_DIR = Path("/content/minimax-h3-setup")
RUNS_ROOT = Path("/content/minimax-h3-runs")
SETUP_DIR.mkdir(parents=True, exist_ok=True)
print(json.dumps(selected_config(), ensure_ascii=False, indent=2))
print("模型／量化與任務模式只需選一次。接下來執行 2–5；每片只執行後面的 6–7。")


# Source notebook cell: hardware-check
# @title 2. 檢查實際 GPU、RAM 與硬碟
import json, platform, shutil, subprocess
from pathlib import Path
import psutil
import torch

assert torch.cuda.is_available(), "Select a GPU runtime before running this notebook."
gpu = torch.cuda.get_device_properties(0)
free_vram, total_vram = torch.cuda.mem_get_info(0)
vm = psutil.virtual_memory()
disk = shutil.disk_usage("/content")
hardware = {
    "gpu": gpu.name,
    "gpu_count": torch.cuda.device_count(),
    "vram_total_gib": round(total_vram / 2**30, 2),
    "vram_free_gib": round(free_vram / 2**30, 2),
    "ram_total_gib": round(vm.total / 2**30, 2),
    "ram_available_gib": round(vm.available / 2**30, 2),
    "disk_free_gib": round(disk.free / 2**30, 2),
    "python": platform.python_version(),
    "torch": torch.__version__,
    "cuda": torch.version.cuda,
    "bf16_supported": torch.cuda.is_bf16_supported(),
}
(SETUP_DIR / "hardware.json").write_text(json.dumps(hardware, indent=2))
print(json.dumps(hardware, indent=2))
subprocess.run(["nvidia-smi", "--query-gpu=name,memory.total,memory.free,driver_version", "--format=csv"], check=True)

assert gpu.major >= 8 and torch.cuda.is_bf16_supported(), (
    f"本 notebook 需要原生 BF16 運算；{gpu.name} 不適用。V100 為 16/32GB，請選 A100 或更新的 GPU。")
WEIGHT_VRAM_GIB = min(70.0, hardware["vram_total_gib"] - 10.0)
assert WEIGHT_VRAM_GIB > 0, "GPU 記憶體不足以預留推論空間。"
print(f"權重載入預算：{WEIGHT_VRAM_GIB:.2f} GiB；它不是總 VRAM 的硬上限。")
if selected_config()["precision"] == "bf16" and hardware["vram_total_gib"] < 70:
    print("提醒：BF16 的既有實測是 80GB GPU。可用 offload 嘗試本機，或在選單選 INT8／NF4。")

# Source notebook cell: install-inference
# @title 3. 安裝固定版本（同一 kernel 已安裝則略過）
import importlib.metadata, subprocess, sys, time

def install_signature():
    return DIFFSYNTH_COMMIT + ("+comfy-kitchen-0.2.35" if selected_config()["precision"] == "int8_pruned" else "")

if globals().get("_INSTALL_SIGNATURE") != install_signature():
    constraints = []
    for package in ("torch", "torchvision", "torchaudio"):
        try:
            constraints.append(f"{package}=={importlib.metadata.version(package)}")
        except importlib.metadata.PackageNotFoundError:
            pass
    constraint_path = SETUP_DIR / "torch-constraints.txt"
    constraint_path.write_text("\n".join(constraints) + "\n")
    packages = [f"git+https://github.com/modelscope/DiffSynth-Studio.git@{DIFFSYNTH_COMMIT}",
                "transformers==5.16.1", "safetensors==0.8.0", "modelscope==1.40.1",
                "bitsandbytes==0.50.2", "av==18.1.0", "librosa==0.11.0",
                "soundfile==0.14.0", "imageio-ffmpeg==0.6.0"]
    if selected_config()["precision"] == "int8_pruned":
        packages.append("comfy-kitchen==0.2.35")
    subprocess.run([sys.executable, "-m", "pip", "install", "--disable-pip-version-check",
                    "-c", str(constraint_path), *packages], check=True)
    _INSTALL_SIGNATURE = install_signature()
else:
    print("沿用本 kernel 已安裝的套件。")

from diffsynth.pipelines.minimax_h3_audio_video import MiniMaxH3Pipeline, ModelConfig
from diffsynth.utils.data.audio_video import write_video_audio
versions = {name: importlib.metadata.version(name) for name in (
    "diffsynth", "torch", "transformers", "bitsandbytes", "modelscope", "safetensors")}
if selected_config()["precision"] == "int8_pruned":
    import comfy_kitchen
    # DiffSynth may already be imported before switching BF16 -> INT8 in this kernel.
    from diffsynth.core.quant.backends import comfy_kitchen as ck_backend
    if not ck_backend.COMFY_KITCHEN_AVAILABLE:
        raise RuntimeError("INT8 套件已安裝。請重新啟動 kernel，再執行 A 區；磁碟上的模型快取會保留。")
    versions["comfy-kitchen"] = importlib.metadata.version("comfy-kitchen")
(SETUP_DIR / "versions.json").write_text(json.dumps(versions, indent=2))
print(json.dumps(versions, indent=2))

# Source notebook cell: download-models
# @title 4. 只下載選中的固定版本（不會下載整套選單）
assert globals().get("_INSTALL_SIGNATURE") == install_signature(), "請先成功執行安裝。"
import os
from concurrent.futures import ThreadPoolExecutor, as_completed
os.environ["HF_XET_CHUNK_CACHE_SIZE_BYTES"] = "0"
os.environ["HF_XET_NUM_CONCURRENT_RANGE_GETS"] = "4"
from huggingface_hub import HfApi, hf_hub_download
from huggingface_hub.utils import disable_progress_bars
disable_progress_bars()

def repo_dir(repo):
    # Revisions have separate directories, so changing a pin never reuses another revision's bytes.
    return MODEL_ROOT / repo.replace("/", "--") / REVISIONS[repo]

config = selected_config()
_DOWNLOAD_KEY = None
manifest, seen, infos = [], set(), {}
for repo, pattern in asset_specs(config):
    if repo not in infos:
        infos[repo] = HfApi().model_info(repo, revision=REVISIONS[repo], files_metadata=True, token=False)
    matches = [item for item in infos[repo].siblings if fnmatch.fnmatchcase(item.rfilename, pattern)]
    assert matches, f"固定版本中找不到檔案：{repo} / {pattern}"
    for item in matches:
        if (repo, item.rfilename) in seen:
            continue
        seen.add((repo, item.rfilename))
        assert item.size is not None
        manifest.append({"repo": repo, "revision": REVISIONS[repo], "file": item.rfilename,
                         "size": item.size, "local_dir": str(repo_dir(repo))})
def cached_size(item):
    path = Path(item["local_dir"]) / item["file"]
    return path.stat().st_size if path.is_file() else 0
missing_bytes = sum(item["size"] for item in manifest if cached_size(item) != item["size"])
print(f"選定檔案：{len(manifest)} 個，共 {sum(x['size'] for x in manifest)/2**30:.2f} GiB；待下載 {missing_bytes/2**30:.2f} GiB。", flush=True)
assert shutil.disk_usage("/content").free > missing_bytes + 8 * 2**30, "硬碟空間不足，請改選量化版本或清理不用的模型。"
(SETUP_DIR / "model_manifest.json").write_text(json.dumps(manifest, indent=2))
started = time.perf_counter()
def download_one(item):
    return hf_hub_download(item["repo"], item["file"], revision=item["revision"],
                           local_dir=item["local_dir"], token=False)
with ThreadPoolExecutor(max_workers=4) as pool:
    futures = {pool.submit(download_one, item): item for item in manifest}
    for count, future in enumerate(as_completed(futures), 1):
        future.result()
        print(f"[{count}/{len(manifest)}] {futures[future]['file']}", flush=True)
assert all(cached_size(item) == item["size"] for item in manifest), "下載檔案大小檢查失敗。"
DOWNLOAD_SECONDS = time.perf_counter() - started
_DOWNLOAD_KEY = config_key(config)
print(f"下載完成：{DOWNLOAD_SECONDS:.1f}s")

# Source notebook cell: load-model
# @title 5. 載入模型一次（下一片沿用，不重建）
import gc


def adapt_comfy_qkv_lora(state_dict, head_dim=128):
    # Native H3: [head, QKV, channel]; Comfy pruned H3: [QKV, head, channel].
    # Permute B's output rows only: P(B @ A) == (P B) @ A.
    result = dict(state_dict)
    for name, weight in state_dict.items():
        if name.endswith(".attn.qkv_proj.lora_B.weight"):
            rows, rank = weight.shape
            assert rows % (3 * head_dim) == 0, f"Unexpected QKV LoRA shape: {weight.shape}"
            result[name] = weight.reshape(-1, 3, head_dim, rank).permute(1, 0, 2, 3).reshape(rows, rank).contiguous()
    return result


def configure_lora_layout(pipeline, precision):
    if precision not in ("nf4_pruned", "int8_pruned"):
        return
    from diffsynth.utils.lora.minimax_h3 import MiniMaxH3LoRALoader
    class ComfyLayoutH3LoRALoader(MiniMaxH3LoRALoader):
        def convert_state_dict(self, state_dict, suffix=".weight"):
            native_lightx2v = self.is_lightx2v_format(state_dict)
            converted = super().convert_state_dict(state_dict, suffix=suffix)
            # Already converted/Comfy LoRAs must not be permuted a second time.
            if native_lightx2v:
                assert suffix == ".weight"
                converted = adapt_comfy_qkv_lora(converted)
            return converted
    pipeline.lora_loader = ComfyLayoutH3LoRALoader


def ensure_model_loaded():
    global pipe, _LOADED_KEY, _LOADED_CONFIG, LOAD_SECONDS
    config = selected_config()
    key = config_key(config) + f"|vram={WEIGHT_VRAM_GIB}"
    if globals().get("_LOADED_KEY") == key and globals().get("pipe") is not None:
        print("沿用已載入的模型；沒有重新載入或重複加入 LoRA。")
        return pipe
    assert globals().get("_DOWNLOAD_KEY") == config_key(config), "模型設定有變更，請先執行 A 區下載。"
    _LOADED_KEY = None
    pipe = None
    gc.collect()
    torch.cuda.empty_cache()
    started = time.perf_counter()
    vram_config = {
        "offload_dtype": "disk", "offload_device": "disk",
        "onload_dtype": "disk", "onload_device": "disk",
        "preparing_dtype": torch.bfloat16, "preparing_device": "cuda",
        "computation_dtype": torch.bfloat16, "computation_device": "cuda",
    }
    configs = []
    for repo, pattern in component_specs(config):
        paths = sorted(str(repo_dir(repo) / item["file"]) for item in manifest
                       if item["repo"] == repo and fnmatch.fnmatchcase(item["file"], pattern))
        assert paths and all(Path(path).is_file() for path in paths), f"模型檔案缺少：{pattern}"
        configs.append(ModelConfig(path=paths if "*" in pattern else paths[0], **vram_config))
    try:
        processor_dir = repo_dir("MiniMaxAI/MiniMax-H3") / TASK_PROCESSOR_DIRS[config["task_mode"]] / "processor"
        pipe = MiniMaxH3Pipeline.from_pretrained(
            torch_dtype=torch.bfloat16, device="cuda", model_configs=configs,
            processor_config=ModelConfig(path=str(processor_dir)),
            vram_limit=WEIGHT_VRAM_GIB)
        if config["lora"]:
            configure_lora_layout(pipe, config["precision"])
            lora_path = repo_dir("lightx2v/Minimax-h3-Turbo") / config["lora"]
            # Preserve training alpha/rank from the pinned native header (user strength stays 1).
            pipe.load_lora(pipe.dit, ModelConfig(path=str(lora_path)), alpha=config["lora_scale"], hotload=True)
            # All three pinned native adapters have 52 attention/MLP groups, four fused targets each.
            patched = sum(bool(getattr(module, "lora_A_weights", [])) for module in pipe.dit.modules())
            assert patched == 208, f"LoRA 只套用了 {patched}/208 層，停止以免誤用未加速的模型。"
        _LOADED_CONFIG = dict(config)
        _LOADED_KEY = key
        LOAD_SECONDS = round(time.perf_counter() - started, 2)
        (SETUP_DIR / "loaded_model.json").write_text(json.dumps(
            {"config": config, "load_seconds": LOAD_SECONDS, "weight_vram_gib": WEIGHT_VRAM_GIB}, indent=2, ensure_ascii=False))
        print(f"{config['task_mode'].upper()} 模型已就緒（{LOAD_SECONDS}s）。接下來只需執行 6–7。")
        return pipe
    except Exception:
        pipe = None
        gc.collect()
        torch.cuda.empty_cache()
        raise


ensure_model_loaded()
