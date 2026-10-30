"""Recreated FastH3 text-to-video/audio graphs; no GPU imports or downloads."""

import json
import math
from pathlib import Path, PurePosixPath
import re


DEFAULT_PROMPT = (
    "integrated_multimodal_description: [Shot 1] A small red toy train rolls slowly "
    "from left to right along a wooden track on a clean tabletop. The train stays "
    "fully visible in a steady wide shot; its wheels turn as it moves. No dialogue.\n"
    "overall_soundscape: Quiet room ambience and gentle wheel clicks on the wooden track.\n"
    "non_diegetic_music: N/A"
)
UNET_NAME = "minimax_h3_fastvideo_vsa_datafree_1300step_4step_int8_convrot.safetensors"
CLIP_NAME = "qwen3vl_32b_minimax_h3_nvfp4_awq.safetensors"
VIDEO_VAE_NAME = "minimax_h3_video_vae_int8_convrot.safetensors"
AUDIO_VAE_NAME = "minimax_h3_audio_vae_fp32.safetensors"


def model_frame_count(duration_seconds):
    """Round 24 fps output up to the native 17k+5 grid before final trimming."""
    if type(duration_seconds) is not int or not 5 <= duration_seconds <= 15:
        raise ValueError("duration_seconds must be an integer from 5 to 15")
    return ((duration_seconds * 24 - 5 + 16) // 17) * 17 + 5


def build_graph(prompt, width=864, height=480, duration_seconds=5,
                seed=123456662, loras=None, run_name="fast_h3",
                generation_mode="t2va", reference_images=None, request_id=None):
    length = model_frame_count(duration_seconds)
    if any(type(value) is not int or value <= 0 or value % 32 for value in (width, height)):
        raise ValueError("width and height must be positive integer multiples of 32")
    if width * height > 1344 * 768:
        raise ValueError("requested area exceeds 1344 x 768")
    if type(seed) is not int or not 0 <= seed <= 2**64 - 1:
        raise ValueError("seed must be an integer from 0 to 2^64-1")
    if generation_mode not in ("t2va", "experimental_ref2va_ood"):
        raise ValueError("generation_mode must be t2va or experimental_ref2va_ood")
    reference_images = [] if reference_images is None else reference_images
    if not isinstance(reference_images, list):
        raise ValueError("reference_images must be a resolved list of ComfyUI input filenames")
    experimental = generation_mode == "experimental_ref2va_ood"
    if (experimental and not 1 <= len(reference_images) <= 3) or (not experimental and reference_images):
        raise ValueError("Experimental Ref2VA requires 1–3 images; T2VA requires none")
    for name in reference_images:
        if (not isinstance(name, str) or not name or "\\" in name or ".." in PurePosixPath(name).parts
                or PurePosixPath(name).is_absolute() or PurePosixPath(name).suffix.lower() not in (".png", ".jpg", ".jpeg", ".webp")):
            raise ValueError("References must be relative ComfyUI input image filenames")
    if len(set(reference_images)) != len(reference_images):
        raise ValueError("Do not repeat the same reference file")
    fields = (("subject_definitions", "summary", "retention_analysis", "detailed_description", "overall_soundscape", "non_diegetic_music")
              if experimental else ("integrated_multimodal_description", "overall_soundscape", "non_diegetic_music"))
    pattern = r"\A\s*" + r"\s*".join(re.escape(field) + r":\s*(.+?)" for field in fields) + r"\s*\Z"
    match = re.fullmatch(pattern, prompt, flags=re.DOTALL) if isinstance(prompt, str) else None
    if match is None or not all(value.strip() for value in match.groups()):
        raise ValueError("prompt must contain all nonempty H3 mode fields in canonical order")
    tags = re.findall(r"<(Picture|Video|Audio)\s+(\d+)>", prompt, flags=re.IGNORECASE)
    if not experimental and tags:
        raise ValueError("reference tags are unsupported by this text-only workflow")
    if experimental:
        if any(kind.lower() != "picture" for kind, _ in tags):
            raise ValueError("This experiment supports image references only")
        if {int(number) for _, number in tags} != set(range(1, len(reference_images) + 1)):
            raise ValueError("Picture tags must match the ordered reference images exactly")
        if not match.group(2).lstrip().startswith("[reference generation]"):
            raise ValueError("Ref2VA summary must start with [reference generation]")
    if not isinstance(run_name, str) or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.-]*", run_name):
        raise ValueError("run_name must be a filename-safe name without path separators")
    if loras is None:
        loras = []
    if not isinstance(loras, list):
        raise ValueError("loras must be a resolved list of lora_name/strength_model dictionaries")

    def node(class_type, **inputs):
        return {"class_type": class_type, "inputs": inputs}

    graph = {"1": node("UNETLoader", unet_name=UNET_NAME, weight_dtype="default")}
    model = ["1", 0]
    for index, lora in enumerate(loras):
        if not isinstance(lora, dict) or set(lora) != {"lora_name", "strength_model"}:
            raise ValueError("each LoRA must have exactly lora_name and strength_model")
        name, strength = lora["lora_name"], lora["strength_model"]
        if (not isinstance(name, str) or not name or "\\" in name
                or PurePosixPath(name).is_absolute() or ".." in PurePosixPath(name).parts
                or not name.endswith(".safetensors")):
            raise ValueError("lora_name must be a relative .safetensors model filename")
        if type(strength) not in (int, float) or not math.isfinite(strength):
            raise ValueError("strength_model must be a finite number")
        identity = str(100 + index)
        graph[identity] = node("FastH3CheckedLoraLoader", model=model, lora_name=name,
                               strength_model=float(strength))
        model = [identity, 0]
    graph.update({
        "2": node("MiniMaxH3SigmaShift", model=model, shift_video=12.0, shift_audio=3.0),
        "3": node("FastH3VSAPatch", model=["2", 0], keep_percent=10.0, min_tokens=8192,
                  failure_mode="error", allow_unsupported_conditioning=experimental, verbose=True),
        "4": node("CLIPLoader", clip_name=CLIP_NAME, type="minimax", device="default"),
        "5": node("VAELoader", vae_name=VIDEO_VAE_NAME),
        "6": node("VAELoader", vae_name=AUDIO_VAE_NAME),
        "7": node("MiniMaxH3ImageToVideo", clip=["4", 0], vae=["5", 0], prompt=prompt,
                  width=width, height=height, length=length),
        "8": node("BasicGuider", model=["3", 0], conditioning=["7", 0]),
        "9": node("FastH3ExactSigmas", model=["3", 0]),
        "10": node("KSamplerSelect", sampler_name="euler"),
        "11": node("RandomNoise", noise_seed=seed),
        "12": node("SamplerCustomAdvanced", noise=["11", 0], guider=["8", 0], sampler=["10", 0],
                   sigmas=["9", 0], latent_image=["7", 1]),
        "13": node("VAEDecode", samples=["12", 0], vae=["5", 0]),
        "14": node("VAEDecodeAudio", samples=["12", 0], vae=["6", 0]),
        "15": node("FastH3ReportAndTrim", model=["3", 0], sigmas=["9", 0], images=["13", 0],
                   audio=["14", 0], duration_seconds=float(duration_seconds)),
        "16": node("CreateVideo", images=["15", 0], audio=["15", 1], fps=24.0),
        "17": node("SaveVideo", video=["16", 0], filename_prefix="fast_h3/" + run_name,
                   **{"format": "mp4", "format.codec": "h264", "format.codec.encoding": "auto"}),
    })
    if experimental:
        for index, name in enumerate(reference_images):
            graph[str(200 + index)] = node("LoadImage", image=name)
        graph["7"] = node("FastH3ExperimentalReference", model=["3", 0], clip=["4", 0], vae=["5", 0],
                          prompt=prompt, width=width, height=height, length=length,
                          **{f"reference_{index + 1}": [str(200 + index), 0] for index in range(len(reference_images))})
        graph["8"]["inputs"].update(model=["7", 0], conditioning=["7", 1])
        graph["9"]["inputs"]["model"] = ["7", 0]
        graph["12"]["inputs"]["latent_image"] = ["7", 2]
        graph["15"]["inputs"]["model"] = ["7", 0]
        graph["19"] = node("FastH3SampleRequest", noise=["11", 0], request_id=request_id or run_name)
        graph["12"]["inputs"]["noise"] = ["19", 0]
    return graph


