#!/usr/bin/env python3
"""Pinned, opt-in ComfyUI workspace for Colab; imports only the standard library.

This is independent of the verified L4 FastH3 installation. Installing nodes or
starting the server does not establish that a model fits or produces good media.
"""
from __future__ import annotations

import argparse
import hashlib
import importlib.metadata
import json
import os
from pathlib import Path, PurePosixPath
import re
import signal
import socket
import subprocess
import sys
import tempfile
import time
from urllib.parse import quote
from urllib.request import urlopen
import uuid
import shutil

from fast_h3_client import ComfyClient, PromptExecutionError, PromptTimeoutError


CATALOG_PATH = Path(__file__).with_name("comfyui_catalog.json")
DEFAULT_EXTENSIONS = ("continuum", "ref2va-vsa")


def load_catalog():
    return json.loads(CATALOG_PATH.read_text(encoding="utf-8"))


def write_json(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + ".tmp")
    temporary.write_text(json.dumps(value, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    temporary.replace(path)


def sha256(path):
    digest = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for chunk in iter(lambda: stream.read(8 * 1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def model_path(root, destination):
    relative = PurePosixPath(destination)
    if (relative.is_absolute() or not relative.parts or ".." in relative.parts
            or "\\" in destination):
        raise ValueError("Model destination must be relative to ComfyUI/models")
    root = Path(root).resolve()
    target = (root / str(relative)).resolve()
    if not target.is_relative_to(root):
        raise ValueError("Model destination leaves ComfyUI/models")
    return target


def download_asset(asset, target):
    """Stream one pinned artifact, verifying it before atomic publication.

    Existing different files are never overwritten. A retry can reuse completed
    files; an incomplete temporary transfer is discarded on failure.
    """
    if not re.fullmatch(r"[0-9a-f]{40}", asset["revision"]):
        raise ValueError("Model revision must be a full commit SHA")
    if not re.fullmatch(r"[0-9a-f]{64}", asset["sha256"]):
        raise ValueError("Model must have a SHA-256")
    target = Path(target)
    if target.exists():
        if target.stat().st_size != asset["size"] or sha256(target) != asset["sha256"]:
            raise RuntimeError(f"Existing model differs from the catalog: {target}")
        return target
    target.parent.mkdir(parents=True, exist_ok=True)
    url = ("https://huggingface.co/" + quote(asset["repo"], safe="/") + "/resolve/"
           + asset["revision"] + "/" + quote(asset["file"], safe="/"))
    descriptor, temporary = tempfile.mkstemp(prefix="." + target.name + ".", suffix=".part", dir=target.parent)
    digest, received = hashlib.sha256(), 0
    try:
        with os.fdopen(descriptor, "wb") as output, urlopen(url, timeout=120) as response:
            for chunk in iter(lambda: response.read(8 * 1024 * 1024), b""):
                received += len(chunk)
                if received > asset["size"]:
                    raise RuntimeError(f"Model exceeds its declared size: {target.name}")
                output.write(chunk)
                digest.update(chunk)
            output.flush()
            os.fsync(output.fileno())
        if received != asset["size"] or digest.hexdigest() != asset["sha256"]:
            raise RuntimeError(f"Model size/SHA-256 mismatch: {target.name}")
        os.link(temporary, target)
        return target
    finally:
        Path(temporary).unlink(missing_ok=True)


class ComfyWorkspace:
    def __init__(self, root="/content/comfyui-workspace", port=8190, extensions=DEFAULT_EXTENSIONS):
        self.root = Path(root).expanduser().resolve()
        self.comfy = self.root / "ComfyUI"
        self.state = self.root / "state"
        self.python = self.root / "venv/bin/python"
        if type(port) is not int or not 1024 <= port <= 65535:
            raise ValueError("Use a port between 1024 and 65535")
        self.port = port
        self.catalog = load_catalog()
        if isinstance(extensions, str):
            extensions = [name.strip() for name in extensions.split(",") if name.strip()]
        unknown = set(extensions) - self.catalog["extensions"].keys()
        if unknown:
            raise ValueError(f"Unknown extensions: {sorted(unknown)}")
        self.extensions = tuple(sorted(set(extensions)))
        self.client = ComfyClient(f"http://127.0.0.1:{port}")
        self.server = None

    def _signature(self):
        selected = {key: self.catalog["extensions"][key] for key in self.extensions}
        return hashlib.sha256(json.dumps({"comfyui": self.catalog["comfyui"],
                                         "extensions": selected}, sort_keys=True).encode()).hexdigest()

    def _bundle(self, name):
        if name not in self.catalog["bundles"]:
            raise ValueError(f"Unknown model bundle: {name}")
        bundle = self.catalog["bundles"][name]
        missing = set(bundle["extensions"]) - set(self.extensions)
        if missing:
            raise ValueError(f"Enable extensions for {name}: {sorted(missing)}")
        return bundle

    def plan(self, bundle="none"):
        selected = self._bundle(bundle)
        assets = [self.catalog["assets"][key] for key in selected["assets"]]
        return {"root": str(self.root), "port": self.port, "comfyui": self.catalog["comfyui"],
                "extensions": {key: self.catalog["extensions"][key] for key in self.extensions},
                "bundle": bundle, "description": selected["description"], "assets": assets,
                "download_bytes": sum(item["size"] for item in assets),
                "download_gib": round(sum(item["size"] for item in assets) / 2**30, 2),
                "gpu_generation": "not_run"}

    def _run(self, command, cwd=None):
        self.state.mkdir(parents=True, exist_ok=True)
        print("ComfyUI:", " ".join(map(str, command)), flush=True)
        with (self.state / "install.log").open("a") as log:
            result = subprocess.run(list(map(str, command)), cwd=cwd, stdout=log, stderr=subprocess.STDOUT)
        if result.returncode:
            raise RuntimeError(f"Command exited {result.returncode}; see {self.state / 'install.log'}")

    def _checkout(self, spec, destination):
        if (destination / ".git").is_dir():
            actual = subprocess.check_output(["git", "-C", str(destination), "rev-parse", "HEAD"], text=True).strip()
            if actual != spec["revision"]:
                raise RuntimeError(f"Existing checkout has another revision: {destination}; use a new workspace root")
            return
        if destination.exists() and any(destination.iterdir()):
            raise RuntimeError(f"Refusing to replace a nonempty directory: {destination}")
        destination.mkdir(parents=True, exist_ok=True)
        self._run(["git", "init", destination])
        self._run(["git", "-C", destination, "remote", "add", "origin", spec["repo"]])
        self._run(["git", "-C", destination, "fetch", "--depth", "1", "origin", spec["revision"]])
        self._run(["git", "-C", destination, "checkout", "--detach", "FETCH_HEAD"])

    def _versions(self):
        code = """import importlib.metadata as m,json,torch
names=('torch','torchvision','torchaudio','triton','comfy-kitchen','safetensors')
versions={}
for name in names:
    try: versions[name]=m.version(name)
    except m.PackageNotFoundError: pass
print(json.dumps({'packages':versions,'cuda':torch.version.cuda,'cuda_available':torch.cuda.is_available(),
 'gpu':torch.cuda.get_device_name(0) if torch.cuda.is_available() else None}))
"""
        return json.loads(subprocess.check_output([str(self.python), "-c", code], text=True).strip().splitlines()[-1])

    def install(self):
        if self._port_open():
            self._require_owned_server()
            marker = self._server_marker()
            if marker["signature"] != self._signature():
                raise RuntimeError("Stop this workspace's server before changing enabled extensions")
            return self.status()
        old = self._server_marker()
        identity = self._process_identity(old.get("pid")) if old else None
        if identity and identity == old.get("identity"):
            raise RuntimeError("Stop the existing workspace server before installing, including a server on another port")
        self.state.mkdir(parents=True, exist_ok=True)
        self._checkout(self.catalog["comfyui"], self.comfy)
        for name in self.extensions:
            spec = self.catalog["extensions"][name]
            self._checkout(spec, self.comfy / "custom_nodes" / spec["directory"])
        installed = self.state / "installed.json"
        if installed.exists() and json.loads(installed.read_text()).get("signature") == self._signature() and self.python.is_file():
            return json.loads(installed.read_text())
        # Colab exposes pip but can disable ensurepip. Keep its working GPU stack.
        self._run([sys.executable, "-m", "venv", "--system-site-packages", "--without-pip", self.root / "venv"])
        preserved = {}
        for distribution in importlib.metadata.distributions():
            name = distribution.metadata.get("Name", "").lower().replace("_", "-")
            if name in ("torch", "torchvision", "torchaudio", "triton") or name.startswith("nvidia-"):
                preserved[name] = distribution.version
        if "torch" not in preserved:
            raise RuntimeError("A preinstalled PyTorch/CUDA stack is required; use a standard Colab GPU runtime")
        constraints = [f"{name}=={version}" for name, version in sorted(preserved.items())]
        constraint_file = self.state / "gpu-constraints.txt"
        constraint_file.write_text("\n".join(constraints) + "\n")
        requirements = [item for name in self.extensions for item in self.catalog["extensions"][name]["requirements"]]
        self._run([self.python, "-m", "pip", "install", "--disable-pip-version-check", "-c", constraint_file,
                   "-r", self.comfy / "requirements.txt", *requirements])
        versions = self._versions()
        if any(versions["packages"].get(name) != version for name, version in preserved.items()
               if name in versions["packages"]):
            raise RuntimeError("The effective GPU stack changed; restart with a compatible runtime")
        freeze = subprocess.check_output([str(self.python), "-m", "pip", "freeze"], text=True)
        (self.state / "versions.txt").write_text(freeze)
        result = {"signature": self._signature(), "plan": self.plan(), "environment": versions,
                  "gpu_generation": "not_run"}
        write_json(installed, result)
        return result

    def _preflight_bundle(self, bundle):
        code = """import json,torch
assert torch.cuda.is_available(), 'Model bundles require a CUDA GPU'
p=torch.cuda.get_device_properties(0)
result={'gpu':p.name,'vram_bytes':p.total_memory,'capability':list(torch.cuda.get_device_capability())}
"""
        if bundle == "h3-ref2va-vsa":
            code += """assert p.major >= 8 and p.total_memory >= 22*2**30, 'Ref2VA-VSA needs a 24 GB class NVIDIA Ampere+ GPU'
import comfy_kitchen as ck
from comfy_kitchen.backends import cuda
assert cuda._EXT_AVAILABLE, str(cuda._EXT_ERROR)
q=torch.randn(1,256,4,128,device='cuda',dtype=torch.bfloat16)
with ck.use_backend('cuda'):
    out=ck.sol_attn(q,torch.randn_like(q),torch.randn_like(q),topk_ratio=0.25,tail=False,
      sink_blocks=[0,1],sink_q=[0,1],block_len=torch.full((4,),64,device='cuda',dtype=torch.int32),
      coarse_gate=torch.zeros_like(q))
assert out.shape==q.shape and torch.isfinite(out).all(), 'Sol CUDA kernel probe failed'
torch.cuda.synchronize()
result['sol_kernel']='pass'
"""
        code += "print(json.dumps(result))\n"
        self.state.mkdir(parents=True, exist_ok=True)
        probe = subprocess.run([str(self.python), "-c", code], capture_output=True, text=True)
        (self.state / "model-preflight.log").write_text(probe.stdout + probe.stderr)
        if probe.returncode:
            raise RuntimeError(f"Model hardware/kernel preflight failed before downloads; see {self.state / 'model-preflight.log'}")
        result = json.loads(probe.stdout.strip().splitlines()[-1])
        write_json(self.state / "model-preflight.json", {"bundle": bundle, **result})
        return result

    def download_models(self, bundle="none"):
        selected = self._bundle(bundle)
        if not selected["assets"]:
            return {"bundle": bundle, "downloaded": [], "status": "no_models_requested"}
        if self._port_open():
            raise RuntimeError("Stop the ComfyUI server before downloading models, then start it to refresh model lists")
        installed = self.state / "installed.json"
        if (not installed.is_file() or not self.python.is_file()
                or json.loads(installed.read_text()).get("signature") != self._signature()):
            raise RuntimeError("Install the workspace before downloading models")
        self._preflight_bundle(bundle)
        assets = [self.catalog["assets"][key] for key in selected["assets"]]
        missing_bytes = sum(item["size"] for item in assets if not model_path(self.comfy / "models", item["destination"]).exists())
        if shutil.disk_usage(self.root).free < missing_bytes + 2 * 2**30:
            raise RuntimeError("Insufficient disk for the selected weights plus 2 GiB headroom")
        paths = []
        for item in assets:
            print("Model:", item["destination"], flush=True)
            path = download_asset(item, model_path(self.comfy / "models", item["destination"]))
            paths.append(str(path))
            write_json(self.state / "download-progress.json", {"bundle": bundle, "verified_paths": paths})
        result = {"bundle": bundle, "status": "verified", "paths": paths,
                  "assets": assets, "gpu_generation": "not_run"}
        write_json(self.state / (bundle + "-models.json"), result)
        return result

    def stage_workflows(self):
        from comfyui_workflows import export
        return [str(path) for path in export(self.root / "workflows", presets=[
            key for key, spec in self.catalog["bundles"].items()
            if key != "none" and set(spec["extensions"]).issubset(self.extensions)])]

    def _port_open(self):
        try:
            with socket.create_connection(("127.0.0.1", self.port), timeout=1):
                return True
        except OSError:
            return False

    def _server_marker(self):
        marker = self.state / "server.json"
        return json.loads(marker.read_text()) if marker.exists() else {}

    @staticmethod
    def _process_identity(pid):
        # Linux /proc start time prevents a stale PID from owning another server.
        try:
            process = Path("/proc") / str(int(pid))
            stat = (process / "stat").read_text().rsplit(")", 1)[1].split()
            if stat[0] == "Z":
                return None
            return {"start_ticks": stat[19], "command": (process / "cmdline").read_bytes().decode().rstrip("\0").split("\0")}
        except (OSError, ValueError, TypeError):
            return None

    def _require_owned_server(self):
        marker = self._server_marker()
        identity = self._process_identity(marker.get("pid"))
        if (not identity or identity != marker.get("identity") or marker.get("port") != self.port
                or marker.get("command") != identity["command"]
                or str(self.comfy / "main.py") not in identity["command"]):
            raise RuntimeError("The port/process is not owned by this workspace; use another port/root")
        return marker

    def start(self, timeout=180):
        if timeout <= 0:
            raise ValueError("Startup timeout must be positive")
        if self._port_open():
            marker = self._require_owned_server()
            if marker["signature"] != self._signature():
                raise RuntimeError("Stop the server before changing enabled extensions")
            return self._ready()
        old = self._server_marker()
        identity = self._process_identity(old.get("pid")) if old else None
        if identity and identity == old.get("identity"):
            raise RuntimeError("The owned server is still starting or unhealthy; inspect server.log before restarting")
        installed = self.state / "installed.json"
        if not installed.exists() or json.loads(installed.read_text()).get("signature") != self._signature():
            raise RuntimeError("Install the selected workspace/extensions before starting")
        directories = [self.catalog["extensions"][name]["directory"] for name in self.extensions]
        command = [str(self.python), str(self.comfy / "main.py"), "--listen", "127.0.0.1", "--port", str(self.port),
                   "--disable-auto-launch", "--disable-comfy-compiler", "--use-pytorch-cross-attention",
                   "--disable-all-custom-nodes"]
        if directories:
            command += ["--whitelist-custom-nodes", *directories]
        with (self.state / "server.log").open("a") as log:
            self.server = subprocess.Popen(command, cwd=self.comfy, stdout=log, stderr=subprocess.STDOUT,
                                           start_new_session=True)
        identity = self._process_identity(self.server.pid)
        if not identity:
            raise RuntimeError("Cannot verify the ComfyUI process; see server.log")
        write_json(self.state / "server.json", {"pid": self.server.pid, "port": self.port,
                    "command": command, "identity": identity, "signature": self._signature()})
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            if self.server.poll() is not None:
                raise RuntimeError("ComfyUI startup failed; see server.log")
            if self._port_open():
                try:
                    return self._ready()
                except OSError:
                    pass
            time.sleep(1)
        raise TimeoutError("ComfyUI is still starting; inspect status/server.log before retrying")

    def _ready(self):
        marker = self._require_owned_server()
        if marker["signature"] != self._signature():
            raise RuntimeError("Server extension selection differs; stop, install the selection and restart")
        schemas = self.client.object_info()
        expected = {node for name in self.extensions for node in self.catalog["extensions"][name]["expected_nodes"]}
        missing = expected - schemas.keys()
        if missing:
            raise RuntimeError(f"Custom nodes did not load: {sorted(missing)}; inspect server.log")
        write_json(self.state / "object-info.json", schemas)
        return {"server": "ready", "base_url": self.client.base_url, "extensions": list(self.extensions),
                "node_count": len(schemas), "gpu_generation": "not_run"}

    def status(self):
        if not self._port_open():
            marker = self._server_marker()
            identity = self._process_identity(marker.get("pid")) if marker else None
            alive = bool(identity and identity == marker.get("identity"))
            return {"server": "starting_or_unhealthy" if alive else "stopped", "root": str(self.root)}
        result = self._ready()
        result["queue"] = self.client.get_json("/queue")
        return result

    def stop(self):
        marker = self._server_marker()
        if not marker or self._process_identity(marker.get("pid")) is None:
            return {"server": "stopped", "colab_runtime": "unchanged"}
        marker = self._require_owned_server()
        os.kill(marker["pid"], signal.SIGTERM)
        if self.server is not None:
            self.server.wait(timeout=30)
        deadline = time.monotonic() + 30
        while self._process_identity(marker["pid"]) == marker["identity"]:
            if time.monotonic() >= deadline:
                raise TimeoutError("ComfyUI has not stopped; inspect status before downloading or restarting")
            time.sleep(0.25)
        return {"server": "stopped", "colab_runtime": "unchanged"}

    def run_api(self, workflow_path, timeout=1800):
        if timeout <= 0:
            raise ValueError("Execution timeout must be positive")
        graph = json.loads(Path(workflow_path).read_text())
        if not isinstance(graph, dict) or "nodes" in graph or not graph:
            raise ValueError("Use a ComfyUI API graph, not a UI workflow export")
        from comfyui_workflows import validate_attention
        validate_attention(graph)
        marker = self._require_owned_server()
        if marker["signature"] != self._signature():
            raise RuntimeError("Server extension selection differs; stop, install the selection and restart")
        self.client.validate_graph(graph)
        identity = str(uuid.uuid4())
        run_dir = self.root / "runs" / identity
        run_dir.mkdir(parents=True)
        write_json(run_dir / "workflow.api.json", graph)
        receipt = {"prompt_id": identity, "status": "submitting", "run_dir": str(run_dir),
                   "catalog": self.catalog, "media_validation": "not_run", "content_review": "not_run"}
        write_json(run_dir / "receipt.json", receipt)
        try:
            response = self.client.queue_prompt(graph, prompt_id=identity)
            if response["prompt_id"] != identity:
                raise RuntimeError("ComfyUI returned a different prompt identity; inspect queue/history")
            receipt["status"] = "queued"
            write_json(run_dir / "receipt.json", receipt)
            history = self.client.wait_prompt(identity, timeout=timeout)
            write_json(run_dir / "history.json", history)
            receipt.update(status="execution_complete", outputs=history.get("outputs", {}))
        except PromptExecutionError as error:
            write_json(run_dir / "history.json", error.history)
            receipt.update(status="execution_failed", error_type=type(error).__name__)
            raise
        except PromptTimeoutError:
            receipt["status"] = "timeout_may_be_running"
            raise
        except Exception as error:
            receipt.update(status="submission_or_connection_unknown", error_type=type(error).__name__)
            raise
        finally:
            write_json(run_dir / "receipt.json", receipt)
            print("Receipt:", run_dir / "receipt.json", "Prompt:", identity, flush=True)
        return receipt


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("plan", "install", "download", "start", "status", "stop", "run", "workflows"))
    parser.add_argument("--root", type=Path, default=Path("/content/comfyui-workspace"))
    parser.add_argument("--port", type=int, default=8190)
    parser.add_argument("--extensions", default=",".join(DEFAULT_EXTENSIONS))
    parser.add_argument("--bundle", default="none", choices=tuple(load_catalog()["bundles"]))
    parser.add_argument("--workflow", type=Path)
    parser.add_argument("--timeout", type=int, default=1800)
    args = parser.parse_args()
    workspace = ComfyWorkspace(args.root, args.port, args.extensions)
    if args.command == "run" and args.workflow is None:
        parser.error("run requires --workflow")
    actions = {"plan": lambda: workspace.plan(args.bundle), "install": workspace.install,
               "download": lambda: workspace.download_models(args.bundle), "start": workspace.start,
               "status": workspace.status, "stop": workspace.stop,
               "run": lambda: workspace.run_api(args.workflow, args.timeout), "workflows": workspace.stage_workflows}
    print(json.dumps(actions[args.command](), indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
