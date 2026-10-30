#!/usr/bin/env python3
"""Export native ComfyUI super-resolution graphs and a FastH3 post-process branch."""

from __future__ import annotations

import argparse
import copy
import json
from pathlib import Path, PurePosixPath

import fast_h3_workflow as fast_h3


ROOT = Path(__file__).resolve().parents[1]
CATALOG = Path(__file__).with_name("media_upscale_models.json")
DEFAULT_MODEL = "realesrgan-x2plus"

# Input order matches the ComfyUI commit used by the existing FastH3 runtime.
SCHEMAS = {
    "LoadImage": ([("image", "COMBO")], ["IMAGE", "MASK"]),
    "LoadVideo": ([("file", "COMBO")], ["VIDEO"]),
    "GetVideoComponents": ([("video", "VIDEO")], ["IMAGE", "AUDIO", "FLOAT", "COMBO", "COMBO"]),
    "UpscaleModelLoader": ([("model_name", "COMBO")], ["UPSCALE_MODEL"]),
    "ImageUpscaleWithModel": ([("upscale_model", "UPSCALE_MODEL"), ("image", "IMAGE")], ["IMAGE"]),
    "ImageScaleBy": ([("image", "IMAGE"), ("upscale_method", "COMBO"), ("scale_by", "FLOAT")], ["IMAGE"]),
    "SaveImage": ([("images", "IMAGE"), ("filename_prefix", "STRING")], []),
    "CreateVideo": ([("images", "IMAGE"), ("fps", "FLOAT"), ("audio", "AUDIO")], ["VIDEO"]),
    "SaveVideo": ([("video", "VIDEO"), ("filename_prefix", "STRING"),
                   ("format", "COMFY_DYNAMICCOMBO_V3"), ("format.codec", "COMFY_DYNAMICCOMBO_V3"),
                   ("format.codec.encoding", "COMFY_DYNAMICCOMBO_V3"),
                   ("format.codec.encoding.crf", "FLOAT")], ["VIDEO"]),
}


def model_spec(model_id: str, scale: int) -> dict:
    models = json.loads(CATALOG.read_text(encoding="utf-8"))["models"]
    if model_id not in models:
        raise ValueError(f"Unknown model: {model_id}")
    if type(scale) is not int or scale not in (2, 4) or scale > models[model_id]["scale"]:
        raise ValueError("Use scale 2 or 4, no greater than the model's native scale")
    return models[model_id]


def node(class_type: str, **inputs) -> dict:
    return {"class_type": class_type, "inputs": inputs}


def save_video(video: list, prefix: str) -> dict:
    return node("SaveVideo", video=video, filename_prefix=prefix,
                **{"format": "mp4", "format.codec": "h264",
                   "format.codec.encoding": "re-encode", "format.codec.encoding.crf": 18.0})


def add_upscale(graph: dict, images: list, model_id: str, scale: int, start_id: int) -> list:
    spec = model_spec(model_id, scale)
    identity = str(start_id)
    if any(str(start_id + offset) in graph for offset in range(3)):
        raise ValueError("Upscale node IDs conflict with the input graph")
    graph[identity] = node("UpscaleModelLoader", model_name=spec["file"])
    graph[str(start_id + 1)] = node("ImageUpscaleWithModel", upscale_model=[identity, 0], image=images)
    output = [str(start_id + 1), 0]
    if scale != spec["scale"]:
        graph[str(start_id + 2)] = node("ImageScaleBy", image=output, upscale_method="lanczos",
                                      scale_by=scale / spec["scale"])
        output = [str(start_id + 2), 0]
    return output


