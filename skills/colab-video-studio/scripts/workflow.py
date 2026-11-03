"""Immutable shot jobs and evidence-bound reviews. Python standard library only."""
from __future__ import annotations

from contextlib import contextmanager
import copy
import hashlib
import json
import math
import re
import shutil
import uuid
from datetime import datetime, timezone
from pathlib import Path


SCRIPT_DIR = Path(__file__).resolve().parent
MODELS = {
    "h3": ("MiniMaxAI/MiniMax-H3", "42ed227ee7df40d41602854ae760620d6eb651fe", 24),
    "wan22-ti2v": ("Wan-AI/Wan2.2-TI2V-5B-Diffusers", "b8fff7315c768468a5333511427288870b2e9635", 24),
    "wan22-i2v-a14b": ("Wan-AI/Wan2.2-I2V-A14B-Diffusers", "596658fd9ca6b7b71d5057529bbf319ecbc61d74", 16),
    "wan21-vace": ("Wan-AI/Wan2.1-VACE-1.3B-diffusers", "ec4d2cb062b548996b179d493fdd05340de702a1", 16),
    "wan22-animate": ("Wan-AI/Wan2.2-Animate-14B-Diffusers", "6f4df10861c758af86ac3c979aacc1bf5c03eff0", 30),
}
ROLES = {"first_frame", "last_frame", "references", "control_video", "mask_video",
         "pose_video", "face_video", "background_video", "audio_track"}
KINDS = {"provided-person", "photoreal", "stylized"}


def read_json(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def write_json(path, data):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + "." + uuid.uuid4().hex + ".tmp")
    temporary.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    temporary.replace(path)


def digest(data):
    return hashlib.sha256(json.dumps(data, sort_keys=True, ensure_ascii=False,
                                     separators=(",", ":")).encode()).hexdigest()


def sha256(path):
    hasher = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            hasher.update(block)
    return hasher.hexdigest()


def identifier(value):
    if not isinstance(value, str) or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_-]{0,63}", value):
        raise ValueError(f"Invalid identifier: {value!r}")
    return value


def local_path(root, relative):
    if not isinstance(relative, str) or not relative or Path(relative).is_absolute():
        raise ValueError("Asset/output paths must be nonempty project-relative paths")
    path = (Path(root) / relative).resolve()
    if not path.is_relative_to(Path(root).resolve()):
        raise ValueError(f"Path leaves project: {relative}")
    return path


def settings_for(plan, shot):
    settings = dict(plan.get("settings", {}), **shot.get("settings", {}))
    backend = settings.get("backend")
    if backend not in MODELS:
        raise ValueError(f"Unsupported backend: {backend}")
    model, revision, fps = MODELS[backend]
    settings.setdefault("model_id", model)
    settings.setdefault("revision", revision)
    if settings["model_id"] != model or not re.fullmatch(r"[a-f0-9]{40}", settings["revision"]):
        raise ValueError("Choose an implemented model and an immutable model revision")
    settings.setdefault("steps", 20 if backend == "wan22-animate" else 40 if backend == "wan22-i2v-a14b" else 50)
    settings.setdefault("guidance_scale", 1.0 if backend in ("h3", "wan22-animate") else 3.5 if backend == "wan22-i2v-a14b" else 5.0)
    settings.setdefault("offload", "model")
    settings.setdefault("loras", [])
    if not isinstance(settings["steps"], int) or not 1 <= settings["steps"] <= 100:
        raise ValueError("steps must be an integer in 1..100")
    if settings["offload"] not in ("model", "none"):
        raise ValueError("offload must be model or none")
    for key in ("guidance_scale", "conditioning_scale"):
        if key in settings and (isinstance(settings[key],bool) or not isinstance(settings[key],(int,float))
                                or not math.isfinite(settings[key]) or settings[key] < 0):
            raise ValueError(f"{key} must be finite and nonnegative")
    if backend == "h3":
        if settings["guidance_scale"] != 1.0:
            raise ValueError("Pinned H3 CFG-distilled pipeline requires guidance_scale=1")
        settings.setdefault("task_mode", "fl2va")
        settings.setdefault("model_preset", "turbo8")
        settings.setdefault("precision", "bf16")
        if settings["task_mode"] not in ("fl2va", "ref2va"):
            raise ValueError("H3 task_mode must be fl2va or ref2va")
        if settings["model_preset"] not in ("original50", "turbo8", "turbo4"):
            raise ValueError("Unsupported H3 preset")
        if settings["precision"] not in ("bf16", "nf4_pruned"):
            raise ValueError("Implemented H3 precision: bf16 or nf4_pruned")
        if settings["task_mode"] == "ref2va" and settings["model_preset"] == "turbo4":
            raise ValueError("Ref2VA Turbo4 is not integrated in this setup")
        settings["steps"] = {"original50": 50, "turbo8": 8, "turbo4": 4}[settings["model_preset"]]
    if backend == "wan22-animate" and settings["loras"]:
        raise ValueError("Generic Wan LoRAs are not supported on Wan-Animate")
    if backend == "wan22-i2v-a14b" and settings["loras"]:
        raise ValueError("Custom dual-denoiser LoRA mapping has not been integrated on A14B")
    return settings, fps


