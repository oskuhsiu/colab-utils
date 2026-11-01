"""Pinned inference adapters. Importing this module requires only the stdlib.

Wan API contract: diffusers v0.40.0, pipelines/wan. Wan dependencies are
staged by the caller. H3 executes the pinned setup recipe (including installation
on a new dependency signature); its installation marker is shared by the runner.
"""
from __future__ import annotations

from pathlib import Path
import math
import hashlib
import subprocess
import tempfile
import time


def _image(path):
    from PIL import Image
    with Image.open(path) as image:
        return image.convert("RGB")


def _video_frames(path, shot, *, mask=False, face=False):
    """Resample to the model clock and canvas; hold the last frame if short."""
    from PIL import Image
    width, height = (512, 512) if face else (shot["width"], shot["height"])
    scale = "neighbor" if mask else "lanczos"
    filters = (f"fps={shot['fps']},scale={width}:{height}:flags={scale},"
               f"setsar=1,tpad=stop_mode=clone:stop_duration={shot['model_frames'] / shot['fps']}")
    if mask:
        filters += ",format=gray"
    with tempfile.TemporaryDirectory(prefix="video-control-") as directory:
        subprocess.run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-nostdin",
                        "-i", str(path), "-an", "-vf", filters, "-frames:v",
                        str(shot["model_frames"]), str(Path(directory) / "%06d.png")],
                       check=True, capture_output=True)
        files = sorted(Path(directory).glob("*.png"))
        if len(files) != shot["model_frames"]:
            raise ValueError(f"Control video decoded {len(files)} frames; expected {shot['model_frames']}")
        frames = []
        for filename in files:
            with Image.open(filename) as image:
                # No inversion: upstream masks use black=condition, white=generate.
                frames.append(image.convert("L" if mask else "RGB"))
        return frames


def _validate_shot(shot, backend):
    for key in ("width", "height", "fps", "output_frames", "model_frames"):
        if not isinstance(shot.get(key), int) or isinstance(shot[key], bool) or shot[key] <= 0:
            raise ValueError(f"{key} must be a positive integer")
    if shot["output_frames"] > shot["model_frames"]:
        raise ValueError("output_frames cannot exceed model_frames")
    if not math.isclose(shot["output_frames"] / shot["fps"], shot["duration_seconds"], abs_tol=1e-6):
        raise ValueError("duration_seconds must equal output_frames / fps")
    if not shot.get("prompt", "").strip():
        raise ValueError("A nonempty prompt is required")
    if not isinstance(shot.get("seed"), int) or not 0 <= shot["seed"] < 2**32:
        raise ValueError("seed must be an integer in [0, 2**32)")
    alignment = 32 if backend in ("h3", "wan22-ti2v") else 16
    if shot["width"] % alignment or shot["height"] % alignment:
        raise ValueError(f"Canvas dimensions must be divisible by {alignment}")
    if backend == "h3":
        if shot["fps"] != 24 or shot["model_frames"] < 5 or (shot["model_frames"] - 5) % 17:
            raise ValueError("H3 requires 24 fps and 17n+5 model frames")
    elif (shot["model_frames"] - 1) % 4:
        raise ValueError("Wan requires 4n+1 model frames")
    native_fps = {"h3": 24, "wan22-ti2v": 24, "wan22-i2v-a14b": 16,
                  "wan21-vace": 16, "wan22-animate": 30}
    if shot["fps"] != native_fps[backend]:
        raise ValueError(f"{backend} requires {native_fps[backend]} fps")


def _check_inputs(inputs, allowed):
    roles = [key for key, value in inputs.items() if value]
    unsupported = set(roles) - set(allowed)
    if unsupported:
        raise ValueError(f"Unsupported input roles: {', '.join(sorted(unsupported))}")
    for role in roles:
        values = inputs[role] if role == "references" else [inputs[role]]
        for value in values:
            if not Path(value).is_file():
                raise FileNotFoundError(f"Missing {role}: {value}")
    return roles


def _validate_loras(settings, task):
    loras = settings.get("loras", [])
    if loras and settings["backend"] == "wan22-animate":
        raise ValueError("Wan Animate does not accept generic Wan LoRAs")
    if loras and settings["backend"] == "wan22-i2v-a14b":
        raise ValueError("A14B LoRAs require separately verified dual-denoiser mapping; custom LoRAs are disabled")
    for lora in loras:
        if not all(lora.get(key) for key in ("path", "kind", "base_model", "task")):
            raise ValueError("LoRA needs path, kind, base_model and task compatibility declarations")
        if lora["base_model"] != settings["model_id"] or lora["task"] != task:
            raise ValueError("LoRA base_model/task does not match the selected backend")
        if lora["kind"] not in ("identity", "style", "motion", "control"):
            raise ValueError("Local LoRA kind must be identity, style, motion or control; acceleration is preset-owned")
        path = Path(lora["path"])
        if not path.is_absolute() or not path.is_file():
            raise ValueError("LoRA path must be an existing staged absolute file")
        if not isinstance(lora.get("scale"), (int, float)) or not math.isfinite(lora["scale"]):
            raise ValueError("LoRA scale must be finite")
    return loras


