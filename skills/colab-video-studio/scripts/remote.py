"""Colab kernel runner. Definitions can be exec'd repeatedly; attempts cannot."""
from __future__ import annotations

import gc
import hashlib
import importlib.metadata
import importlib.util
import json
import re
import subprocess
import sys
import time
import zipfile
from datetime import datetime, timezone
from pathlib import Path


def _write(path, value):
    path = Path(path)
    temporary = path.with_suffix(".tmp")
    temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2))
    temporary.replace(path)


def _hash(path):
    hasher = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for part in iter(lambda: stream.read(1024*1024), b""):
            hasher.update(part)
    return hasher.hexdigest()


def backend_cache_key(settings, code):
    """Content identity, not the attempt-specific transport paths of LoRAs."""
    stable = dict(settings)
    stable["loras"] = []
    for adapter in settings.get("loras", []):
        if not re.fullmatch(r"[0-9a-f]{64}", adapter.get("sha256", "")):
            raise ValueError("A verified LoRA SHA-256 is required for model reuse")
        stable["loras"].append({k: v for k, v in adapter.items() if k != "path"})
    return json.dumps(dict(settings=stable, code=code), sort_keys=True)


def cached_backend(key, loader, release=lambda: None):
    """Invalidate both halves before loading; failed replacement is never reusable."""
    if globals().get("_VIDEO_BACKEND_KEY") == key and globals().get("_VIDEO_BACKEND") is not None:
        return globals()["_VIDEO_BACKEND"], True
    globals()["_VIDEO_BACKEND_KEY"] = None
    globals()["_VIDEO_BACKEND"] = None
    release()
    backend = loader()
    if backend is None:
        raise RuntimeError("Backend loader returned no model")
    globals()["_VIDEO_BACKEND"] = backend
    globals()["_VIDEO_BACKEND_KEY"] = key
    return backend, False


def _install_wan(root):
    signature = "diffusers0.40-transformers5.16.1-accelerate1.12.0"
    if globals().get("_VIDEO_WAN_INSTALL") == signature:
        return
    constraints = []
    for name in ("torch", "torchvision", "torchaudio"):
        try:
            constraints.append(f"{name}=={importlib.metadata.version(name)}")
        except importlib.metadata.PackageNotFoundError:
            pass
    path = root / "torch-constraints.txt"
    path.write_text("\n".join(constraints))
    globals()["_VIDEO_H3_INSTALL_STATE"] = {}
    subprocess.run([sys.executable, "-m", "pip", "install", "--disable-pip-version-check",
        "-c", str(path), "diffusers==0.40.0", "transformers==5.16.1", "accelerate==1.12.0",
        "sentencepiece", "ftfy", "safetensors==0.8.0", "imageio-ffmpeg==0.6.0"], check=True)
    globals()["_VIDEO_WAN_INSTALL"] = signature