def check_h3_prompt(prompt, settings, inputs):
    ref = settings["task_mode"] == "ref2va"
    fields = (["subject_definitions", "summary", "retention_analysis", "detailed_description",
               "overall_soundscape", "non_diegetic_music"] if ref else
              ["integrated_multimodal_description", "overall_soundscape", "non_diegetic_music"])
    positions = [prompt.find(name+":") for name in fields]
    if any(n < 0 for n in positions) or positions != sorted(positions) or len(set(positions)) != len(fields):
        raise ValueError("H3 final prompt must use the documented ordered fields for this mode")
    if "[Shot 1]" not in prompt:
        raise ValueError("H3 final prompt needs an explicit [Shot 1]")
    if ref and "[reference generation]" not in prompt[positions[1]:positions[2]]:
        raise ValueError("Ref2VA summary needs its actual reference-generation task tag")
    pictures = {int(n) for n in re.findall(r"<Picture\s+(\d+)>", prompt)}
    count = len(inputs.get("references", [])) if ref else len(set(inputs) & {"first_frame", "last_frame"})
    if any(n < 1 or n > count for n in pictures):
        raise ValueError("H3 prompt refers to a picture not actually supplied")
    if not ref and count and positions[0] == 0:
        raise ValueError("H3 keyframe tasks need the official alignment instruction before the three fields")
    # Language dialogue belongs on the timeline, not the environmental sound field.
    sound = prompt[positions[-2]:positions[-1]]
    if "<d>" in sound:
        raise ValueError("Put H3 dialogue on the shot timeline, not in overall_soundscape")