def _result(settings, shot, roles, started, steps, **extra):
    return dict(video="video.mp4", backend=settings["backend"], model_id=settings["model_id"],
                revision=settings.get("revision"), steps=steps, seed=shot["seed"], input_roles=roles,
                generation_seconds=round(time.perf_counter() - started, 3), **extra)


class H3Backend:
    def __init__(self, settings, progress, install_state=None):
        self.settings = dict(settings)
        self.settings.setdefault("model_id", "MiniMaxAI/MiniMax-H3")
        task, preset = settings.get("task_mode", "fl2va"), settings.get("model_preset", "turbo8")
        if task not in ("fl2va", "ref2va") or preset not in ("original50", "turbo8", "turbo4"):
            raise ValueError("Unsupported H3 task_mode/model_preset")
        if task == "ref2va" and preset == "turbo4":
            raise ValueError("Ref2VA has no compatible turbo4 preset")
        if settings.get("precision", "nf4_pruned") not in ("bf16", "nf4_pruned"):
            raise ValueError("H3 precision must be bf16 or nf4_pruned")
        expected_steps = {"original50": 50, "turbo8": 8, "turbo4": 4}[preset]
        if settings.get("steps", expected_steps) != expected_steps:
            raise ValueError("H3 steps must match the selected preset")
        if settings.get("guidance_scale", 1.0) != 1.0:
            raise ValueError("The pinned H3 recipe requires guidance_scale=1")
        loras = _validate_loras(self.settings, task)
        namespace = {"__name__": "h3_video_setup", "H3_TASK_MODE": task, "H3_PRESET": preset,
                     "H3_PRECISION": settings.get("precision", "nf4_pruned")}
        setup = Path(__file__).with_name("h3_setup.py")
        namespace["__file__"] = str(setup)
        progress(phase="loading", backend="h3")
        source = setup.read_text()
        setup_key = hashlib.sha256(source.encode()).hexdigest()
        if install_state is not None and install_state.get("source_sha256") == setup_key:
            namespace["_INSTALL_SIGNATURE"] = install_state.get("signature")
        try:
            exec(compile(source, str(setup), "exec"), namespace)
        finally:
            # Installation can succeed even when subsequent model loading fails.
            if install_state is not None and namespace.get("_INSTALL_SIGNATURE"):
                install_state.update(source_sha256=setup_key, signature=namespace["_INSTALL_SIGNATURE"])
        self.namespace, self.pipe = namespace, namespace["pipe"]
        self.config = namespace["selected_config"]()
        if (self.config["task_mode"] != task or self.config["steps"] != expected_steps
                or self.config["precision"] != namespace["H3_PRECISION"]):
            raise ValueError("H3 setup did not honor requested task/preset")
        self.settings["revision"] = namespace["REVISIONS"][self.settings["model_id"]]
        if loras:
            namespace["configure_lora_layout"](self.pipe, self.config["precision"])
        for lora in loras:
            before = sum(len(getattr(module, "lora_A_weights", [])) for module in self.pipe.dit.modules())
            self.pipe.load_lora(self.pipe.dit, namespace["ModelConfig"](path=lora["path"]),
                                alpha=lora["scale"], hotload=True)
            after = sum(len(getattr(module, "lora_A_weights", [])) for module in self.pipe.dit.modules())
            if after <= before:
                raise ValueError("Custom H3 LoRA patched no modules; export/loader format is incompatible")

    def render(self, shot, inputs, output_dir, progress=lambda **kwargs: None):
        _validate_shot(shot, "h3")
        ref_mode = self.config["task_mode"] == "ref2va"
        roles = _check_inputs(inputs, ("references",) if ref_mode else ("first_frame", "last_frame"))
        kwargs = {}
        if ref_mode:
            paths = inputs.get("references", [])
            if not paths or len(paths) > 9:
                raise ValueError("H3 Ref2VA requires 1–9 reference images")
            kwargs = {"references": [{"type": "image", "image": _image(path)} for path in paths],
                      "ref_image_short_edge": 1024}
        else:
            pairs = [(role, index) for role, index in (("first_frame", 0), ("last_frame", -1)) if inputs.get(role)]
            if pairs:
                kwargs = {"keyframes": [_image(inputs[role]) for role, _ in pairs],
                          "keyframe_indices": [index for _, index in pairs]}
        output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)
        progress(phase="generating", backend="h3", shot_id=shot["id"])
        started = time.perf_counter()
        with self.namespace["torch"].inference_mode():
            video, audio = self.pipe(prompt=shot["prompt"], negative_prompt=shot.get("negative_prompt", " "),
                                     width=shot["width"], height=shot["height"], num_frames=shot["model_frames"],
                                     num_inference_steps=self.config["steps"], seed=shot["seed"], cfg_scale=1.0,
                                     flow_shift=self.config["video_shift"], audio_flow_shift=self.config["audio_shift"], **kwargs)
        self.namespace["torch"].cuda.synchronize()
        samples = round(shot["output_frames"] / shot["fps"] * 32000)
        if len(video) < shot["output_frames"] or audio is None or audio.shape[-1] < samples:
            raise ValueError("H3 returned insufficient video/audio for the requested duration")
        result = _result(self.settings, shot, roles, started, self.config["steps"],
                         task_mode=self.config["task_mode"], precision=self.config["precision"],
                         model_revisions=self.namespace["REVISIONS"], audio_generated=True)
        progress(phase="encoding", backend="h3", shot_id=shot["id"])
        self.namespace["write_video_audio"](video=video[:shot["output_frames"]], audio=audio[..., :samples],
                                           output_path=str(output_dir / "video.mp4"), fps=shot["fps"], audio_sample_rate=32000)
        return result