# Input order and widget types follow ComfyUI/VSA node schemas. Seed-control and
# optional CreateVideo widgets are frontend settings, not required API inputs.
_SCHEMAS = {
    "UNETLoader": ([("unet_name", "COMBO"), ("weight_dtype", "COMBO")], ["MODEL"]),
    "FastH3CheckedLoraLoader": ([("model", "MODEL"), ("lora_name", "COMBO"), ("strength_model", "FLOAT")], ["MODEL"]),
    "MiniMaxH3SigmaShift": ([("model", "MODEL"), ("shift_video", "FLOAT"), ("shift_audio", "FLOAT")], ["MODEL"]),
    "FastH3VSAPatch": ([("model", "MODEL"), ("keep_percent", "FLOAT"), ("min_tokens", "INT"),
                        ("failure_mode", "COMBO"), ("allow_unsupported_conditioning", "BOOLEAN"),
                        ("verbose", "BOOLEAN")], ["MODEL", "STRING"]),
    "CLIPLoader": ([("clip_name", "COMBO"), ("type", "COMBO"), ("device", "COMBO")], ["CLIP"]),
    "VAELoader": ([("vae_name", "COMBO")], ["VAE"]),
    "LoadImage": ([("image", "COMBO")], ["IMAGE", "MASK"]),
    "FastH3SampleRequest": ([("noise", "NOISE"), ("request_id", "STRING")], ["NOISE"]),
    "FastH3ExperimentalReference": ([("model", "MODEL"), ("clip", "CLIP"), ("vae", "VAE"),
        ("prompt", "STRING"), ("width", "INT"), ("height", "INT"), ("length", "INT"),
        ("reference_1", "IMAGE"), ("reference_2", "IMAGE"), ("reference_3", "IMAGE")], ["MODEL", "CONDITIONING", "LATENT"]),
    "MiniMaxH3ImageToVideo": ([("clip", "CLIP"), ("vae", "VAE"), ("prompt", "STRING"),
                              ("width", "INT"), ("height", "INT"), ("length", "INT")], ["CONDITIONING", "LATENT"]),
    "BasicGuider": ([("model", "MODEL"), ("conditioning", "CONDITIONING")], ["GUIDER"]),
    "FastH3ExactSigmas": ([("model", "MODEL")], ["SIGMAS", "STRING"]),
    "KSamplerSelect": ([("sampler_name", "COMBO")], ["SAMPLER"]),
    "RandomNoise": ([("noise_seed", "INT")], ["NOISE"]),
    "SamplerCustomAdvanced": ([("noise", "NOISE"), ("guider", "GUIDER"), ("sampler", "SAMPLER"),
                               ("sigmas", "SIGMAS"), ("latent_image", "LATENT")], ["LATENT", "LATENT"]),
    "VAEDecode": ([("samples", "LATENT"), ("vae", "VAE")], ["IMAGE"]),
    "VAEDecodeAudio": ([("samples", "LATENT"), ("vae", "VAE")], ["AUDIO"]),
    "FastH3ReportAndTrim": ([("model", "MODEL"), ("sigmas", "SIGMAS"), ("images", "IMAGE"),
                            ("audio", "AUDIO"), ("duration_seconds", "FLOAT")], ["IMAGE", "AUDIO", "STRING"]),
    "CreateVideo": ([("images", "IMAGE"), ("fps", "FLOAT"), ("audio", "AUDIO")], ["VIDEO"]),
    "SaveVideo": ([("video", "VIDEO"), ("filename_prefix", "STRING"), ("format", "COMFY_DYNAMICCOMBO_V3"),
                   ("format.codec", "COMFY_DYNAMICCOMBO_V3"), ("format.codec.encoding", "COMFY_DYNAMICCOMBO_V3")], ["VIDEO"]),
}
_POSITIONS = {1: (0, 0), 2: (720, 0), 3: (720, 190), 4: (0, 180), 5: (0, 370),
              6: (0, 500), 7: (0, 700), 8: (1100, 0), 9: (1100, 170), 10: (1100, 340),
              11: (1100, 500), 12: (1470, 550), 13: (1860, 0), 14: (1860, 170),
              15: (1860, 370), 16: (2250, 0), 17: (2640, 0), 19: (1100, 680),
              200: (-660, 600), 201: (-660, 950), 202: (-660, 1300)}


