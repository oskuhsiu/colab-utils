"""Local ComfyUI nodes for the article's FastH3 schedule, LoRAs and receipts.

Learned VSA itself is supplied by the separately pinned public VSA node pack.
This file is installed as a custom-node package by fast_h3_runtime.py.
"""

import hashlib
import json
from pathlib import Path
import time


class ReferenceTrace:
    def __init__(self, *args, **kwargs):
        self.data = dict(*args, **kwargs)

    def __getitem__(self, key):
        return self.data[key]

    def __setitem__(self, key, value):
        self.data[key] = value

    def __deepcopy__(self, memo):
        # ModelPatcher copies options into sampler/executors; receipts must see
        # the trace produced by those executors, just like the public VSA runtime.
        return self


class FastH3SampleRequest:
    """Execute new sampling while retaining exact seed and cached conditioning."""
    @classmethod
    def INPUT_TYPES(cls):
        return {"required": {"noise": ("NOISE",), "request_id": ("STRING",)}}
    RETURN_TYPES = ("NOISE",)
    FUNCTION = "stamp"
    CATEGORY = "FastH3/sampling"

    def stamp(self, noise, request_id):
        if not isinstance(request_id, str) or not request_id:
            raise ValueError("A new sampling request requires an identity")
        return (noise,)


def _tensor_digest(tensor):
    import torch
    value = tensor.detach().contiguous().view(torch.uint8).cpu()
    return hashlib.sha256(value.numpy().tobytes()).hexdigest()


def _reference_sample_wrapper(executor, *args, **kwargs):
    trace = executor.class_obj.model_options["fast_h3_reference"]
    trace["forward_seconds"] = []
    trace["layouts"] = []
    started = time.perf_counter()
    try:
        return executor(*args, **kwargs)
    finally:
        trace["sampler_seconds"] = time.perf_counter() - started


def _reference_diffusion_wrapper(executor, x, timestep, context, transformer_options=None,
                                 minimax_payload=None, **kwargs):
    import torch
    options = transformer_options if transformer_options is not None else {}
    trace = options["fast_h3_reference_trace"]
    layout = (minimax_payload or {}).get("layout")
    segments = list(getattr(layout, "segments", ()))
    rows = sum(int(end) - int(start) for start, end, kind in segments if kind == "ref_img")
    if rows <= 0 or rows != trace["expected_ref_image_tokens"]:
        raise RuntimeError("Reference latent rows did not reach the H3 diffusion-model input")
    torch.cuda.synchronize()
    started = time.perf_counter()
    result = executor(x, timestep, context, options, minimax_payload=minimax_payload, **kwargs)
    torch.cuda.synchronize()
    trace["forward_seconds"].append(time.perf_counter() - started)
    trace["layouts"].append({"ref_image_tokens": rows,
                             "segments": [[int(a), int(b), kind] for a, b, kind in segments]})
    return result