def build_graph(kind: str, model_id: str = DEFAULT_MODEL, scale: int = 2,
                input_name: str | None = None, fast_h3_graph: dict | None = None) -> dict:
    """Return a fresh graph; a FastH3 branch keeps its original output and receipt."""
    model_spec(model_id, scale)
    if kind not in ("image", "video", "fast-h3"):
        raise ValueError("kind must be image, video, or fast-h3")
    if input_name is not None:
        name = PurePosixPath(input_name)
        if not input_name or name.is_absolute() or ".." in name.parts or "\\" in input_name:
            raise ValueError("input_name must be a relative ComfyUI input filename")
    prefix = f"ai_upscale/{kind}_{scale}x"
    if kind == "image":
        graph = {"1": node("LoadImage", image=input_name or "input.png")}
        images = add_upscale(graph, ["1", 0], model_id, scale, 2)
        graph["5"] = node("SaveImage", images=images, filename_prefix=prefix)
    elif kind == "video":
        graph = {"1": node("LoadVideo", file=input_name or "input.mp4"),
                 "2": node("GetVideoComponents", video=["1", 0])}
        images = add_upscale(graph, ["2", 0], model_id, scale, 3)
        graph["6"] = node("CreateVideo", images=images, fps=["2", 2], audio=["2", 1])
        graph["7"] = save_video(["6", 0], prefix)
    else:
        graph = copy.deepcopy(fast_h3_graph if fast_h3_graph is not None
                              else fast_h3.build_graph(fast_h3.DEFAULT_PROMPT))
        if (graph.get("15", {}).get("class_type") != "FastH3ReportAndTrim"
                or graph.get("16", {}).get("class_type") != "CreateVideo"):
            raise ValueError("Expected the current FastH3 trimmed-image/audio graph")
        images = add_upscale(graph, ["15", 0], model_id, scale, 300)
        graph["303"] = node("CreateVideo", images=images, fps=graph["16"]["inputs"]["fps"], audio=["15", 1])
        graph["304"] = save_video(["303", 0], f"ai_upscale/fast_h3_{scale}x")
    return graph


def ordered_ids(graph: dict) -> list[str]:
    """Topological node order also handles a post-process branch added to an existing graph."""
    result, pending = [], list(graph)
    while pending:
        ready = [identity for identity in pending if all(
            value[0] in result for value in graph[identity]["inputs"].values() if isinstance(value, list))]
        if not ready:
            raise ValueError("Graph has a cycle or unresolved source node")
        result.extend(ready)
        pending = [identity for identity in pending if identity not in ready]
    return result


