"""L4-only FastH3 runtime shared by the notebook and agent ComfyUI flow.

The host imports only the standard library. Model dependencies are isolated in
a Colab venv, and the server listens on loopback. No original H3 is downloaded.
"""
from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
import math
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import threading
import time
from urllib.request import urlopen
import uuid
import zipfile

from fast_h3_client import ComfyClient, GraphValidationError, PromptExecutionError, PromptTimeoutError
from fast_h3_workflow import build_graph, to_ui_workflow


def write_json(path, data):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + ".tmp")
    temporary.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    temporary.replace(path)


def sha256(path):
    digest = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for chunk in iter(lambda: stream.read(8 * 1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def verify_media(path, *, width, height, duration_seconds):
    from fractions import Fraction
    command = ["ffprobe", "-v", "error", "-count_frames", "-show_streams", "-show_format", "-of", "json", str(path)]
    result = subprocess.run(command, capture_output=True, text=True, check=True)
    info = json.loads(result.stdout)
    video = next(s for s in info["streams"] if s["codec_type"] == "video")
    audio = next(s for s in info["streams"] if s["codec_type"] == "audio")
    if (video["width"], video["height"]) != (width, height):
        raise ValueError("Decoded video dimensions differ from the requested graph")
    if float(Fraction(video["avg_frame_rate"])) != 24 or int(video["nb_read_frames"]) != round(duration_seconds * 24):
        raise ValueError("Decoded video frame count/rate differs from the requested graph")
    if abs(float(video["duration"]) - duration_seconds) > 1 / 24:
        raise ValueError("Video duration differs from the requested graph")
    if int(audio["sample_rate"]) != 32000 or int(audio["channels"]) != 2:
        raise ValueError("Output must have native 32 kHz stereo audio")
    if abs(float(audio["duration"]) - duration_seconds) > 0.06:
        raise ValueError("Audio duration differs from the requested graph")
    subprocess.run(["ffmpeg", "-v", "error", "-xerror", "-i", str(path), "-f", "null", "-"],
                   capture_output=True, check=True)
    return info


class ResourceMonitor:
    """Observe the notebook and its Comfy subprocess tree, not just notebook RSS."""
    def __init__(self, state_dir):
        self.state_dir = Path(state_dir)
        self.stop_event = threading.Event()
        self.thread = None

    def sample(self):
        import psutil
        vm = psutil.virtual_memory()
        parent = psutil.Process()
        processes = [parent] + parent.children(recursive=True)
        process_info = []
        for process in processes:
            try:
                process_info.append({"pid": process.pid, "rss_bytes": process.memory_info().rss,
                                     "alive": process.is_running()})
            except psutil.Error:
                pass
        gpu = subprocess.run(["nvidia-smi", "--query-gpu=memory.used,utilization.gpu", "--format=csv,noheader,nounits"],
                             capture_output=True, text=True, timeout=15)
        result = {"time_utc": datetime.now(timezone.utc).isoformat(),
                  "ram_available_bytes": vm.available, "ram_total_bytes": vm.total,
                  "processes": process_info, "tree_rss_bytes": sum(p["rss_bytes"] for p in process_info),
                  "disk_free_bytes": shutil.disk_usage(self.state_dir).free,
                  "gpu": gpu.stdout.strip() if gpu.returncode == 0 else "unavailable"}
        cgroup = Path("/sys/fs/cgroup")
        for key in ("memory.current", "memory.max", "memory.events"):
            try:
                result[key] = (cgroup / key).read_text().strip()
            except OSError:
                result[key] = "unavailable"
        for name in ("install.log", "server.log"):
            file = self.state_dir / name
            result[name + "_bytes"] = file.stat().st_size if file.exists() else 0
        cache = self.state_dir.parent / "model-cache"
        result["download_bytes"] = sum(p.stat().st_size for p in cache.rglob("*") if p.is_file()) if cache.exists() else 0
        write_json(self.state_dir / "telemetry.json", result)
        with (self.state_dir / "resources.jsonl").open("a") as stream:
            stream.write(json.dumps(result) + "\n")

    def start(self):
        if self.thread and self.thread.is_alive():
            return
        self.stop_event.clear()
        def loop():
            while not self.stop_event.is_set():
                try:
                    self.sample()
                except Exception as error:
                    write_json(self.state_dir / "monitor-error.json", {"error_type": type(error).__name__})
                self.stop_event.wait(5)
        self.thread = threading.Thread(target=loop, daemon=True)
        self.thread.start()

    def stop(self):
        self.stop_event.set()
        if self.thread:
            self.thread.join(timeout=20)


class FastH3Runtime:
    def __init__(self, root="/content/fast-h3", port=8188):
        self.root = Path(root)
        self.state = self.root / "state"
        self.comfy = self.root / "ComfyUI"
        self.venv = self.root / "venv"
        self.python = self.venv / "bin/python"
        self.port = int(port)
        self.state.mkdir(parents=True, exist_ok=True)
        self.lock = json.loads(Path(__file__).with_name("fast_h3_lock.json").read_text())
        self.client = ComfyClient(f"http://127.0.0.1:{self.port}")
        self.monitor = ResourceMonitor(self.state)
        self.server = None

    def phase(self, phase, **extra):
        write_json(self.state / "progress.json", {"phase": phase, "updated_utc": datetime.now(timezone.utc).isoformat(), **extra})
        print("FastH3:", phase, flush=True)

    def check_hardware(self):
        import psutil
        result = subprocess.run(["nvidia-smi", "--query-gpu=name,memory.total,memory.free,driver_version", "--format=csv,noheader,nounits"],
                                capture_output=True, text=True, check=True)
        rows = [row.split(",") for row in result.stdout.strip().splitlines()]
        if len(rows) != 1 or rows[0][0].strip() != "NVIDIA L4":
            raise RuntimeError("This FastH3 test flow requires exactly one NVIDIA L4; no A100/base-model fallback")
        row = [x.strip() for x in rows[0]]
        vm = psutil.virtual_memory()
        hardware = {"gpu": row[0], "vram_total_mib": float(row[1]), "vram_free_mib": float(row[2]),
                    "driver": row[3], "ram_total_gib": round(vm.total / 2**30, 2),
                    "ram_available_gib": round(vm.available / 2**30, 2),
                    "disk_free_gib": round(shutil.disk_usage(self.root).free / 2**30, 2),
                    "python": sys.version.split()[0]}
        write_json(self.state / "hardware.json", hardware)
        return hardware

    def _run(self, command, *, cwd=None):
        with (self.state / "install.log").open("a") as log:
            result = subprocess.run([str(x) for x in command], cwd=cwd, stdout=log, stderr=subprocess.STDOUT)
        if result.returncode:
            raise RuntimeError(f"{Path(str(command[0])).name} exited {result.returncode}; see {self.state / 'install.log'}")

    def _checkout(self, repo, revision, destination):
        destination = Path(destination)
        if (destination / ".git").is_dir():
            actual = subprocess.check_output(["git", "-C", str(destination), "rev-parse", "HEAD"], text=True).strip()
            if actual != revision:
                raise RuntimeError(f"Existing checkout has a different revision: {destination}")
            return
        if destination.exists() and any(destination.iterdir()):
            raise RuntimeError(f"Refusing to replace a nonempty installation: {destination}")
        destination.mkdir(parents=True, exist_ok=True)
        self._run(["git", "init", str(destination)])
        self._run(["git", "-C", destination, "remote", "add", "origin", repo])
        self._run(["git", "-C", destination, "fetch", "--depth", "1", "origin", revision])
        self._run(["git", "-C", destination, "checkout", "--detach", "FETCH_HEAD"])

    def _install(self):
        self.phase("installing")
        self._checkout(**dict(self.lock["comfyui"], destination=self.comfy))
        pack = self.comfy / "custom_nodes/ComfyUI-FastH3-VSA"
        self._checkout(**dict(self.lock["vsa_pack"], destination=pack))
        signature = hashlib.sha256(json.dumps({key: self.lock[key] for key in
                                   ("comfyui", "vsa_pack", "comfy_kitchen")}, sort_keys=True).encode()).hexdigest()
        marker = self.state / "installed.json"
        if not marker.exists() or json.loads(marker.read_text()).get("signature") != signature:
            # Colab can disable ensurepip while exposing its existing pip module.
            # This also repairs a venv left incomplete by ensurepip failure.
            self._run([sys.executable, "-m", "venv", "--system-site-packages", "--without-pip", str(self.venv)])
            self._run([self.python, "-m", "pip", "--version"])
            import importlib.metadata
            constraints = []
            for package in ("torch", "torchvision", "torchaudio"):
                try:
                    constraints.append(f"{package}=={importlib.metadata.version(package)}")
                except importlib.metadata.PackageNotFoundError:
                    pass
            constraint_file = self.state / "torch-constraints.txt"
            constraint_file.write_text("\n".join(constraints) + "\n")
            self._run([self.python, "-m", "pip", "install", "--disable-pip-version-check", "-c", constraint_file,
                       "-r", self.comfy / "requirements.txt", "huggingface_hub==1.11.0"])
            self._run([self.python, "-m", "pip", "freeze"])
            versions = subprocess.check_output([self.python, "-m", "pip", "freeze"], text=True)
            (self.state / "versions.txt").write_text(versions)
            write_json(marker, {"signature": signature, "lock": self.lock})
        own_package = self.comfy / "custom_nodes/FastH3-L4-Flow"
        own_package.mkdir(exist_ok=True)
        shutil.copyfile(Path(__file__).with_name("fast_h3_nodes.py"), own_package / "__init__.py")

    def _kernel_preflight(self):
        self.phase("kernel_preflight")
        script = '''import json, torch, comfy_kitchen
from comfy_kitchen.backends import cuda
assert torch.cuda.get_device_capability() == (8, 9)
assert cuda._EXT_AVAILABLE, str(cuda._EXT_ERROR)
for name in ("sol_attn_plan", "sol_producer_begin", "sol_producer_chunk", "sol_attn_core"):
    assert callable(getattr(cuda._C, name, None)), name
q = torch.randn(1, 256, 4, 128, device="cuda", dtype=torch.bfloat16)
k = torch.randn_like(q); v = torch.randn_like(q)
out = cuda.sol_attn(q, k, v, topk_ratio=0.1, tail=False,
                   sink_blocks=[0,1], sink_q=[0,1],
                   block_len=torch.full((4,),64,device="cuda",dtype=torch.int32),
                   coarse_gate=torch.zeros_like(q))
assert out.shape == q.shape and torch.isfinite(out).all()
torch.cuda.synchronize()
print(json.dumps({"torch":torch.__version__, "cuda":torch.version.cuda,
                  "comfy_kitchen":comfy_kitchen.__version__ if hasattr(comfy_kitchen,"__version__") else "unknown",
                  "device":torch.cuda.get_device_name(), "vsa_kernel":"sol_attn_cuda", "status":"pass"}))
'''
        result = subprocess.run([str(self.python), "-c", script], capture_output=True, text=True)
        (self.state / "kernel-preflight.log").write_text(result.stdout + result.stderr)
        if result.returncode:
            raise RuntimeError("L4 native Sol-Attn kernel preflight failed; model downloads have not started")
        write_json(self.state / "kernel-preflight.json", json.loads(result.stdout.strip().splitlines()[-1]))

    def _lora_assets(self, loras):
        if not isinstance(loras, list):
            raise ValueError("loras must be a JSON list")
        assets, resolved = [], []
        for item in loras:
            if not isinstance(item, dict):
                raise ValueError("Each LoRA must be an object")
            strength = item.get("strength", item.get("strength_model", 1.0))
            if type(strength) not in (int, float) or not math.isfinite(strength) or not -2 <= strength <= 2:
                raise ValueError("LoRA strength must be a finite value in [-2,2]")
            if "path" in item:
                path = Path(item["path"])
                if not path.is_file() or path.suffix != ".safetensors":
                    raise ValueError("Local LoRA path must be an existing safetensors file")
                digest = sha256(path)
                name = digest[:12] + "_" + path.name
                assets.append({"local_path": str(path), "size": path.stat().st_size,
                               "sha256": digest, "destination": "loras/" + name})
            else:
                repo, revision, file = item.get("repo", ""), item.get("revision", ""), item.get("file", "")
                if (not re.fullmatch(r"[\w.-]+/[\w.-]+", repo) or not re.fullmatch(r"[0-9a-f]{40}", revision)
                        or not file.endswith(".safetensors") or file.startswith("/") or ".." in Path(file).parts):
                    raise ValueError("Remote LoRA requires repo, exact 40-character revision, and safetensors file")
                with urlopen(f"https://huggingface.co/api/models/{repo}/revision/{revision}?blobs=true", timeout=30) as response:
                    info = json.load(response)
                sibling = next((x for x in info["siblings"] if x["rfilename"] == file), None)
                if sibling is None or not sibling.get("lfs", {}).get("sha256"):
                    raise ValueError("Pinned LoRA file has no verifiable HF LFS hash")
                digest = sibling["lfs"]["sha256"]
                name = digest[:12] + "_" + Path(file).name
                assets.append({"repo": repo, "revision": revision, "file": file,
                               "sha256": digest, "size": sibling["size"], "destination": "loras/" + name})
            resolved.append({"lora_name": name, "strength_model": float(strength)})
        return assets, resolved

    def _download(self, extra_assets):
        self.phase("downloading")
        assets = self.lock["assets"] + extra_assets
        verified_file = self.state / "verified-assets.json"
        verified = json.loads(verified_file.read_text()) if verified_file.exists() else {}
        missing = []
        for item in assets:
            path = self.comfy / "models" / item["destination"]
            if path.exists() and path.stat().st_size == item["size"]:
                record = verified.get(item["destination"], {})
                if record.get("sha256") == item["sha256"] and record.get("mtime_ns") == path.stat().st_mtime_ns:
                    continue
                if sha256(path) == item["sha256"]:
                    verified[item["destination"]] = {"sha256": item["sha256"], "mtime_ns": path.stat().st_mtime_ns}
                    continue
                raise ValueError("Existing model file has a different SHA256: " + item["destination"])
            missing.append(item)
        missing_bytes = sum(item["size"] for item in missing)
        if shutil.disk_usage(self.root).free < missing_bytes + 8 * 2**30:
            raise RuntimeError("Insufficient disk for selected FastH3 files and output workspace")
        write_json(self.state / "model-manifest.json", assets)
        write_json(self.state / "download-job.json", {"root": str(self.root), "assets": missing})
        # HF dependencies belong to the isolated environment, not the notebook.
        download_script = '''import hashlib,json,os,shutil
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
os.environ["HF_XET_CHUNK_CACHE_SIZE_BYTES"]="0"
os.environ["HF_XET_NUM_CONCURRENT_RANGE_GETS"]="4"
from huggingface_hub import hf_hub_download
from huggingface_hub.utils import disable_progress_bars
disable_progress_bars()
job=json.loads(Path(__import__("sys").argv[1]).read_text());root=Path(job["root"])
def one(item):
 dst=root/"ComfyUI/models"/item["destination"];dst.parent.mkdir(parents=True,exist_ok=True)
 if dst.exists():raise RuntimeError("Partial destination exists: "+item["destination"])
 if "local_path" in item:src=Path(item["local_path"])
 else:
  cache=root/"model-cache"/item["repo"].replace("/","--")/item["revision"]
  src=Path(hf_hub_download(item["repo"],item["file"],revision=item["revision"],local_dir=cache,token=False))
 digest=hashlib.sha256()
 with src.open("rb") as f:
  for chunk in iter(lambda:f.read(8*1024*1024),b""):digest.update(chunk)
 assert src.stat().st_size==item["size"] and digest.hexdigest()==item["sha256"],item["destination"]
 if "local_path" in item:shutil.copyfile(src,dst)
 else:os.link(src,dst)
 print("VERIFIED",item["destination"],flush=True)
with ThreadPoolExecutor(max_workers=2) as pool:list(pool.map(one,job["assets"]))
'''
        self._run([self.python, "-c", download_script, self.state / "download-job.json"])
        for item in missing:
            path = self.comfy / "models" / item["destination"]
            verified[item["destination"]] = {"sha256": item["sha256"], "mtime_ns": path.stat().st_mtime_ns}
        write_json(verified_file, verified)

    def _server_ready(self):
        try:
            self.client.get_json("/system_stats")
            marker = self.state / "server.json"
            if not marker.exists():
                raise RuntimeError("The selected local port belongs to another server")
            return True
        except (OSError, ConnectionError):
            return False

    def _start_server(self):
        if self._server_ready():
            return
        self.phase("starting_server")
        environment = dict(os.environ, FASTH3_STATE_DIR=str(self.state))
        log = (self.state / "server.log").open("a")
        command = [str(self.python), str(self.comfy / "main.py"), "--listen", "127.0.0.1", "--port", str(self.port),
                   "--disable-auto-launch", "--lowvram", "--disable-pinned-memory", "--cache-lru", "1",
                   "--reserve-vram", "3", "--use-pytorch-cross-attention", "--enable-triton-backend",
                   "--disable-comfy-compiler"]
        self.server = subprocess.Popen(command, cwd=self.comfy, env=environment, stdout=log, stderr=subprocess.STDOUT)
        log.close()
        write_json(self.state / "server.json", {"pid": self.server.pid, "port": self.port, "command": command})
        deadline = time.monotonic() + 180
        while time.monotonic() < deadline:
            if self.server.poll() is not None:
                raise RuntimeError("ComfyUI startup failed; see server.log")
            if self._server_ready():
                required = {"FastH3VSAPatch", "FastH3ExactSigmas", "FastH3CheckedLoraLoader", "FastH3ReportAndTrim"}
                if not required <= self.client.object_info().keys():
                    raise RuntimeError("Required public/local FastH3 nodes failed to import")
                return
            time.sleep(2)
        raise TimeoutError("ComfyUI did not start within 180 seconds")

    def setup(self, loras=None):
        started = time.monotonic()
        hardware = self.check_hardware()
        extra_assets, resolved = self._lora_assets([] if loras is None else loras)
        self.monitor.start()
        try:
            self._install()
            self._kernel_preflight()
            self._download(extra_assets)
            self._start_server()
            result = {"status": "ready", "hardware": hardware, "lock": self.lock,
                      "loras": resolved, "setup_seconds": round(time.monotonic() - started, 2)}
            write_json(self.state / "setup.json", result)
            self.phase("ready")
            return result
        except Exception as error:
            self.phase("setup_failed", error_type=type(error).__name__)
            raise
        finally:
            self.monitor.stop()

    def ensure_ready(self, loras=None):
        assets, resolved = self._lora_assets([] if loras is None else loras)
        if not self._server_ready():
            return self.setup(loras=loras)
        self.check_hardware()
        if assets:
            self.monitor.start()
            try:
                self._download(assets)
            finally:
                self.monitor.stop()
        return resolved

    def status(self):
        result = {"root": str(self.root), "server_ready": self._server_ready()}
        for name in ("progress.json", "hardware.json", "kernel-preflight.json"):
            file = self.state / name
            if file.exists():
                result[name[:-5]] = json.loads(file.read_text())
        if result["server_ready"]:
            result["queue"] = self.client.get_json("/queue")
        return result

    def _reference_inputs(self, reference_paths, *, stage=True):
        if not isinstance(reference_paths, list) or not 1 <= len(reference_paths) <= 3:
            raise ValueError("Experimental Ref2VA requires 1–3 local reference image paths")
        manifest, names = [], []
        for index, value in enumerate(reference_paths):
            if not isinstance(value, str):
                raise ValueError("Reference paths must be strings")
            source = Path(value).expanduser().resolve(strict=True)
            if not source.is_file() or source.suffix.lower() not in (".png", ".jpg", ".jpeg", ".webp"):
                raise ValueError("Reference must be a local PNG/JPEG/WebP file")
            from PIL import Image
            with Image.open(source) as img:
                img.load()
                size = list(img.size)
            digest = sha256(source)
            # Stock LoadImage advertises only files directly in its input root.
            name = "fast_h3_ref_" + digest + source.suffix.lower()
            if name in names:
                raise ValueError("Do not repeat identical reference files")
            target = self.comfy / "input" / name
            if stage:
                target.parent.mkdir(parents=True, exist_ok=True)
                if not target.exists():
                    shutil.copyfile(source, target)
                if sha256(target) != digest:
                    raise ValueError("Reference input copy failed SHA256 verification")
            names.append(name)
            manifest.append({"picture": index + 1, "input_name": name, "sha256": digest,
                             "bytes": source.stat().st_size, "source_size": size})
        return names, manifest

    def generate(self, prompt, width=864, height=480, duration_seconds=5, seed=123456662,
                 loras=None, run_name="fast_h3_notebook", timeout=1800,
                 generation_mode="t2va", reference_paths=None):
        # Validate settings before any setup/download or queue side effect.
        reference_paths = [] if reference_paths is None else reference_paths
        if not isinstance(reference_paths, list):
            raise ValueError("reference_paths must be a JSON list")
        build_graph(prompt, width, height, duration_seconds, seed, run_name=run_name,
                    generation_mode=generation_mode,
                    reference_images=[f"reference_{i}.png" for i in range(len(reference_paths))])
        names, reference_manifest = self._reference_inputs(reference_paths, stage=False) if reference_paths else ([], [])
        _, resolved = self._lora_assets([] if loras is None else loras)
        self.ensure_ready(loras=loras)
        if reference_paths:
            names, reference_manifest = self._reference_inputs(reference_paths)
        identity = str(uuid.uuid4())
        run_dir = self.root / "runs" / (run_name + "_" + datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S") + "_" + identity[:8])
        run_dir.mkdir(parents=True, exist_ok=False)
        graph = build_graph(prompt, width, height, duration_seconds, seed, loras=resolved,
                            run_name=run_dir.name, generation_mode=generation_mode, reference_images=names,
                            request_id=identity)
        workflow = to_ui_workflow(graph)
        write_json(run_dir / "workflow.api.json", graph)
        write_json(run_dir / "workflow.json", workflow)
        if reference_manifest:
            write_json(run_dir / "reference-manifest.json", reference_manifest)
        metrics = {"status": "submitting", "prompt_id": identity, "run_dir": str(run_dir),
                   "width": width, "height": height, "duration_seconds": duration_seconds,
                   "prompt": prompt, "seed": seed, "lock": self.lock, "loras": resolved,
                   "generation_mode": generation_mode, "reference_manifest": reference_manifest}
        started = time.monotonic()
        write_json(run_dir / "metrics.json", metrics)
        with (run_dir / "started.json").open("x") as stream:
            json.dump({"prompt_id": identity}, stream)
        self.monitor.start()
        try:
            self.phase("submitting", prompt_id=identity, run_dir=str(run_dir))
            response = self.client.queue_prompt(graph, prompt_id=identity,
                        extra_data={"extra_pnginfo": {"workflow": workflow}})
            if response["prompt_id"] != identity:
                raise RuntimeError("ComfyUI did not retain the reserved prompt identity")
            metrics["status"] = "queued"
            write_json(run_dir / "metrics.json", metrics)
            history = self.client.wait_prompt(identity, timeout=timeout, on_status=lambda data:
                        self.phase(data["state"], prompt_id=identity, run_dir=str(run_dir), elapsed_seconds=data["elapsed_seconds"]))
            write_json(run_dir / "history.json", history)
            reports = [report for output in history.get("outputs", {}).values() for report in output.get("fast_h3", [])]
            if len(reports) != 1:
                raise RuntimeError("ComfyUI completed without the FastH3 execution receipt")
            if generation_mode == "experimental_ref2va_ood":
                report = reports[0]
                reference = report.get("reference", {})
                if (report.get("mode") != generation_mode or reference.get("reference_count") != len(names)
                        or len(reference.get("forward_seconds", [])) != 4
                        or len(reference.get("layouts", [])) != 4
                        or any(item.get("ref_image_tokens", 0) <= 0 for item in reference.get("layouts", []))):
                    raise RuntimeError("Ref2VA receipt did not prove four image-conditioned forwards")
            outputs = self.client.output_files(history)
            if len(outputs) != 1:
                raise RuntimeError("Expected one saved FastH3 MP4")
            self.phase("verifying", prompt_id=identity, run_dir=str(run_dir))
            video = self.client.download_output(outputs[0], run_dir / "video.mp4")
            media = verify_media(video, width=width, height=height, duration_seconds=duration_seconds)
            write_json(run_dir / "media.json", media)
            metrics.update(reports[0], status="technically_valid", video_path=str(video),
                           video_sha256=sha256(video), total_seconds=round(time.monotonic() - started, 2))
            for name in ("hardware.json", "kernel-preflight.json", "versions.txt", "model-manifest.json", "resources.jsonl"):
                file = self.state / name
                if file.exists():
                    shutil.copyfile(file, run_dir / name)
            write_json(run_dir / "metrics.json", metrics)
            archive = run_dir.with_suffix(".zip")
            with zipfile.ZipFile(archive, "w", compression=zipfile.ZIP_STORED) as bundle:
                for file in run_dir.iterdir():
                    if file.is_file():
                        bundle.write(file, file.name)
            metrics["archive_path"] = str(archive)
            write_json(self.root / "latest.json", metrics)
            self.phase("technically_valid", prompt_id=identity, run_dir=str(run_dir))
            print("PASS: FastH3, four Euler forwards, 200 native VSA calls, video + stereo audio", flush=True)
            return metrics
        except Exception as error:
            if isinstance(error, GraphValidationError):
                metrics["status"] = "validation_failed"
            elif isinstance(error, PromptExecutionError):
                write_json(run_dir / "history.json", error.history)
                metrics["status"] = "execution_failed"
            else:
                metrics["status"] = "needs_reconcile"
            metrics["error_type"] = type(error).__name__
            metrics["total_seconds"] = round(time.monotonic() - started, 2)
            write_json(run_dir / "metrics.json", metrics)
            self.phase(metrics["status"], prompt_id=identity, run_dir=str(run_dir))
            raise
        finally:
            self.monitor.stop()

    def stop_server(self):
        marker = self.state / "server.json"
        if not marker.exists():
            return
        import psutil
        pid = json.loads(marker.read_text())["pid"]
        try:
            process = psutil.Process(pid)
            if str(self.comfy / "main.py") not in process.cmdline():
                raise RuntimeError("Server PID now belongs to another process")
            process.terminate()
            process.wait(timeout=20)
        except psutil.NoSuchProcess:
            pass
        self.phase("server_stopped")