def compile_job(project, shot_id):
    """Reject unsupported conditioning before any runtime is allocated."""
    project = Path(project).resolve()
    plan = read_json(project / "plan.json")
    if plan.get("schema_version") != 1 or plan.get("request", {}).get("kind") not in KINDS:
        raise ValueError("schema_version=1 and a supported request.kind are required")
    identifier(plan["project_id"])
    if not plan["request"].get("text", "").strip():
        raise ValueError("Keep the user's original request in request.text")
    budget = plan.get("budget", {})
    if any(isinstance(budget.get(k), bool) or not isinstance(budget.get(k), int) or budget[k] < 1
           for k in ("max_total_attempts", "max_attempts_per_shot")):
        raise ValueError("Set positive integer per-project and per-shot attempt budgets")
    delivery = plan.get("delivery", {})
    if any(not isinstance(delivery.get(k), int) or delivery[k] < 128 or delivery[k] % 2
           for k in ("width", "height")) or delivery.get("fps", 24) not in (16,24,30):
        raise ValueError("Delivery needs even dimensions and fps 16,24 or30")
    shots = plan.get("shots", [])
    ids = [identifier(item["id"]) for item in shots]
    if len(ids) != len(set(ids)) or shot_id not in ids:
        raise ValueError("Shot identifiers must be unique; requested shot must exist")
    shot = dict(shots[ids.index(shot_id)])
    if "audio_timeline" in shot:
        raise ValueError("audio_timeline is compiler-owned; source plans must use a validated audio_artifact and dialogue_timing")
    settings, fps = settings_for(plan, shot)
    from reference_resolver import resolve_shot
    shot = resolve_shot(plan, shot, settings)
    audio_asset = plan.get("assets", {}).get(shot.get("inputs", {}).get("audio_track"), {})
    if audio_asset.get("audio_artifact") and "dialogue_timing" not in shot:
        raise ValueError("An imported audio artifact requires dialogue_timing to check current text/speaker/voice dependencies")
    duration = shot.get("duration_seconds")
    if "dialogue_timing" in shot:
        from dialogue_timing import H3_CONSTRAINTS, action_prompt, pacing_prompt, plan_timing
        if not isinstance(shot["dialogue_timing"], dict):
            raise ValueError("dialogue_timing must be an object")
        timing_spec = dict(shot["dialogue_timing"])
        if duration not in (None, "auto"):
            if "clip_seconds" in timing_spec and timing_spec["clip_seconds"] != duration:
                raise ValueError("Shot duration and dialogue clip_seconds conflict")
            timing_spec["clip_seconds"] = duration
        constraints = H3_CONSTRAINTS if settings["backend"] == "h3" else dict(
            min_seconds=1, max_seconds=15, step_seconds=1/fps, fps=fps, frame_step=4, frame_offset=1)
        has_speech = bool(timing_spec.get("utterances"))
        if shot.get("audio") == "separate":
            from audio_artifacts import bind_timing
            asset_id = shot.get("inputs", {}).get("audio_track")
            if not isinstance(asset_id, str) or not plan.get("assets", {}).get(asset_id, {}).get("audio_artifact"):
                raise ValueError("Separate dialogue_timing requires an audio_track with an imported audio_artifact")
            timing_spec, timeline = bind_timing(project, plan, asset_id, timing_spec)
            timing = plan_timing(timing_spec, constraints=constraints)
            for line in timing["utterances"]:
                for key in ("voice_mode", "delivery", "rate_multiplier"):
                    line.pop(key, None)
                line["basis"] = "Supplied utterance boundaries within measured PCM WAV; not detected speech"
            timing["limitations"] = ("Recorded audio timing; no voice or mouth instructions were compiled. "
                                     "Action windows are prompt intent only. Review the actual sound and picture.")
            timeline["duration_seconds"] = timing["requested_duration_seconds"]
            shot["audio_timeline"] = timeline
            shot["prompt"] = action_prompt(shot["prompt"], timing, native_h3=settings["backend"] == "h3")
        else:
            if has_speech and (settings["backend"] != "h3" or shot.get("audio") != "native"):
                raise ValueError("Compiled dialogue_timing requires native H3 or a separate imported audio artifact")
            timing = plan_timing(timing_spec, constraints=constraints)
            shot["prompt"] = (pacing_prompt(shot["prompt"], timing) if has_speech else
                              action_prompt(shot["prompt"], timing, native_h3=settings["backend"] == "h3"))
        duration = timing["requested_duration_seconds"]
        shot.update(duration_seconds=duration, dialogue_timing_result=timing)
    if isinstance(duration, bool) or not isinstance(duration, (int, float)) or not math.isfinite(duration) or not 1 <= duration <= 15:
        raise ValueError("duration_seconds must be finite and in 1..15")
    if settings["backend"] == "h3" and (int(duration) != duration or duration < 5):
        raise ValueError("This H3 wrapper requires integer 5..15 seconds")
    if abs(duration * fps - round(duration * fps)) > 1e-6:
        raise ValueError("Choose a duration with an integer native frame count")
    width, height = shot.get("width"), shot.get("height")
    grid = 32 if settings["backend"] in ("h3", "wan22-ti2v") else 16
    if any(isinstance(x, bool) or not isinstance(x, int) or x < 128 or x > 2048 or x % grid for x in (width, height)):
        raise ValueError(f"Shot width/height must be 128..2048, divisible by {grid}")
    if not isinstance(shot.get("seed"), int) or not 0 <= shot["seed"] < 2**32:
        raise ValueError("Specify an integer seed in 0..2^32-1")
    if not isinstance(shot.get("prompt"), str) or not shot["prompt"].strip():
        raise ValueError("A final model-specific prompt is required")
    for field in ("start_state", "end_state"):
        if not isinstance(shot.get(field), dict) or not shot[field]:
            raise ValueError(f"Record {field} for each shot")
    transition = shot.get("transition", "cut")
    if transition not in ("cut", "continuous", "intentional-change"):
        raise ValueError("Unknown transition")
    if ids.index(shot_id) and transition == "continuous":
        previous = shots[ids.index(shot_id) - 1]
        if previous.get("end_state") != shot["start_state"]:
            raise ValueError("Continuous shots have contradictory planned boundary states")
    criteria = shot.get("criteria", [])
    criterion_ids = [identifier(c["id"]) for c in criteria]
    if not criteria or len(criterion_ids) != len(set(criterion_ids)):
        raise ValueError("Each shot needs unique observable acceptance criteria")
    if any(not c.get("requirement", "").strip() for c in criteria):
        raise ValueError("Criteria must describe observable requirements")
    required_kinds = {"action", "framing", "style", "artifacts", "audio"}
    if shot.get("characters"):
        required_kinds |= {"identity", "wardrobe"}
    if not required_kinds.issubset({c.get("kind") for c in criteria}):
        raise ValueError(f"Missing criterion kinds: {sorted(required_kinds - {c.get('kind') for c in criteria})}")
    windows = shot.get("qa", {}).get("event_windows", [])
    for window in windows:
        start, end = window["start"], window["end"]
        if window["criterion"] not in criterion_ids or not 0 <= start < end <= duration:
            raise ValueError("Event windows must belong to a criterion and lie within the shot")
        if window.get("fps", 8) < 2 or window.get("fps", 8) > fps:
            raise ValueError("Event sampling rate must lie in 2..native fps")
    for region in shot.get("qa", {}).get("regions", []):
        identifier(region["id"])
        x,y,w,h = region["box"]
        if any(not isinstance(v, int) for v in (x,y,w,h)) or x < 0 or y < 0 or w < 16 or h < 16 or x+w > width or y+h > height:
            raise ValueError("Invalid source-pixel inspection region")
    action_ids = {c["id"] for c in criteria if c.get("kind") == "action"}
    if not action_ids.issubset({w["criterion"] for w in windows}):
        raise ValueError("Every action criterion needs a dense temporal inspection window")

    assets = plan.get("assets", {})
    inputs = shot.get("inputs", {})
    if not set(inputs).issubset(ROLES) or any(value in (None, "", []) for value in inputs.values()):
        raise ValueError("Use supported input roles; omit empty roles")
    selected = {}

    def asset(asset_id, ancestry=()):
        identifier(asset_id)
        if asset_id in ancestry:
            raise ValueError("Asset lineage contains a cycle")
        if asset_id in selected:
            return
        value = dict(assets[asset_id])
        if value.get("role") not in ("identity", "keyframe", "scene", "prop", "style", "control", "pose", "face", "mask", "audio", "video", "wardrobe"):
            raise ValueError(f"Unsupported asset role for {asset_id}")
        path = local_path(project, value["path"])
        if not path.is_file() or value.get("status") != "ready":
            raise ValueError(f"Asset {asset_id} is missing or has not passed preparation review")
        parents = value.get("derived_from", [])
        for parent in parents:
            asset(parent, (*ancestry, asset_id))
        selected[asset_id] = dict(value, sha256=sha256(path), bytes=path.stat().st_size)

    for role, values in inputs.items():
        if role == "references":
            if not isinstance(values, list) or not values:
                raise ValueError("references must be an ordered list of asset IDs")
        elif not isinstance(values, str):
            raise ValueError(f"{role} must name one asset ID")
        for name in values if isinstance(values, list) else [values]:
            asset(name)
            suffix = Path(assets[name]["path"]).suffix.lower()
            image_roles = {"first_frame", "last_frame", "references"}
            if role in image_roles and suffix not in (".png", ".jpg", ".jpeg", ".webp"):
                raise ValueError(f"{role} requires an actual image asset")
            if role.endswith("video") and suffix not in (".mp4", ".mov", ".mkv", ".webm", ".avi"):
                raise ValueError(f"{role} requires an actual video asset")
            expected_role = {"pose_video":"pose", "face_video":"face", "mask_video":"mask", "audio_track":"audio"}.get(role)
            if expected_role and assets[name]["role"] != expected_role:
                raise ValueError(f"{role} needs an asset explicitly prepared for role {expected_role}")
            if role in ("first_frame","last_frame") and assets[name]["role"] == "keyframe" and assets[name].get("source") == "generated":
                review = assets[name].get("preparation_review", {})
                if any(review.get(k) != "pass" for k in ("identity","wardrobe","framing")):
                    raise ValueError("Generated keyframe needs original-identity/wardrobe/framing preparation review")
    characters = {c["id"]: c for c in plan.get("characters", [])}
    char_specs = []
    for char_id in shot.get("characters", []):
        char = characters[char_id]
        origins = char.get("identity_assets", [])
        if not origins:
            raise ValueError(f"Character {char_id} needs an immutable identity baseline")
        for name in origins:
            asset(name)
            if assets[name].get("source") != "original":
                raise ValueError("Identity baselines cannot be earlier rendered video frames")
        from reference_resolver import generation_character
        char_specs.append(generation_character(char))
        # At least one actual input must retain lineage to this character's baseline.
        def descends(name):
            return name in origins or any(descends(p) for p in assets[name].get("derived_from", []))
        actual = [name for role,value in inputs.items() if role in ("first_frame","last_frame","references")
                  for name in (value if isinstance(value, list) else [value])]
        trained_identity = any(adapter.get("kind") == "identity" and adapter.get("character_id") == char_id
                               and set(origins) & set(adapter.get("identity_assets",[])) for adapter in settings["loras"])
        if not any(descends(name) for name in actual) and not trained_identity:
            raise ValueError(f"No actual model input links to character {char_id}'s identity baseline")
    if "audio_timeline" in shot:
        timeline = shot["audio_timeline"]
        audio = selected.get(inputs.get("audio_track"), {})
        if (timeline["asset_id"] != inputs.get("audio_track")
                or timeline["audio"]["sha256"] != audio.get("sha256")
                or timeline["audio"]["path"] != audio.get("path")):
            raise ValueError("Audio changed between artifact validation and input snapshot; reload/reimport before continuing")
    backend = settings["backend"]
    roles = set(inputs) - {"audio_track"}
    allowed = {
        "h3": {"references"} if settings.get("task_mode") == "ref2va" else {"first_frame", "last_frame"},
        "wan22-ti2v": {"first_frame"},
        "wan22-i2v-a14b": {"first_frame"},
        "wan21-vace": {"references", "control_video", "mask_video"},
        "wan22-animate": {"first_frame", "pose_video", "face_video", "background_video", "mask_video"},
    }[backend]
    if not roles.issubset(allowed):
        raise ValueError(f"{backend} cannot combine input roles {sorted(roles - allowed)}")
    if backend == "h3" and settings["task_mode"] == "ref2va" and "references" not in roles:
        raise ValueError("H3 Ref2VA requires actual references")
    if backend == "h3" and settings["revision"] != MODELS["h3"][1]:
        raise ValueError("H3 setup is pinned to its declared revision")
    if backend == "h3" and settings["task_mode"] == "ref2va" and (
        len(inputs["references"]) > 9 or any(Path(assets[n]["path"]).suffix.lower() not in (".png",".jpg",".jpeg",".webp") for n in inputs["references"])):
        raise ValueError("This H3 adapter supports 1..9 image references; reference videos are not implemented")
    if backend == "wan21-vace" and "control_video" not in roles:
        raise ValueError("This VACE route requires a control video; use an anchored backend otherwise")
    if backend == "wan22-i2v-a14b" and "first_frame" not in roles:
        raise ValueError("A14B I2V requires an actual first_frame")
    if backend == "wan22-animate" and not {"first_frame", "pose_video", "face_video"}.issubset(roles):
        raise ValueError("Animate needs character image plus PREPROCESSED pose and face videos")
    if "mask_video" in roles and backend == "wan21-vace" and "control_video" not in roles:
        raise ValueError("A VACE mask requires a control video")
    if backend == "wan22-animate" and ("background_video" in roles) != ("mask_video" in roles):
        raise ValueError("Animate replacement needs both background and mask")
    if shot.get("motion_precision") == "strict" and backend not in ("wan21-vace", "wan22-animate"):
        raise ValueError("Strict motion needs a control-bearing backend, not prompt-only/I2V claims")
    settings["mode"] = ("i2v" if "first_frame" in roles else "t2v") if backend in ("wan22-ti2v", "wan22-i2v-a14b") else (
        "replace" if "background_video" in roles else "animate") if backend == "wan22-animate" else "control" if backend == "wan21-vace" else settings["task_mode"]
    if shot.get("audio", "none") not in ("none", "native", "separate"):
        raise ValueError("audio must be none, native or separate")
    if shot.get("audio") == "native" and backend != "h3":
        raise ValueError("This backend does not generate native audio")
    if (shot.get("audio") == "separate") != ("audio_track" in inputs):
        raise ValueError("Separate audio requires exactly one actual audio_track")
    for adapter in settings["loras"]:
        if adapter.get("kind") not in ("identity", "style", "control"):
            raise ValueError("Custom adapters require an identity/style/control role; preset owns speed LoRA")
        if adapter.get("base_model") != settings["model_id"] or adapter.get("task") != settings["mode"]:
            raise ValueError("LoRA base model and task must match the selected pipeline")
        path = local_path(project, adapter["path"])
        if not path.is_file() or not isinstance(adapter.get("scale"), (int, float)):
            raise ValueError("LoRA file and explicit scale required")
        if not math.isfinite(adapter["scale"]) or (adapter.get("trigger") and adapter["trigger"] not in shot["prompt"]):
            raise ValueError("LoRA needs a finite scale and any declared trigger in the actual final prompt")
        adapter["sha256"] = sha256(path)
    output_frames = round(duration * fps)
    model_frames = 5 + 17 * math.ceil((output_frames - 5) / 17) if backend == "h3" else 1 + 4 * math.ceil((output_frames - 1) / 4)
    shot.update(fps=fps, output_frames=output_frames, model_frames=model_frames)
    if backend == "h3":
        check_h3_prompt(shot["prompt"],settings,inputs)
    code = {name: sha256(SCRIPT_DIR / name) for name in ("backends.py", "remote.py", "h3_setup.py")}
    job = dict(schema_version=1, project_id=plan["project_id"], request=plan["request"],
               settings=settings, shot=shot, assets=selected, characters=char_specs,
               budget=plan["budget"], code=code, generation_digest_version=2)
    job["generation_digest"] = generation_digest(job)
    job["job_digest"] = job["generation_digest"]
    return job