def to_ui_workflow(graph: dict, kind: str, model_id: str = DEFAULT_MODEL, scale: int = 2) -> dict:
    spec = model_spec(model_id, scale)
    schemas = {**fast_h3._SCHEMAS, **SCHEMAS}
    nodes, links = [], []
    for order, identity in enumerate(ordered_ids(graph)):
        api = graph[identity]
        input_specs, output_types = schemas[api["class_type"]]
        # The unmodified FastH3 SaveVideo uses the automatic encoding widget.
        input_specs = [(name, type_) for name, type_ in input_specs
                       if name in api["inputs"]]
        if set(api["inputs"]) != {name for name, _ in input_specs}:
            raise ValueError(f"Unsupported inputs on node {identity}")
        inputs, widgets = [], []
        for name, type_ in input_specs:
            value = api["inputs"][name]
            entry = {"name": name, "type": type_, "link": None}
            if isinstance(value, list):
                source, slot = value
                source_types = schemas[graph[source]["class_type"]][1]
                if type(slot) is not int or not 0 <= slot < len(source_types) or source_types[slot] != type_:
                    raise ValueError(f"Invalid link type on node {identity}: {name}")
                link_id = len(links) + 1
                entry["link"] = link_id
                links.append([link_id, int(source), slot, int(identity), len(inputs), type_])
                if type_ in ("FLOAT", "INT", "COMBO"):
                    entry["widget"] = {"name": name}
                    # A converted widget remains in widgets_values even when linked.
                    if api["class_type"] == "CreateVideo" and name == "fps":
                        widgets.append(30.0)
                    else:
                        raise ValueError(f"Missing converted-widget default for {identity}: {name}")
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
        if kind == "fast-h3" and node_id < 300:
            pos = fast_h3._POSITIONS.get(int(identity), (0, 1300 + int(identity) * 180))
        elif kind == "fast-h3":
            pos = {300: (1420, 900), 301: (1860, 900), 302: (1860, 1160),
                   303: (2250, 900), 304: (2640, 900)}[node_id]
        elif kind == "image":
            pos = {1: (0, 0), 2: (0, 280), 3: (440, 60), 4: (880, 60),
                   5: (1320 if "4" in graph else 880, 60)}[node_id]
        else:
            pos = {1: (0, 0), 2: (420, 0), 3: (420, 330), 4: (840, 0), 5: (1260, 0),
                   6: (1680 if "5" in graph else 1260, 0),
                   7: (2100 if "5" in graph else 1680, 0)}[node_id]
        prompt_node = api["class_type"] in ("MiniMaxH3ImageToVideo", "FastH3ExperimentalReference")
        width = 620 if kind == "fast-h3" and node_id in (1, 4, 5, 6, 7) else 340
        size = [width, 420 if prompt_node else 90 + 24 * len(inputs)]
        nodes.append({"id": int(identity), "type": api["class_type"], "pos": list(pos), "size": size,
                      "flags": {}, "order": order, "mode": 0, "inputs": inputs,
                      "outputs": [{"name": type_, "type": type_, "links": None, "slot_index": slot}
                                  for slot, type_ in enumerate(output_types)],
                      "properties": {"Node name for S&R": api["class_type"]}, "widgets_values": widgets})
    by_id = {entry["id"]: entry for entry in nodes}
    for link_id, source, slot, *_ in links:
        output = by_id[source]["outputs"][slot]
        if output["links"] is None:
            output["links"] = []
        output["links"].append(link_id)
    note = (f"# AI {scale}x enlarger\n\nModel: {spec['file']} (native {spec['scale']}x). "
            "Put the verified weight in ComfyUI/models/upscale_models. "
            "Core ImageUpscaleWithModel uses tiled inference. "
            "A native 4x model followed by Lanczos 0.5 produces a 2x delivery.\n\n"
            "Use 8-bit SDR inputs. Upload your image/video in the Load node, then queue. "
            "For transparency, use the streaming CLI/notebook image path. "
            "Video frames are processed independently: check flicker in playback. "
            "Video fps and audio come from the source; no frame interpolation.\n\n"
            "The native video graph materializes all frames. For long clips or limited RAM, "
            "use scripts/media_upscale.py or AI_Media_Upscaler_Colab.ipynb. See doc/AI_UPSCALER.md.")
    if kind == "fast-h3":
        note += ("\n\nFastH3 L4: the original generation, VSA receipt, trim and native MP4 remain connected. "
                 "The new branch starts AFTER trimming and writes a second, enlarged MP4. "
                 "Use this variant directly in ComfyUI; existing fast_h3_colab.py keeps its native-output contract.")
    note_id = max(by_id) + 1
    nodes.append({"id": note_id, "type": "MarkdownNote", "pos": [0, -420], "size": [1160, 350],
                  "flags": {}, "order": len(nodes), "mode": 0, "inputs": [], "outputs": [],
                  "properties": {}, "widgets_values": [note]})
    members = [entry for entry in nodes if entry["type"] != "MarkdownNote"
               and (kind != "fast-h3" or entry["id"] >= 300)]
    left = min(entry["pos"][0] for entry in members) - 20
    top = min(entry["pos"][1] for entry in members) - 60
    right = max(entry["pos"][0] + entry["size"][0] for entry in members) + 20
    bottom = max(entry["pos"][1] + entry["size"][1] for entry in members) + 20
    groups = [{"title": f"AI {scale}x post-process", "bounding": [left, top, right-left, bottom-top],
               "color": "#4f8a73", "font_size": 24, "flags": {}}]
    return {"last_node_id": note_id, "last_link_id": len(links), "nodes": nodes, "links": links,
            "groups": groups, "config": {}, "extra": {"ds": {"scale": 0.5, "offset": [60, 450]},
                "ai_upscale": {"model_id": model_id, "native_scale": spec["scale"], "output_scale": scale,
                               "comfyui_revision": json.loads((ROOT / "scripts/fast_h3_lock.json").read_text())["comfyui"]["revision"]}},
            "version": 0.4}


def export(output_dir: Path, model_id: str = DEFAULT_MODEL, scale: int = 2, kind: str = "all") -> list[Path]:
    model_spec(model_id, scale)
    paths = []
    for selected in ("image", "video", "fast-h3") if kind == "all" else (kind,):
        graph = build_graph(selected, model_id=model_id, scale=scale)
        stem = f"fast_h3_l4_upscale_{scale}x" if selected == "fast-h3" else f"ai_upscale_{selected}_{scale}x"
        output_dir.mkdir(parents=True, exist_ok=True)
        for suffix, data in ((".api.json", graph), (".json", to_ui_workflow(graph, selected, model_id, scale))):
            path = output_dir / (stem + suffix)
            path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
            paths.append(path)
    return paths


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--kind", choices=("all", "image", "video", "fast-h3"), default="all")
    parser.add_argument("--model", default=DEFAULT_MODEL)
    parser.add_argument("--scale", type=int, choices=(2, 4), default=2)
    parser.add_argument("--output-dir", type=Path, default=ROOT / "workflows")
    args = parser.parse_args()
    for path in export(args.output_dir, args.model, args.scale, args.kind):
        print(path)


if __name__ == "__main__":
    main()