def to_ui_workflow(graph):
    """Convert this builder's API graph to ComfyUI workflow schema 0.4."""
    nodes, links, ordered = [], [], []
    pending = dict(graph)
    while pending:
        ready = [identity for identity, node in pending.items()
                 if all(not isinstance(value, list) or value[0] in ordered for value in node["inputs"].values())]
        if not ready:
            raise ValueError("graph has missing link sources or a cycle")
        for identity in ready:
            ordered.append(identity)
            del pending[identity]
    for order, identity in enumerate(ordered):
        api = graph[identity]
        input_specs, output_types = _SCHEMAS[api["class_type"]]
        if api["class_type"] == "FastH3ExperimentalReference":
            input_specs = [(name, kind) for name, kind in input_specs
                           if name not in ("reference_2", "reference_3") or name in api["inputs"]]
        if set(api["inputs"]) != {name for name, _ in input_specs}:
            raise ValueError(f"node {identity} inputs differ from supported workflow schema")
        inputs, widgets = [], []
        for name, kind in input_specs:
            value = api["inputs"][name]
            entry = {"name": name, "type": kind, "link": None}
            if isinstance(value, list):
                source, slot = value
                source_types = _SCHEMAS[graph[source]["class_type"]][1]
                if type(slot) is not int or not 0 <= slot < len(source_types) or source_types[slot] != kind:
                    raise ValueError(f"node {identity} has invalid output slot or link type")
                link_id = len(links) + 1
                entry["link"] = link_id
                links.append([link_id, int(source), slot, int(identity), len(inputs), kind])
            else:
                entry["widget"] = {"name": name}
                widgets.append(value)
            inputs.append(entry)
        if api["class_type"] == "RandomNoise":
            widgets.append("fixed")
        elif api["class_type"] == "CreateVideo":
            widgets.extend(["auto", "sRGB", "none"])
            inputs.extend({"name": name, "type": "COMBO", "link": None, "widget": {"name": name}}
                          for name in ("bit_depth", "color_space", "codec"))
        node_id = int(identity)
        width = 620 if node_id in (1, 4, 5, 6, 7) else 330
        height = 420 if node_id == 7 else 70 + 24 * max(len(widgets), len(inputs))
        pos = _POSITIONS.get(node_id, (0, 1220 + (node_id - 100) * 190))
        nodes.append({"id": node_id, "type": api["class_type"], "pos": list(pos), "size": [width, height],
                      "flags": {}, "order": order, "mode": 0, "inputs": inputs,
                      "outputs": [{"name": kind, "type": kind, "links": None, "slot_index": slot}
                                  for slot, kind in enumerate(output_types)],
                      "properties": {"Node name for S&R": api["class_type"]}, "widgets_values": widgets})
    by_id = {node["id"]: node for node in nodes}
    for link_id, source, slot, *_ in links:
        output = by_id[source]["outputs"][slot]
        if output["links"] is None:
            output["links"] = []
        output["links"].append(link_id)
    notes = ("## 自行重建的 FastH3 文生影音工作流\n\n"
             "依公開節點重建，並非受限作者原始 JSON。預設 864×480、24 fps、5 秒；"
             "原生 124 幀經影音裁切後輸出 120 幀。僅文生影音，不含首尾幀或參考素材。\n\n"
             "student → 可選 LoRA → Sigma Shift → 嚴格 VSA → 四步 Euler → 影音解碼 → 裁切 → MP4。"
             "不預設掛載 Turbo LoRA。L4 已完成 864×480、5 秒文生影音測試，200 次 VSA、零 fallback。\n\n"
             "Colab L4 請用 --disable-comfy-compiler 啟動 ComfyUI，保留動態 VRAM 與 offload。"
             "其他尺寸／片長及實際內容 LoRA 的品質需另行測試。")
    if graph["7"]["class_type"] == "FastH3ExperimentalReference":
        notes = ("## FastH3 圖片參照實驗（未蒸餾 Ref2VA）\n\n"
                 "圖片經原生 MiniMaxH3ReferenceToVideo 送入 Qwen 與 video VAE；每個 DiT forward 核對 ref_img rows。"
                 "四步 checkpoint 的訓練範圍仍為 T2VA，本接線屬分布外實驗，人物品質須另驗。"
                 "VSA override 只對此實驗分支開啟；仍要求 200 VSA、零 fallback，不掛 speed LoRA。")
    nodes.append({"id": 18, "type": "MarkdownNote", "pos": [720, 850], "size": [1090, 260],
                  "flags": {}, "order": len(nodes), "mode": 0, "inputs": [], "outputs": [],
                  "properties": {}, "widgets_values": [notes]})
    groups = []
    for title, members, color in (("模型與文字條件（可選 LoRA）", {1, 4, 5, 6, 7} | {int(i) for i in graph if int(i) >= 100}, "#3f789e"),
                                   ("嚴格 VSA 與四步 Euler", set(range(2, 4)) | set(range(8, 13)), "#6b659b"),
                                   ("影音解碼、裁切與 MP4", set(range(13, 18)), "#4f8a73")):
        chosen = [node for node in nodes if node["id"] in members]
        left = min(node["pos"][0] for node in chosen) - 20
        top = min(node["pos"][1] for node in chosen) - 60
        right = max(node["pos"][0] + node["size"][0] for node in chosen) + 20
        bottom = max(node["pos"][1] + node["size"][1] for node in chosen) + 20
        groups.append({"title": title, "bounding": [left, top, right - left, bottom - top], "color": color, "font_size": 24, "flags": {}})
    return {"last_node_id": max(max(by_id), 18), "last_link_id": len(links), "nodes": nodes, "links": links,
            "groups": groups, "config": {}, "extra": {"ds": {"scale": 0.5, "offset": [60, 100]},
            "fast_h3_notes": notes},
            "version": 0.4}


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Export the public FastH3 UI/API workflow; --help is read-only.")
    parser.add_argument("--output-dir", type=Path, default=Path(__file__).resolve().parents[1] / "workflows")
    destination = parser.parse_args().output_dir
    destination.mkdir(parents=True, exist_ok=True)
    graph = build_graph(DEFAULT_PROMPT)
    for name, content in (("fast_h3_l4.api.json", graph), ("fast_h3_l4.json", to_ui_workflow(graph))):
        (destination / name).write_text(json.dumps(content, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