def generation_digest(job, *, version=None):
    """Content identity, independent of spend policy and evidence sampling.

    Keep the immutable job snapshot for provenance. This projection also lets
    pre-separation attempts be compared without rewriting their receipts.
    """
    value = copy.deepcopy(job)
    version = job.get("generation_digest_version", 1) if version is None else version
    if version not in (1, 2):
        raise ValueError("Unsupported generation digest version")
    for key in ("job_digest", "generation_digest", "budget", "review_spec_digest"):
        value.pop(key, None)
    value.pop("generation_digest_version", None)
    for key in ("qa", "criteria"):
        value["shot"].pop(key, None)
    # The final prompt/duration and actual asset bytes already contain all
    # model inputs. Lookup aliases and subtitle alignment must not force GPU
    # regeneration. Current artifact validation still rejects stale speech.
    if version == 2:
        for key in ("reference_bindings", "audio_timeline", "dialogue_timing", "dialogue_timing_result"):
            value["shot"].pop(key, None)
        from reference_resolver import generation_character
        value["characters"] = [generation_character(character) for character in value.get("characters", [])]
        for asset in value.get("assets", {}).values():
            asset.pop("audio_artifact", None)
    return digest(value)


def review_spec(job):
    return {"criteria": job["shot"]["criteria"], "qa": job["shot"].get("qa", {})}


