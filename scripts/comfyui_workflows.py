#!/usr/bin/env python3
"""Small native H3 starters for the optional ComfyUI workspace (no GPU imports)."""
from __future__ import annotations

import argparse
import json
import math
from pathlib import Path, PurePosixPath
import re
import uuid


PRESETS = ("h3-continuum", "h3-ref2va-vsa", "h3-omni-int8")
DEFAULT_PROMPT = (
    "integrated_multimodal_description: [Shot 1] A small red toy train rolls "
    "steadily across a wooden table. Static wide camera, soft daylight.\n"
    "overall_soundscape: Wheels rattle softly against the wood.\n"
    "non_diegetic_music: N/A."
)
REFERENCE_PROMPT = (
    "subject_definitions: <Subject 1> is the red toy train in <Picture 1>.\n"
    "summary: [reference generation] The referenced toy train rolls across a table.\n"
    "retention_analysis: <Subject 1> (appears in [Shot 1]): fully_preserved.\n"
    "detailed_description: [Shot 1] <Subject 1> from <Picture 1> rolls steadily "
    "across a wooden table. Static wide camera, soft daylight.\n"
    "overall_soundscape: Wheels rattle softly against the wood.\n"
    "non_diegetic_music: N/A."
)


def node(class_type, **inputs):
    return {"class_type": class_type, "inputs": inputs}


def validate_attention(graph):
    """Reject a second attention patch along a Ref2VA-VSA model wire.

    Other custom patch conflicts remain the node's responsibility at execution;
    importing an unrelated branch's attention patch is not itself a conflict.
    """
    for identity, item in graph.items():
        if not isinstance(item, dict):
            raise ValueError("API graph values must be node dictionaries")
        chain, visited, current = [], set(), identity
        while current in graph and current not in visited:
            visited.add(current)
            entry = graph[current]
            kind = entry.get("class_type", "")
            chain.append(kind)
            model = entry.get("inputs", {}).get("model")
            if not (isinstance(model, list) and len(model) == 2 and isinstance(model[0], str)):
                break
            current = model[0]
        if "Ref2VAVSAGatePatch" in chain:
            patches = [kind for kind in chain if kind == "Ref2VAVSAGatePatch"
                       or any(part in kind.lower() for part in ("attention", "vsapatch", "solattn"))]
            if len(patches) > 1:
                raise ValueError("Ref2VA-VSA cannot be stacked with another attention patch on the same model")
    return graph