class FastH3ExperimentalReference:
    """Native full Ref2VA conditioning on the unchanged T2VA student: OOD."""

    @classmethod
    def INPUT_TYPES(cls):
        return {"required": {
            "model": ("MODEL",), "clip": ("CLIP",), "vae": ("VAE",),
            "prompt": ("STRING", {"multiline": True}),
            "width": ("INT", {"default": 864, "min": 32, "step": 32}),
            "height": ("INT", {"default": 480, "min": 32, "step": 32}),
            "length": ("INT", {"default": 124, "min": 5, "step": 17}),
            "reference_1": ("IMAGE",),
        }, "optional": {"reference_2": ("IMAGE",), "reference_3": ("IMAGE",)}}

    RETURN_TYPES = ("MODEL", "CONDITIONING", "LATENT")
    FUNCTION = "condition"
    CATEGORY = "FastH3/experimental"

    def condition(self, model, clip, vae, prompt, width, height, length,
                  reference_1, reference_2=None, reference_3=None):
        import comfy.patcher_extension
        from comfy_extras.nodes_minimax_h3 import MiniMaxH3ReferenceToVideo
        if reference_3 is not None and reference_2 is None:
            raise ValueError("Reference images must be consecutive")
        images = [image for image in (reference_1, reference_2, reference_3) if image is not None]
        if not images or vae is None:
            raise ValueError("Full Ref2VA requires both an image and video VAE")
        native = MiniMaxH3ReferenceToVideo.execute(
            clip=clip, vae=vae, prompt=prompt, width=width, height=height, length=length,
            ref_image_size="match", ref_images={f"ref_image_{i + 1}": image for i, image in enumerate(images)})
        conditioning, latent = native.result
        blocks = conditioning[0][1].get("minimax_refs", [])
        if len(blocks) != len(images) or any(b.get("kind") != "image" or b.get("latent") is None for b in blocks):
            raise RuntimeError("Native reference conditioning omitted the image VAE latents")
        trace = ReferenceTrace({
            "mode": "experimental_ref2va_ood", "supported_by_distillation": False,
            "native_conditioner": "MiniMaxH3ReferenceToVideo", "reference_count": len(images),
            "ref_image_size": "match", "forward_seconds": [], "layouts": [],
            "sources": [{"picture": i + 1, "rgb_shape": list(image.shape), "rgb_tensor_sha256": _tensor_digest(image)}
                        for i, image in enumerate(images)],
            "encoded": [{"picture": i + 1, "latent_shape": list(b["latent"].shape),
                         "latent_sha256": _tensor_digest(b["latent"])} for i, b in enumerate(blocks)],
            "expected_ref_image_tokens": sum((b["latent_h"] // 2) * (b["latent_w"] // 2) for b in blocks),
        })
        result = model.clone()
        result.model_options = dict(result.model_options)
        result.model_options["fast_h3_reference"] = trace
        options = dict(result.model_options.get("transformer_options", {}))
        options["fast_h3_reference_trace"] = trace
        result.model_options["transformer_options"] = options
        result.add_wrapper_with_key(comfy.patcher_extension.WrappersMP.OUTER_SAMPLE,
                                    "fast_h3_reference_trace", _reference_sample_wrapper)
        result.add_wrapper_with_key(comfy.patcher_extension.WrappersMP.DIFFUSION_MODEL,
                                    "fast_h3_reference_trace", _reference_diffusion_wrapper)
        return result, conditioning, latent


class FastH3ExactSigmas:
    @classmethod
    def INPUT_TYPES(cls):
        return {"required": {"model": ("MODEL",)}}

    RETURN_TYPES = ("SIGMAS", "STRING")
    RETURN_NAMES = ("sigmas", "schedule")
    FUNCTION = "schedule"
    CATEGORY = "FastH3/sampling"

    def schedule(self, model):
        import torch
        sampling = model.get_model_object("model_sampling")
        if (float(sampling.shift), float(sampling.audio_shift)) != (12.0, 3.0):
            raise ValueError("FastH3 requires MiniMaxH3SigmaShift video=12, audio=3")
        timesteps = [999, 749, 500, 250]
        sigmas = sampling.sigma(torch.tensor(timesteps, dtype=torch.float32))
        sigmas = torch.cat((sigmas, sigmas.new_zeros(1)))
        report = {"timesteps": timesteps, "sigmas": sigmas.tolist(),
                  "video_shift": 12.0, "audio_shift": 3.0, "forwards": 4}
        return sigmas, json.dumps(report)


class FastH3CheckedLoraLoader:
    @classmethod
    def INPUT_TYPES(cls):
        import folder_paths
        return {"required": {
            "model": ("MODEL",),
            "lora_name": (folder_paths.get_filename_list("loras"),),
            "strength_model": ("FLOAT", {"default": 1.0, "min": -2.0, "max": 2.0, "step": 0.05}),
        }}

    RETURN_TYPES = ("MODEL",)
    FUNCTION = "load"
    CATEGORY = "FastH3/LoRA"

    def load(self, model, lora_name, strength_model):
        import comfy.lora
        import comfy.utils
        import folder_paths
        # FastH3 already contains the speed distillation. These known base-model
        # speed adapters do not establish compatibility with this student.
        name = lora_name.lower()
        if any(word in name for word in ("turbo", "flashgen", "pdmd", "dmad")):
            raise ValueError("Use a FastH3-compatible content/style LoRA; do not stack a base H3 speed adapter")
        result = model.clone()
        path = Path(folder_paths.get_full_path_or_raise("loras", lora_name))
        digest = hashlib.sha256()
        with path.open("rb") as stream:
            for chunk in iter(lambda: stream.read(8 * 1024 * 1024), b""):
                digest.update(chunk)
        matched = 0
        if strength_model != 0:
            state = comfy.utils.load_torch_file(str(path), safe_load=True)
            keys = comfy.lora.model_lora_keys_unet(model.model, {})
            patches = comfy.lora.load_lora(state, keys)
            if not patches:
                raise ValueError("LoRA has no targets recognized by the FastH3 ComfyUI model")
            applied = result.add_patches(patches, strength_model)
            if len(applied) != len(patches):
                raise ValueError(f"LoRA targets only partially mapped: {len(applied)}/{len(patches)}")
            matched = len(applied)
        options = dict(result.model_options)
        entries = list(options.get("fast_h3_loras", []))
        entries.append({"name": lora_name, "sha256": digest.hexdigest(),
                        "strength_model": float(strength_model), "mapped_targets": matched})
        options["fast_h3_loras"] = entries
        result.model_options = options
        return (result,)


class FastH3ReportAndTrim:
    @classmethod
    def INPUT_TYPES(cls):
        return {"required": {
            "model": ("MODEL",), "sigmas": ("SIGMAS",),
            "images": ("IMAGE",), "audio": ("AUDIO",),
            "duration_seconds": ("FLOAT", {"default": 5.0, "min": 5.0, "max": 15.0, "step": 1.0}),
        }}

    RETURN_TYPES = ("IMAGE", "AUDIO", "STRING")
    RETURN_NAMES = ("images", "audio", "report")
    FUNCTION = "report"
    CATEGORY = "FastH3/output"
    OUTPUT_NODE = True

    def report(self, model, sigmas, images, audio, duration_seconds):
        import torch
        frames = round(duration_seconds * 24)
        if images.shape[0] < frames:
            raise ValueError("FastH3 decoded fewer video frames than the requested duration")
        waveform = audio["waveform"]
        rate = int(audio["sample_rate"])
        samples = round(duration_seconds * rate)
        if rate != 32000 or waveform.shape[1] != 2 or waveform.shape[-1] < samples:
            raise ValueError("FastH3 requires complete 32 kHz stereo audio")
        candidates = [value for value in model.model_options.get("transformer_options", {}).values()
                      if hasattr(value, "last_summary") and hasattr(value, "kernel_calls")]
        if len(candidates) != 1 or candidates[0].last_summary is None:
            raise RuntimeError("The learned VSA runtime did not produce an execution summary")
        vsa = dict(candidates[0].last_summary)
        if (vsa["kernel_calls"] != 200 or vsa["dense_fallbacks"] != 0 or vsa["errors"] != 0):
            raise RuntimeError(f"Expected 50 blocks × 4 native VSA forwards with zero fallbacks: {vsa}")
        if len(sigmas) != 5 or float(sigmas[-1]) != 0:
            raise ValueError("FastH3 must execute the four trained forwards plus the zero endpoint")
        receipt = {
            "backend": "comfyui_fasth3", "mode": "t2va", "vsa": vsa,
            "timesteps": [999, 749, 500, 250], "sigmas": sigmas.tolist(),
            "steps": 4, "sampler": "euler", "video_shift": 12.0, "audio_shift": 3.0,
            "width": int(images.shape[2]), "height": int(images.shape[1]),
            "model_frames": int(images.shape[0]), "output_frames": frames,
            "fps": 24, "duration_seconds": duration_seconds,
            "audio_sample_rate": rate, "audio_channels": 2,
            "loras": model.model_options.get("fast_h3_loras", []),
            "peak_torch_allocated_gib": round(torch.cuda.max_memory_allocated() / 2**30, 3),
            "peak_torch_reserved_gib": round(torch.cuda.max_memory_reserved() / 2**30, 3),
        }
        reference = model.model_options.get("fast_h3_reference")
        if reference is not None:
            if len(reference["forward_seconds"]) != 4 or len(reference["layouts"]) != 4:
                raise RuntimeError("Experimental Ref2VA did not execute four traced reference-conditioned forwards")
            receipt.update(mode="experimental_ref2va_ood", reference=json.loads(json.dumps(reference.data)),
                           supported_by_distillation=False)
        trimmed_audio = dict(audio, waveform=waveform[..., :samples])
        return {"result": (images[:frames], trimmed_audio, json.dumps(receipt)),
                "ui": {"fast_h3": [receipt]}}


NODE_CLASS_MAPPINGS = {
    "FastH3SampleRequest": FastH3SampleRequest,
    "FastH3ExperimentalReference": FastH3ExperimentalReference,
    "FastH3ExactSigmas": FastH3ExactSigmas,
    "FastH3CheckedLoraLoader": FastH3CheckedLoraLoader,
    "FastH3ReportAndTrim": FastH3ReportAndTrim,
}

NODE_DISPLAY_NAME_MAPPINGS = {
    "FastH3SampleRequest": "FastH3 新推論請求（保留 seed）",
    "FastH3ExperimentalReference": "FastH3 人物參照（未蒸餾／實驗）",
    "FastH3ExactSigmas": "FastH3 精確時間步 [999,749,500,250]",
    "FastH3CheckedLoraLoader": "FastH3 相容 LoRA 載入",
    "FastH3ReportAndTrim": "FastH3 VSA 執行紀錄與影音裁切",
}