def current_review_job(directory):
    """Read current QA for raw attempts; edited segments retain their recipe."""
    directory = Path(directory).resolve()
    snapshot = read_json(directory / "job.json")
    if directory.parent.name == "attempts" and (directory.parent.parent / "plan.json").is_file():
        verify_current(directory.parent.parent, directory)
        current = compile_job(directory.parent.parent, snapshot["shot"]["id"])
        snapshot["shot"]["criteria"] = current["shot"]["criteria"]
        snapshot["shot"]["qa"] = current["shot"].get("qa", {})
        if "audio_timeline" in current["shot"]:
            snapshot["shot"]["audio_timeline"] = current["shot"]["audio_timeline"]
    return snapshot


@contextmanager
def reservation_lock(path):
    """An OS-held lock releases on process death; never unlink its inode."""
    try:
        import fcntl
    except ImportError as exc:
        raise RuntimeError("Reservation locking requires a POSIX host (Linux/macOS)") from exc
    with Path(path).open("a+") as handle:
        fcntl.flock(handle.fileno(), fcntl.LOCK_EX)
        try:
            yield
        finally:
            fcntl.flock(handle.fileno(), fcntl.LOCK_UN)

def validate_job_media(project, job):
    """Validate decoded modality, not merely the filename extension."""
    from media import probe, run
    decoded = {}
    for name,item in job["assets"].items():
        path = local_path(project,item["path"])
        decoded[name] = probe(path)
        run(["ffmpeg","-v","error","-xerror","-i",str(path),"-f","null","-"])
    for role,values in job["shot"].get("inputs",{}).items():
        for name in values if isinstance(values,list) else [values]:
            info = decoded[name]
            video = [s for s in info["streams"] if s["codec_type"] == "video"]
            if role in ("first_frame","last_frame","references"):
                if not video or video[0].get("codec_name") not in ("png","mjpeg","webp") or int(video[0].get("nb_read_frames",0)) != 1:
                    raise ValueError(f"{role}: decoded input must be a single supported still image")
            elif role.endswith("video"):
                duration = info.get("format",{}).get("duration")
                if not video or duration is None or not math.isfinite(float(duration)) or float(duration) <= 0 or int(video[0].get("nb_read_frames",0)) < 2:
                    raise ValueError(f"{role}: decoded input is not an actual temporal video")
            elif role == "audio_track" and not any(s["codec_type"] == "audio" for s in info["streams"]):
                raise ValueError("audio_track: decoded input has no audio stream")