def build_graph(preset, prompt=None, width=864, height=480, duration_seconds=5,
                seed=42, reference_image="reference.png", chunks=2, run_name="comfy_h3",
                ref_image_size=None):
    if preset not in PRESETS:
        raise ValueError(f"Unknown preset: {preset}")
    if any(type(value) is not int or value < 32 or value % 32 for value in (width, height)):
        raise ValueError("Dimensions must be positive multiples of 32")
    if width * height > 1344 * 768:
        raise ValueError("Starter canvas must not exceed 1344x768; use a custom API graph for other sizes")
    if type(seed) is not int or not 0 <= seed < 2**64:
        raise ValueError("Seed must be a uint64 integer")
    if type(duration_seconds) not in (int, float) or not math.isfinite(duration_seconds):
        raise ValueError("Duration must be finite")
    if type(chunks) is not int or not 1 <= chunks <= 16:
        raise ValueError("Chunks must be from 1 to 16")
    if not isinstance(run_name, str) or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.-]*", run_name):
        raise ValueError("Run name must be filename-safe")
    omni = preset == "h3-omni-int8"
    reference = preset in ("h3-ref2va-vsa", "h3-omni-int8")
    # Preserve the existing Ref2VA starter's sizing; Omni favors reference detail.
    if ref_image_size is None:
        ref_image_size = "max" if omni else "match"
    if ref_image_size not in ("match", "max"):
        raise ValueError("Reference image size must be match or max")
    if prompt is None or prompt == "":
        prompt = REFERENCE_PROMPT if reference else DEFAULT_PROMPT
    if not isinstance(prompt, str) or not prompt.strip():
        raise ValueError("Prompt must be nonempty text")
    if not (5 <= duration_seconds <= 15 if reference else 4 <= duration_seconds <= 30):
        raise ValueError("Duration must be 5–15 seconds for Ref2VA, or 4–30 seconds per Continuum chunk")
    if reference:
        if (not isinstance(reference_image, str) or not reference_image or "\\" in reference_image
                or PurePosixPath(reference_image).is_absolute() or ".." in PurePosixPath(reference_image).parts
                or PurePosixPath(reference_image).suffix.lower() not in (".png", ".jpg", ".jpeg", ".webp")):
            raise ValueError("Reference must be a relative ComfyUI input image filename")
        fields = ("subject_definitions", "summary", "retention_analysis", "detailed_description",
                  "overall_soundscape", "non_diegetic_music")
        pattern = r"\A\s*" + r"\s*".join(field + r":\s*(.+?)" for field in fields) + r"\s*\Z"
        match = re.fullmatch(pattern, prompt, flags=re.DOTALL)
        if not match or not all(value.strip() for value in match.groups()):
            raise ValueError("Ref2VA prompt requires all six nonempty fields in canonical order")
        if not match.group(2).lstrip().startswith("[reference generation]"):
            raise ValueError("Ref2VA summary must start with [reference generation]")
        tags = re.findall(r"<(Picture|Video|Audio)\s+(\d+)>", prompt, flags=re.IGNORECASE)
        if {(kind.lower(), int(number)) for kind, number in tags} != {("picture", 1)}:
            raise ValueError("This starter requires exactly the <Picture 1> reference")

    graph = {
        "1": node("UNETLoader", unet_name=("fasth3_omniref_8step_pruned_int8_convrot.safetensors" if omni
                                         else "minimax_h3_ref2va_pruned_int8_convrot.safetensors" if reference
                                         else "minimax_h3_fl2va_pruned_int8_convrot.safetensors"), weight_dtype="default"),
        "2": node("CLIPLoader", clip_name=("qwen3vl_32b_minimax_h3_int8_convrot.safetensors" if omni
                                         else "qwen3vl_32b_minimax_h3_nvfp4_awq.safetensors"), type="minimax", device="default"),
        "3": node("VAELoader", vae_name=("minimax_h3_video_vae_fp16.safetensors" if reference and not omni
                                       else "minimax_h3_video_vae_int8_convrot.safetensors")),
        "4": node("VAELoader", vae_name="minimax_h3_audio_vae_fp32.safetensors"),
        "5": node("KSamplerSelect", sampler_name="euler" if reference else "res_multistep"),
    }
    if reference:
        if not omni:
            graph.update({
                "6": node("LoraLoaderModelOnly", model=["1", 0],
                          lora_name="minimax_h3_ref2v_turbo_4step_v0.1_comfyui_bf16.safetensors", strength_model=1.0),
                "7": node("Ref2VAVSAGatePatch", model=["6", 0], gate_file="fasth3_vsa_gate.safetensors", sparsity=0.75),
            })
        graph.update({
            # Omni already contains its eight-step distillation and VSA gate weights.
            # Use native dense attention here; no Turbo LoRA or gate transplant.
            "8": node("MiniMaxH3SigmaShift", model=["1" if omni else "7", 0], shift_video=12.0, shift_audio=3.0),
            "9": node("BasicScheduler", model=["8", 0], scheduler="simple", steps=8 if omni else 4, denoise=1.0),
            "10": node("LoadImage", image=reference_image),
            "11": node("MiniMaxH3ReferenceToVideo", clip=["2", 0], vae=["3", 0], audio_vae=["4", 0],
                       prompt=prompt, width=width, height=height,
                       length=(max(5, round(duration_seconds * 24)) - 5 + 16) // 17 * 17 + 5,
                       ref_image_size=ref_image_size, **{"ref_images.ref_image_0": ["10", 0]}),
            "12": node("RandomNoise", noise_seed=seed),
            "13": node("BasicGuider", model=["8", 0], conditioning=["11", 0]),
            "14": node("SamplerCustomAdvanced", noise=["12", 0], guider=["13", 0], sampler=["5", 0],
                       sigmas=["9", 0], latent_image=["11", 1]),
            "15": node("VAEDecode", samples=["14", 0], vae=["3", 0]),
            "16": node("VAEDecodeAudio", samples=["14", 0], vae=["4", 0]),
        })
        images, audio = ["15", 0], ["16", 0]
    else:
        # Explicit shift agrees with Core's native 12/3 defaults; strict upstream
        # compatibility checking stays enabled. No optional accelerator patches.
        graph.update({
            "6": node("MiniMaxH3SigmaShift", model=["1", 0], shift_video=12.0, shift_audio=3.0),
            "7": node("BasicScheduler", model=["6", 0], scheduler="simple", steps=20, denoise=1.0),
            "8": node("H3ContinuumSamplerV39", model=["6", 0], clip=["2", 0], video_vae=["3", 0],
                      sampler=["5", 0], sigmas=["7", 0], sequence_prompt=prompt,
                      prompt_mode="Fixed", chunks=chunks, chunk_seconds=float(duration_seconds),
                      aspect="Landscape 16:9", preset="Draft — 0.30 MP", custom_mp=0.3,
                      continuity="Balanced — 22 frames", base_seed=seed, audio_continuity=True,
                      diagnostics="Detailed Report", reroll_from_chunk="Auto", reroll_nonce=0,
                      strict_compatibility=True, debug=False, show_preview=False,
                      run_storage="Save + Auto Resume", run_name=run_name,
                      reference_size="Match Output", project_id=str(uuid.uuid5(uuid.NAMESPACE_URL, "colab-utils:" + run_name)),
                      video_reference_size="Efficient - 0.4 MP", continuation_backend="Standard",
                      generation_mode="Full Run", review_action="Continue / Next", take_group=0,
                      take_revision_id="", take_action="Automatic", size_source="Manual", width=width, height=height),
            "9": node("H3DecodeCacheHelper", cache_mode="Auto", ram_budget_mb=256, disk_budget_gb=8, reset_token=0,
                      video_samples=["8", 0], audio_samples=["8", 1], video_vae=["3", 0], audio_vae=["4", 0]),
            "10": node("H3ContinuumAssembleSeamV35", images=["9", 0], audio=["9", 1], assembly_plan=["8", 2],
                       driving_audio=["8", 4], exact_total_duration=True, audio_seam="Auto", video_seam="Auto",
                       buffer_backend="Auto", diagnostics="Detailed Report"),
        })
        images, audio = ["10", 0], ["10", 1]
    graph["20"] = node("CreateVideo", images=images, audio=audio, fps=24.0)
    graph["21"] = node("SaveVideo", video=["20", 0], filename_prefix=f"video/{preset}/{run_name}",
                       **{"format": "mp4", "format.codec": "h264", "format.codec.encoding": "auto"})
    return validate_attention(graph)


def export(directory, presets=PRESETS):
    directory = Path(directory)
    directory.mkdir(parents=True, exist_ok=True)
    paths = []
    for preset in presets:
        path = directory / (preset + ".api.json")
        content = json.dumps(build_graph(preset), indent=2, ensure_ascii=False) + "\n"
        if path.exists() and path.read_text() != content:
            raise FileExistsError(f"Starter has local edits; keep it and export to another directory: {path}")
        path.write_text(content)
        paths.append(path)
    return paths


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    for path in export(args.output_dir):
        print(path)


if __name__ == "__main__":
    main()