class WanBackend:
    def __init__(self, settings, progress):
        self.settings = dict(settings)
        for key in ("model_id", "revision"):
            if not settings.get(key):
                raise ValueError(f"Wan requires explicit {key}")
        if settings.get("offload", "model") not in ("model", "none"):
            raise ValueError("offload must be model or none")
        if settings["backend"] == "wan22-ti2v" and settings.get("mode", "t2v") not in ("t2v", "i2v"):
            raise ValueError("Wan5B mode must be t2v or i2v")
        if settings["backend"] == "wan22-i2v-a14b" and settings.get("mode") != "i2v":
            raise ValueError("Wan A14B requires explicit mode i2v")
        if settings["backend"] == "wan22-animate" and settings.get("mode") not in ("animate", "replace"):
            raise ValueError("Wan Animate requires explicit mode animate or replace")
        task = settings.get("mode", "t2v" if settings["backend"] == "wan22-ti2v" else "control")
        self.loras = _validate_loras(settings, task)
        import torch
        import diffusers
        if diffusers.__version__ != "0.40.0":
            raise RuntimeError("Wan adapters require diffusers==0.40.0")
        self.torch, self.diffusers = torch, diffusers
        progress(phase="loading", backend=settings["backend"])
        vae = diffusers.AutoencoderKLWan.from_pretrained(settings["model_id"], subfolder="vae",
                                                       revision=settings["revision"], torch_dtype=torch.float32)
        class_name = {"wan22-ti2v": "WanPipeline", "wan22-i2v-a14b": "WanImageToVideoPipeline", "wan21-vace": "WanVACEPipeline",
                      "wan22-animate": "WanAnimatePipeline"}[settings["backend"]]
        extra = {}
        if settings["backend"] == "wan22-ti2v" and settings.get("mode", "t2v") == "i2v":
            # TI2V-5B's model_index says WanPipeline and has no CLIP encoder.
            class_name = "WanImageToVideoPipeline"
            extra = dict(image_encoder=None, image_processor=None)
        self.pipe = getattr(diffusers, class_name).from_pretrained(
            settings["model_id"], revision=settings["revision"], vae=vae, torch_dtype=torch.bfloat16, **extra)
        if settings["backend"] == "wan22-i2v-a14b":
            # Load both experts and their boundary from the checkpoint model_index.
            if (self.pipe.transformer is None or self.pipe.transformer_2 is None
                    or self.pipe.config.boundary_ratio is None):
                raise ValueError("Wan A14B checkpoint must provide both denoisers and boundary_ratio")
        self._place(self.pipe)
        if settings.get("vae_tiling", True):
            vae.enable_tiling()
        for index, lora in enumerate(self.loras):
            self.pipe.load_lora_weights(lora["path"], adapter_name=f"local_{index}")
        if self.loras:
            self.pipe.set_adapters([f"local_{i}" for i in range(len(self.loras))],
                                   adapter_weights=[lora["scale"] for lora in self.loras])

    def _place(self, pipe):
        if self.settings.get("offload", "model") == "model":
            pipe.enable_model_cpu_offload()
        else:
            pipe.to("cuda")

    def render(self, shot, inputs, output_dir, progress=lambda **kwargs: None):
        backend = self.settings["backend"]
        _validate_shot(shot, backend)
        animate = backend == "wan22-animate"
        a14b = backend == "wan22-i2v-a14b"
        kwargs = dict(prompt=shot["prompt"], negative_prompt=shot.get("negative_prompt", ""),
                      width=shot["width"], height=shot["height"], num_frames=shot["model_frames"],
                      num_inference_steps=self.settings.get("steps", 40 if a14b else 20 if animate else 50),
                      guidance_scale=self.settings.get("guidance_scale", 3.5 if a14b else 1.0 if animate else 5.0),
                      generator=self.torch.Generator(device="cpu").manual_seed(shot["seed"]), output_type="pil")
        pipe = self.pipe
        if backend in ("wan22-ti2v", "wan22-i2v-a14b"):
            # Only first-frame conditioning is exposed by these adapters.
            # TI2V5B additionally ignores last_image with expand_timesteps=True.
            roles = _check_inputs(inputs, ("first_frame",))
            image_mode = self.settings.get("mode", "t2v") == "i2v"
            if image_mode != bool(inputs.get("first_frame")):
                raise ValueError("Wan mode must match the shot: i2v requires first_frame; t2v accepts no frames")
            if inputs.get("first_frame"):
                kwargs["image"] = _image(inputs["first_frame"])
        elif backend == "wan21-vace":
            roles = _check_inputs(inputs, ("references", "control_video", "mask_video"))
            if inputs.get("mask_video") and not inputs.get("control_video"):
                raise ValueError("VACE mask_video requires control_video")
            if inputs.get("references"):
                kwargs["reference_images"] = [_image(path) for path in inputs["references"]]
            if inputs.get("control_video"):
                kwargs["video"] = _video_frames(inputs["control_video"], shot)
            if inputs.get("mask_video"):
                kwargs["mask"] = _video_frames(inputs["mask_video"], shot, mask=True)
            kwargs["conditioning_scale"] = self.settings.get("conditioning_scale", 1.0)
        else:
            roles = _check_inputs(inputs, ("first_frame", "references", "pose_video", "face_video", "background_video", "mask_video"))
            mode = self.settings.get("mode")
            if mode not in ("animate", "replace"):
                raise ValueError("Wan Animate requires explicit mode animate or replace")
            references = inputs.get("references", [])
            if inputs.get("first_frame") and references:
                raise ValueError("Animate accepts one character image source: first_frame or references")
            character = inputs.get("first_frame") or (references[0] if len(references) == 1 else None)
            if not character or not inputs.get("pose_video") or not inputs.get("face_video"):
                raise ValueError("Wan Animate requires one character reference and preprocessed pose_video + face_video")
            if mode == "replace" and not (inputs.get("background_video") and inputs.get("mask_video")):
                raise ValueError("Replace mode requires background_video and mask_video")
            if mode == "animate" and (inputs.get("background_video") or inputs.get("mask_video")):
                raise ValueError("Background/mask inputs require replace mode")
            kwargs.pop("num_frames")
            kwargs.update(image=_image(character), mode=mode,
                          segment_frame_length=self.settings.get("segment_frame_length", 77))
            for role in ("pose_video", "face_video", "background_video", "mask_video"):
                if inputs.get(role):
                    kwargs[role] = _video_frames(inputs[role], shot, mask=role == "mask_video", face=role == "face_video")
        output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)
        def on_step(_pipe, step, _timestep, callback_kwargs):
            progress(phase="generating", backend=backend, shot_id=shot["id"], step=step + 1,
                     steps=kwargs["num_inference_steps"])
            return callback_kwargs
        kwargs["callback_on_step_end"] = on_step
        progress(phase="generating", backend=backend, shot_id=shot["id"])
        started = time.perf_counter()
        with self.torch.inference_mode():
            frames = pipe(**kwargs).frames[0]
        self.torch.cuda.synchronize()
        if len(frames) < shot["output_frames"]:
            raise ValueError("Wan returned fewer frames than requested")
        result = _result(self.settings, shot, roles, started, kwargs["num_inference_steps"],
                         precision="bf16", audio_generated=False)
        progress(phase="encoding", backend=backend, shot_id=shot["id"])
        from diffusers.utils import export_to_video
        export_to_video(frames[:shot["output_frames"]], str(output_dir / "video.mp4"), fps=shot["fps"])
        return result


def load_backend(settings: dict, progress=lambda **kwargs: None, *, install_state=None):
    """Load one reusable adapter after the caller installs/stages dependencies."""
    backend = settings.get("backend")
    if backend == "h3":
        return H3Backend(settings, progress, install_state=install_state)
    if backend in ("wan22-ti2v", "wan22-i2v-a14b", "wan21-vace", "wan22-animate"):
        return WanBackend(settings, progress)
    raise ValueError(f"Unsupported backend: {backend}")