def prepare(project):
    project = Path(project)
    plan = read_json(project / "plan.json")
    jobs = [compile_job(project, shot["id"]) for shot in plan["shots"]]
    for job in jobs:
        validate_job_media(project,job)
    for job in jobs:
        write_json(project / "jobs" / f"{job['shot']['id']}.json", job)
    return jobs


def reserve(project, shot_id):
    """Local durable reservation precedes upload/submit; each attempt is unique."""
    project = Path(project).resolve()
    job = compile_job(project, shot_id)
    validate_job_media(project,job)
    root = project / "attempts"
    root.mkdir(parents=True, exist_ok=True)
    # Exclusive lock serializes the budget check across local controllers.
    lock = root / ".reserve.lock"
    with reservation_lock(lock):
        # The plan may have changed while waiting for another controller.
        job = compile_job(project, shot_id)
        validate_job_media(project, job)
        existing = [read_json(p) for p in root.glob("*/receipt.json")]
        budget = job["budget"]
        if len(existing) >= budget["max_total_attempts"] or sum(r["shot_id"] == shot_id for r in existing) >= budget["max_attempts_per_shot"]:
            raise ValueError("Attempt budget exhausted; revise the explicit project budget before new work")
        attempt_id = identifier(shot_id[:50] + "_" + uuid.uuid4().hex[:12])
        directory = root / attempt_id
        directory.mkdir(exist_ok=False)
        write_json(directory / "job.json", job)
        write_json(directory / "receipt.json", dict(attempt_id=attempt_id, shot_id=shot_id,
            job_digest=job["job_digest"], state="reserved", reserved_utc=datetime.now(timezone.utc).isoformat()))
    return directory, job



def _current_submission_budget(project, directory):
    """Reservations consume the cap, including uncertain and failed attempts.

    Lowering a cap below already reserved work blocks further submissions. Never
    silently discard reservations or increase authorization to make work fit.
    """
    snapshot = verify_current(project, directory)
    budget = compile_job(project, snapshot["shot"]["id"])["budget"]
    existing = [read_json(path) for path in (project / "attempts").glob("*/receipt.json")]
    per_shot = sum(receipt["shot_id"] == snapshot["shot"]["id"] for receipt in existing)
    if len(existing) > budget["max_total_attempts"] or per_shot > budget["max_attempts_per_shot"]:
        raise ValueError("Current attempt budget is below existing reservations; submission blocked. "
                         "Reconcile reservations and explicit budget authorization before spending.")
    return snapshot, dict(budget)