def run_job(job_path):
    """At-most-one local execution per remote attempt, plus durable local ledger."""
    job_path = Path(job_path).resolve()
    root = job_path.parent
    job = json.loads(job_path.read_text())
    output = root.parent / "result"
    output.mkdir(exist_ok=True)
    receipt_path = output / "receipt.json"
    marker = root.parent / "execution-started.json"
    if marker.exists():
        if receipt_path.exists():
            existing = json.loads(receipt_path.read_text())
            if existing.get("status") == "generated" and existing.get("job_digest") == job["job_digest"] and _hash(output / "video.mp4") == existing["video_sha256"]:
                print("ALREADY_GENERATED", job["attempt_id"], flush=True)
                return existing
        raise RuntimeError("This attempt has already started; reconcile it instead of rerunning inference")
    for name, expected in job["code"].items():
        if _hash(root / "scripts" / name) != expected:
            raise ValueError("Staged inference code does not match job")
    paths = {}
    for name, asset in job["assets"].items():
        path = root / "assets" / (name + Path(asset["path"]).suffix.lower())
        if not path.is_file() or _hash(path) != asset["sha256"]:
            raise ValueError("Staged asset does not match job: " + name)
        paths[name] = path
    settings = dict(job["settings"])
    settings["loras"] = [dict(adapter, path=str(root / "loras" / f"{i:03d}.safetensors"))
                         for i, adapter in enumerate(settings["loras"])]
    for actual, expected in zip(settings["loras"], job["settings"]["loras"]):
        if _hash(actual["path"]) != expected["sha256"]:
            raise ValueError("Staged LoRA does not match job")
    inputs = {role: [paths[n] for n in value] if isinstance(value, list) else paths[value]
              for role,value in job["shot"].get("inputs", {}).items()}
    import torch
    import psutil
    import shutil
    if not torch.cuda.is_available() or not torch.cuda.is_bf16_supported():
        raise RuntimeError("This implementation requires a CUDA GPU with native BF16")
    props = torch.cuda.get_device_properties(0)
    hardware = dict(gpu=props.name, vram_total_gib=props.total_memory/2**30,
                    ram_total_gib=psutil.virtual_memory().total/2**30,
                    disk_free_gib=shutil.disk_usage(root).free/2**30,
                    torch=torch.__version__, cuda=torch.version.cuda)
    _write(output / "hardware.json", hardware)
    with marker.open("x") as stream:
        json.dump(dict(attempt_id=job["attempt_id"], job_digest=job["job_digest"],
                       started_utc=datetime.now(timezone.utc).isoformat()), stream)
    receipt = dict(status="running", attempt_id=job["attempt_id"],job_digest=job["job_digest"],
                   shot_id=job["shot"]["id"], hardware=hardware)
    _write(receipt_path, receipt)
    started = time.perf_counter()

    def progress(**values):
        values.update(elapsed_seconds=round(time.perf_counter()-started,2),
                      attempt_id=job["attempt_id"], job_digest=job["job_digest"])
        _write(output / "progress.json", values)
        print("STUDIO_PROGRESS", json.dumps(values), flush=True)

    try:
        progress(phase="installing")
        if settings["backend"] != "h3":
            _install_wan(root)
        key = backend_cache_key(settings, job["code"])
        def release():
            gc.collect()
            torch.cuda.empty_cache()
        def load():
            source = root / "scripts" / "backends.py"
            spec = importlib.util.spec_from_file_location("video_backends_"+job["job_digest"][:12], source)
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            if settings["backend"] == "h3":
                # A dependency installation may alter the other backend's environment.
                globals()["_VIDEO_WAN_INSTALL"] = None
            install_state = globals().setdefault("_VIDEO_H3_INSTALL_STATE", {})
            return module.load_backend(settings, progress, install_state=install_state)
        backend, reused = cached_backend(key, load, release)
        if reused:
            progress(phase="reusing_model")
        torch.cuda.reset_peak_memory_stats()
        audio_track = inputs.pop("audio_track", None)
        generated = backend.render(job["shot"], inputs, output, progress)
        if generated["revision"] != settings["revision"] or generated["model_id"] != settings["model_id"] or generated["steps"] != settings["steps"] or generated["seed"] != job["shot"]["seed"]:
            raise ValueError("Actual generation configuration differs from immutable job")
        if audio_track:
            native = output / "video-native.mp4"
            (output / "video.mp4").replace(native)
            subprocess.run(["ffmpeg", "-v", "error", "-i", str(native), "-i", str(audio_track),
                "-map", "0:v:0", "-map", "1:a:0", "-af",
                f"atrim=duration={job['shot']['duration_seconds']},apad,atrim=duration={job['shot']['duration_seconds']}",
                "-t", str(job["shot"]["duration_seconds"]), "-c:v", "copy", "-c:a", "aac",
                str(output / "video.mp4")], check=True, capture_output=True)
            generated["audio_replaced"] = True
        versions = {}
        for name in ("torch","diffusers","transformers","accelerate","diffsynth"):
            try:
                versions[name] = importlib.metadata.version(name)
            except importlib.metadata.PackageNotFoundError:
                pass
        receipt.update(status="generated", generation=generated, versions=versions,
            video_sha256=_hash(output / "video.mp4"),
            peak_torch_allocated_gib=torch.cuda.max_memory_allocated()/2**30,
            peak_torch_reserved_gib=torch.cuda.max_memory_reserved()/2**30,
            total_seconds=round(time.perf_counter()-started,3))
        _write(receipt_path, receipt)
        progress(phase="generated")
    except Exception as exc:
        receipt.update(status="failed", error=re.sub(r"https?://\S+", "[URL]", f"{type(exc).__name__}: {exc}"))
        _write(receipt_path, receipt)
        progress(phase="failed", error_type=type(exc).__name__)
        raise RuntimeError("STUDIO_FAILED: " + receipt["error"]) from None
    finally:
        archive = root.parent / "result.zip"
        staged = archive.with_suffix(".tmp")
        with zipfile.ZipFile(staged,"w",zipfile.ZIP_STORED) as bundle:
            for path in sorted(output.glob("*")):
                if path.is_file():
                    bundle.write(path, arcname="result/"+path.name)
        staged.replace(archive)
    print("STUDIO_GENERATED", job["attempt_id"], receipt["video_sha256"], flush=True)
    return receipt