def admit_submission(project, attempt, session):
    """Claim one reserved attempt under the same lock as budget reservation."""
    project = Path(project).resolve()
    directory = project / "attempts" / identifier(attempt)
    identifier(session)
    with reservation_lock(project / "attempts/.reserve.lock"):
        receipt = read_json(directory / "receipt.json")
        if receipt.get("state") != "reserved":
            raise ValueError("Only an unsubmitted reserved attempt may be submitted. Fetch/reconcile existing work.")
        job, budget = _current_submission_budget(project, directory)
        if (receipt.get("attempt_id") != attempt or receipt.get("job_digest") != job["job_digest"]
                or receipt.get("shot_id") != job["shot"]["id"]):
            raise ValueError("Reservation receipt does not match this immutable attempt")
        receipt.update(state="uploading", session=session,
            remote_directory=f"/content/video-studio/{job['project_id']}/{attempt}",
            submission_id=uuid.uuid4().hex, submission_budget=budget,
            submission_claimed_utc=datetime.now(timezone.utc).isoformat())
        write_json(directory / "receipt.json", receipt)
    return job, receipt


def confirm_submission(project, attempt, submission_id):
    """Re-read authorization after upload, immediately before remote execution."""
    project = Path(project).resolve()
    directory = project / "attempts" / identifier(attempt)
    with reservation_lock(project / "attempts/.reserve.lock"):
        receipt = read_json(directory / "receipt.json")
        if receipt.get("state") != "uploading" or receipt.get("submission_id") != submission_id:
            raise ValueError("Submission claim changed; reconcile before remote execution")
        _, budget = _current_submission_budget(project, directory)
        receipt.update(state="submitted", execution_budget=budget,
            execution_admitted_utc=datetime.now(timezone.utc).isoformat())
        write_json(directory / "receipt.json", receipt)
    return receipt


def mark_submission_uncertain(project, attempt, submission_id):
    project = Path(project).resolve()
    directory = project / "attempts" / identifier(attempt)
    with reservation_lock(project / "attempts/.reserve.lock"):
        receipt = read_json(directory / "receipt.json")
        if receipt.get("submission_id") == submission_id and receipt.get("state") in ("uploading", "submitted"):
            receipt["state"] = "needs_reconcile"
            write_json(directory / "receipt.json", receipt)


def verify_job_snapshot(job):
    if job.get("provenance") or "generation_digest" not in job:
        expected = digest({key: value for key, value in job.items() if key != "job_digest"})
    else:
        expected = generation_digest(job)
        if job["generation_digest"] != expected:
            raise ValueError("Attempt generation snapshot changed")
    if job.get("job_digest") != expected:
        raise ValueError("Attempt job digest does not match its snapshot")


def verify_media_provenance(directory):
    """Bind editable/reviewable bytes to a generation or conforming receipt."""
    directory = Path(directory).resolve()
    job = read_json(directory / "job.json")
    verify_job_snapshot(job)
    if job.get("provenance", {}).get("method") == "ffmpeg_conform":
        receipt = read_json(directory / "receipt.json")
        if receipt.get("method") != "ffmpeg_conform":
            raise ValueError("Missing conforming receipt")
        if "video_sha256" not in receipt:
            # Older conformed segments bind their media hash in the recipe.
            recipe = read_json(directory.parent.parent / "recipe.json")
            if digest({k: v for k, v in recipe.items() if k != "recipe_digest"}) != recipe.get("recipe_digest"):
                raise ValueError("Legacy edit recipe changed")
            segment = recipe["segments"][job["shot"]["id"]]
            if segment["job_digest"] != job["job_digest"]:
                raise ValueError("Legacy edit recipe belongs to a different segment")
            receipt = dict(receipt, video_sha256=segment["video_sha"])
    else:
        receipt = read_json(directory / "result/receipt.json")
        if receipt.get("status") != "generated" or receipt.get("attempt_id") != directory.name:
            raise ValueError("Result has no matching successful generation receipt")
    if receipt.get("job_digest") != job["job_digest"] or receipt.get("video_sha256") != sha256(directory / "result/video.mp4"):
        raise ValueError("Video differs from its immutable generation/conforming receipt")
    return job

def verify_current(project, directory):
    snapshot = read_json(Path(directory) / "job.json")
    verify_job_snapshot(snapshot)
    current = compile_job(project, snapshot["shot"]["id"])
    if generation_digest(snapshot, version=2) != generation_digest(current, version=2):
        raise ValueError("Attempt no longer matches current request/assets/settings/code")
    return snapshot


def evidence_snapshot(directory):
    """Validate one manifest and bind its exact bytes, spec and job together."""
    directory = Path(directory)
    job = verify_media_provenance(directory)
    manifest_path = directory / "evidence" / "manifest.json"
    manifest_bytes = manifest_path.read_bytes()
    manifest = json.loads(manifest_bytes)
    if manifest["job_digest"] != job["job_digest"] or manifest["video_sha256"] != sha256(directory / "result" / "video.mp4"):
        raise ValueError("Evidence does not describe this job/video")
    expected_spec = review_spec(current_review_job(directory))
    recorded_spec = manifest.get("review_spec", review_spec(job))
    if recorded_spec != expected_spec:
        raise ValueError("Evidence uses an outdated review specification; inspect the same video again")
    if "review_spec_digest" in manifest and manifest["review_spec_digest"] != digest(recorded_spec):
        raise ValueError("Evidence review specification changed")
    for item in manifest["items"]:
        path = local_path(directory / "evidence", item["path"])
        if sha256(path) != item["sha256"]:
            raise ValueError(f"Evidence changed: {item['id']}")
    if manifest_path.read_bytes() != manifest_bytes:
        raise ValueError("Evidence changed while taking review snapshot")
    return dict(manifest=manifest, job=job,
                evidence_sha256=hashlib.sha256(manifest_bytes).hexdigest())


def verify_evidence(directory):
    return evidence_snapshot(directory)["manifest"]


def snapshot_template(snapshot):
    job, manifest = snapshot["job"], snapshot["manifest"]
    result = dict(schema_version=1, job_digest=job["job_digest"], video_sha256=manifest["video_sha256"],
        evidence_sha256=snapshot["evidence_sha256"],
        reviewer={"kind": "agent", "name": "", "model": ""},
        criteria=[dict(id=c["id"], verdict="unknown", evidence=[], reason="") for c in manifest.get("review_spec", review_spec(job))["criteria"]],
        limitations=["Review is limited to supplied frames/audio evidence; unexplored intervals remain uncertain."])
    if "review_spec_digest" in manifest:
        result["review_spec_digest"] = manifest["review_spec_digest"]
    return result


def review_template(directory):
    return snapshot_template(evidence_snapshot(directory))


def require_snapshot_current(directory, snapshot):
    current = evidence_snapshot(directory)
    if current["evidence_sha256"] != snapshot["evidence_sha256"]:
        raise ValueError("Evidence changed since review snapshot")


def validate_review(directory, review, require_pass=False):
    directory = Path(directory)
    snapshot = evidence_snapshot(directory)
    template = snapshot_template(snapshot)
    for key in ("job_digest", "video_sha256", "evidence_sha256", *(["review_spec_digest"] if "review_spec_digest" in template else [])):
        if review.get(key) != template[key]:
            raise ValueError(f"Review has stale {key}")
    if not review.get("reviewer", {}).get("name"):
        raise ValueError("Record the actual reviewer identity")
    expected = {c["id"] for c in template["criteria"]}
    actual = [c["id"] for c in review.get("criteria", [])]
    if len(actual) != len(set(actual)) or set(actual) != expected:
        raise ValueError("Review must cover every criterion exactly once")
    manifest = snapshot["manifest"]
    valid = {item["id"] for item in manifest["items"]}
    passed = True
    for criterion in review["criteria"]:
        if criterion.get("verdict") not in ("pass", "fail", "unknown"):
            raise ValueError("Use pass/fail/unknown verdicts")
        if not criterion.get("reason", "").strip() or not set(criterion.get("evidence", [])).issubset(valid):
            raise ValueError("Review needs reasons and resolvable evidence IDs")
        if criterion["verdict"] != "unknown" and not criterion.get("evidence"):
            raise ValueError("Pass/fail verdicts require actual evidence")
        passed &= criterion["verdict"] == "pass"
    if require_pass and not passed:
        raise ValueError("Failed/unknown criteria block final assembly")
    require_snapshot_current(directory, snapshot)
    return passed


def accept_review(directory, review_path):
    directory = Path(directory)
    review = read_json(review_path)
    # Serialize acceptance with inspect publication so a refreshed manifest cannot
    # be assigned a passing receipt from the prior evidence version.
    with reservation_lock(directory / "evidence" / ".publish.lock"):
        passed = validate_review(directory, review)
        write_json(directory / "review.json", review)
        receipt = read_json(directory / "receipt.json")
        receipt["state"] = "passed" if passed else "failed_review"
        write_json(directory / "receipt.json", receipt)
    return receipt


def selected_attempts(project, selection, require_pass=True):
    project = Path(project).resolve()
    plan = read_json(project / "plan.json")
    expected = [shot["id"] for shot in plan["shots"]]
    if set(selection) != set(expected):
        raise ValueError("Selection must name exactly one attempt for every required shot")
    directories = []
    for shot_id in expected:
        directory = project / "attempts" / identifier(selection[shot_id])
        job = verify_current(project, directory)
        if job["shot"]["id"] != shot_id:
            raise ValueError("Selection refers to a different shot")
        if require_pass:
            validate_review(directory, read_json(directory / "review.json"), require_pass=True)
        else:
            # Editing/preview needs real, technically valid media, not a quality pass.
            from media import verify_video
            verify_media_provenance(directory)
            verify_video(directory / "result/video.mp4", job["shot"])
        directories.append(directory)
    return directories
