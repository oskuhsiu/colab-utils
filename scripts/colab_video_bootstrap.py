#!/usr/bin/env python3
"""Prepare an Omni project, then detach setup -> its original first-shot adapter.

No command allocates a Colab VM. prepare/inspect are offline; launch/run require a
fresh allocation admission and a deadline from the external budget controller.
Re-entry reconciles the original shot and never creates another prompt identity.
"""
from __future__ import annotations

import argparse
from contextlib import contextmanager
import datetime as dt
import fcntl
import hashlib
import importlib.util
import json
import math
import os
from pathlib import Path, PurePosixPath
import re
import runpy
import shutil
import stat
import subprocess
import sys
import tempfile
import threading
import time
import zipfile


TOOLKIT = ("comfyui_workspace.py", "comfyui_assets.py", "comfyui_environment.py",
           "comfyui_workflows.py", "fast_h3_client.py", "comfyui_catalog.json",
           "colab_video_bootstrap.py")
ADAPTER = ("common.py", "run_shot.py", "status.py")


def now():
    return dt.datetime.now(dt.timezone.utc).isoformat()


def digest(path):
    value = hashlib.sha256()
    with Path(path).open("rb") as source:
        for block in iter(lambda: source.read(8 * 1024 * 1024), b""):
            value.update(block)
    return value.hexdigest()


def write_json(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(prefix="." + path.name, dir=path.parent)
    try:
        with os.fdopen(fd, "w") as output:
            json.dump(value, output, indent=2, ensure_ascii=False)
            output.write("\n")
        os.replace(temporary, path)
    finally:
        Path(temporary).unlink(missing_ok=True)


def relative(value):
    if (not isinstance(value, str) or not value or "\\" in value
            or PurePosixPath(value).is_absolute()
            or any(part in ("", ".", "..") for part in value.split("/"))):
        raise ValueError("Package names must be relative POSIX paths")
    return value


def safe_id(value):
    if not isinstance(value, str) or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,79}", value):
        raise ValueError("Deployment and shot IDs must be filename-safe (1-80 characters)")
    return value


def read_json(path):
    return json.loads(Path(path).read_text())


def prepare(runtime, job_path, inputs, output, deployment_id=None, environment=None):
    """Compile the project's existing graph, verify every input, and seal a ZIP."""
    runtime, output = Path(runtime).resolve(), Path(output).resolve()
    job = read_json(job_path)
    identity = safe_id(deployment_id or job["shot_id"])
    safe_id(job["shot_id"])
    if set(inputs) != set(job["reference_images"]):
        raise ValueError("--input names must exactly match the first job's reference_images")
    if output.exists():
        raise FileExistsError("Use a new output directory; existing production packages are immutable")
    output.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="video-prepare-", dir=output.parent) as temporary:
        stage = Path(temporary)
        for name in ADAPTER:
            source = runtime / name
            compile(source.read_text(), str(source), "exec")
            (stage / "runtime").mkdir(exist_ok=True)
            shutil.copyfile(source, stage / "runtime" / name)
        toolkit = stage / "runtime/toolkit"
        toolkit.mkdir()
        for name in TOOLKIT:
            source = Path(__file__).with_name(name)
            if name.endswith(".py"):
                compile(source.read_text(), name, "exec")
            shutil.copyfile(source, toolkit / name)
        write_json(stage / "first-job.json", job)
        # A fresh interpreter prevents a project's 'common' module from sharing
        # globals with the control application. graph_for_job is the same adapter
        # that run_shot will use, with no GPU imports or network operations.
        code = ("import json,sys;sys.path.insert(0,sys.argv[1]);import common;"
                "assert common.BUNDLE=='h3-omni-int8';"
                "job=json.load(open(sys.argv[2]));print(json.dumps(common.graph_for_job(job)))")
        graph = json.loads(subprocess.check_output(
            [sys.executable, "-c", code, str(stage / "runtime"), str(stage / "first-job.json")],
            text=True, timeout=30))
        write_json(stage / "workflow.api.json", graph)
        for name, source in inputs.items():
            target = stage / "inputs" / relative(name)
            target.parent.mkdir(parents=True, exist_ok=True)
            source = Path(source)
            if not source.is_file() or source.stat().st_size == 0:
                raise FileNotFoundError(f"Missing or empty input: {name}")
            shutil.copyfile(source, target)
        if environment is not None:
            # inspect validates every source/wheel before it enters the package.
            from comfyui_environment import inspect_environment
            inspect_environment(environment)
            shutil.copytree(environment, stage / "environment", symlinks=False)
        files = {}
        for path in sorted(stage.rglob("*")):
            if path.is_file():
                name = path.relative_to(stage).as_posix()
                if "__pycache__" in path.parts:
                    continue
                files[name] = {"bytes": path.stat().st_size, "sha256": digest(path),
                               "mode": stat.S_IMODE(path.stat().st_mode)}
        manifest = {"schema_version": 1, "deployment_id": identity,
                    "first_shot_id": job["shot_id"], "model_bundle": "h3-omni-int8",
                    "gpu": "A100", "machine_shape": "STANDARD", "high_mem": False,
                    "environment_mode": "offline" if environment is not None else "online",
                    "files": files}
        write_json(stage / "deployment.json", manifest)
        output.mkdir()
        with zipfile.ZipFile(output / "deployment.zip", "w", zipfile.ZIP_DEFLATED) as archive:
            for name in ["deployment.json", *files]:
                archive.write(stage / name, name)
        shutil.copyfile(Path(__file__), output / "bootstrap.py")
        plan = {**manifest, "package_sha256": digest(output / "deployment.zip"),
                "package_bytes": (output / "deployment.zip").stat().st_size,
                "recommended_root": "/content/video-" + identity,
                "gpu_generation": "not_run"}
        write_json(output / "plan.json", plan)
    return plan


def inspect_package(package):
    with zipfile.ZipFile(package) as archive:
        names = archive.namelist()
        if len(names) != len(set(names)):
            raise ValueError("Duplicate package entries")
        for item in archive.infolist():
            relative(item.filename)
            if stat.S_ISLNK(item.external_attr >> 16):
                raise ValueError("Package symlinks are not supported")
        manifest = json.loads(archive.read("deployment.json"))
        if manifest.get("schema_version") != 1:
            raise ValueError("Unsupported deployment schema")
        safe_id(manifest["deployment_id"])
        safe_id(manifest["first_shot_id"])
        if (manifest["model_bundle"], manifest["gpu"], manifest["machine_shape"]) != (
                "h3-omni-int8", "A100", "STANDARD") or manifest["high_mem"] is not False:
            raise ValueError("This bootstrap uses native Omni on A100 STANDARD, high_mem=false")
        if set(names) != {"deployment.json", *manifest["files"]}:
            raise ValueError("Package inventory differs from manifest")
        required = {"first-job.json", "workflow.api.json", *("runtime/" + name for name in ADAPTER),
                    *("runtime/toolkit/" + name for name in TOOLKIT)}
        if not required.issubset(manifest["files"]):
            raise ValueError("Package is missing the project adapter or toolkit")
        for name, expected in manifest["files"].items():
            value, size = hashlib.sha256(), 0
            with archive.open(name) as source:
                for block in iter(lambda: source.read(8 * 1024 * 1024), b""):
                    value.update(block)
                    size += len(block)
            if size != expected["bytes"] or value.hexdigest() != expected["sha256"]:
                raise ValueError(f"Package integrity failed: {name}")
        return manifest


def restore_package(package, root):
    manifest, root = inspect_package(package), Path(root).resolve()
    with zipfile.ZipFile(package) as archive:
        # Check all conflicts before the first write, including changed manifests.
        for name in archive.namelist():
            target = root / name
            if not target.resolve().is_relative_to(root) or target.is_symlink():
                raise ValueError("Restoration leaves the deployment root")
            if target.exists():
                expected = manifest["files"].get(name)
                if name == "deployment.json":
                    equal = read_json(target) == manifest
                else:
                    equal = target.is_file() and digest(target) == expected["sha256"]
                if not equal:
                    raise FileExistsError(f"Existing deployment differs: {name}")
        for name in archive.namelist():
            target = root / name
            if not target.exists():
                target.parent.mkdir(parents=True, exist_ok=True)
                fd, temporary = tempfile.mkstemp(prefix=".restore-", dir=target.parent)
                try:
                    with archive.open(name) as source, os.fdopen(fd, "wb") as destination:
                        shutil.copyfileobj(source, destination)
                        destination.flush()
                        os.fsync(destination.fileno())
                    if name != "deployment.json":
                        expected = manifest["files"][name]
                        if digest(temporary) != expected["sha256"]:
                            raise ValueError("Restored file integrity failed: " + name)
                        Path(temporary).chmod(expected["mode"])
                    # An interruption never leaves a partial file at the final
                    # name. link also preserves a concurrent different file.
                    os.link(temporary, target)
                finally:
                    Path(temporary).unlink(missing_ok=True)
    return manifest


@contextmanager
def exclusive(path):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a+") as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            raise RuntimeError("Original worker owns this deployment; read status instead") from None
        try:
            yield
        finally:
            fcntl.flock(lock, fcntl.LOCK_UN)


def process_identity(pid):
    try:
        base = Path("/proc") / str(int(pid))
        data = (base / "stat").read_text().rsplit(")", 1)[1].split()
        if data[0] == "Z":
            return None
        return {"start_ticks": data[19], "command": (base / "cmdline").read_bytes().decode().split("\0")}
    except (OSError, ValueError, TypeError):
        return None


def admission_check(admission, fresh=False):
    if (admission.get("accelerator"), admission.get("machine_shape")) != (
            "A100", "STANDARD") or admission.get("high_mem") is not False:
        raise ValueError("Allocation admission must confirm A100 STANDARD, high_mem=false")
    if not isinstance(admission.get("endpoint"), str) or not admission["endpoint"]:
        raise ValueError("Exact allocated endpoint is required")
    observed = admission.get("observed_epoch")
    if type(observed) not in (int, float) or not math.isfinite(observed):
        raise ValueError("A timestamped official allocation observation is required")
    if fresh and not -30 <= time.time() - observed <= 90:
        raise ValueError("Allocation admission is stale; refresh the original endpoint and budget")
    end = dt.datetime.fromisoformat(admission["deadline_utc"].replace("Z", "+00:00"))
    if end.tzinfo is None:
        raise ValueError("deadline_utc must include timezone")
    remaining = (end - dt.datetime.now(dt.timezone.utc)).total_seconds()
    if remaining <= 0:
        raise TimeoutError("Deployment deadline reached; no new work")
    reserve = admission.get("completion_reserve_seconds")
    if type(reserve) not in (int, float) or not math.isfinite(reserve) or reserve <= 0:
        raise ValueError("A positive full generation/save reserve is required")
    return remaining


def launch(package, root, admission_path):
    admission = read_json(admission_path)
    admission_check(admission, fresh=True)
    root = Path(root).resolve()
    with exclusive(root / ".launch.lock"):
        manifest = restore_package(package, root)
        previous = root / "allocation.json"
        if previous.exists() and read_json(previous)["endpoint"] != admission["endpoint"]:
            raise RuntimeError("Deployment belongs to another allocation; use a new root")
        marker = root / "worker.json"
        if marker.exists():
            original = read_json(marker)
            if original.get("identity") and process_identity(original["pid"]) == original["identity"]:
                return {**original, "status": "already_running"}
        write_json(previous, admission)
        with (root / "worker.log").open("a") as log:
            command = [sys.executable, "-u", str(root / "runtime/toolkit/colab_video_bootstrap.py"),
                       "run", "--root", str(root)]
            child = subprocess.Popen(command, stdout=log, stderr=subprocess.STDOUT,
                                     stdin=subprocess.DEVNULL, start_new_session=True)
        info = {"pid": child.pid, "identity": process_identity(child.pid), "started_utc": now(),
                "deployment_id": manifest["deployment_id"], "log": str(root / "worker.log")}
        write_json(marker, info)
        return {**info, "status": "launched"}


def bind_adapter(root):
    root = Path(root).resolve()
    runtime = root / "runtime"
    sys.path.insert(0, str(runtime / "toolkit"))
    sys.path.insert(0, str(runtime))
    spec = importlib.util.spec_from_file_location("common", runtime / "common.py")
    adapter = importlib.util.module_from_spec(spec)
    sys.modules["common"] = adapter
    spec.loader.exec_module(adapter)
    adapter.PRODUCTION = root / "production"
    adapter.WORKSPACE = root / "workspace"
    adapter.PORT = 8190
    return adapter


def install_submission_guard(adapter, admission, post_marker=None):
    original = adapter.workspace
    def workspace():
        ws = original()
        def check(prompt_id):
            if admission_check(admission) < admission["completion_reserve_seconds"]:
                raise TimeoutError("Insufficient full generation/save reserve immediately before POST")
            if post_marker is not None:
                write_json(post_marker, {"prompt_id": prompt_id, "post_started_utc": now()})
        ws.client.before_submit = check
        return ws
    adapter.workspace = workspace


def ensure_result_package(adapter, directory, receipt):
    """Publish/recover the ZIP from already verified files, without a server."""
    identity = directory.name
    results = adapter.PRODUCTION / "results"
    results.mkdir(exist_ok=True)
    target, marker = results / (identity + ".zip"), results / (identity + ".package.json")
    if marker.exists():
        saved = read_json(marker)
        if (saved["prompt_id"] == receipt["prompt_id"] and target.is_file()
                and target.stat().st_size == saved["bytes"] and digest(target) == saved["sha256"]):
            return saved
        raise RuntimeError("Published result package differs from its receipt; preserve for inspection")
    if target.exists():
        # Native finish() may already have published it before an interruption.
        with zipfile.ZipFile(target) as archive:
            if (json.loads(archive.read(identity + "/job.json")) != read_json(directory / "job.json")
                    or json.loads(archive.read(identity + "/receipt.json")) != receipt
                    or hashlib.sha256(archive.read(identity + "/media.mp4")).hexdigest() != receipt["media_sha256"]
                    or archive.testzip() is not None):
                raise RuntimeError("Existing result ZIP differs from the original shot")
    else:
        fd, temporary = tempfile.mkstemp(prefix=".result-", suffix=".zip", dir=results)
        os.close(fd)
        try:
            with zipfile.ZipFile(temporary, "w", zipfile.ZIP_DEFLATED) as archive:
                for path in sorted(directory.rglob("*")):
                    if path.is_file():
                        archive.write(path, (Path(identity) / path.relative_to(directory)).as_posix())
                for path in sorted((adapter.PRODUCTION / "state").glob("*")):
                    if path.is_file() and path.suffix in (".json", ".txt", ".log"):
                        archive.write(path, "setup-evidence/" + path.name)
                for name in ("hardware.json", "plan.json"):
                    path = adapter.PRODUCTION / name
                    if path.is_file():
                        archive.write(path, "setup-evidence/" + name)
            os.link(temporary, target)
        finally:
            Path(temporary).unlink(missing_ok=True)
    saved = {"shot_id": identity, "prompt_id": receipt["prompt_id"], "path": str(target),
             "bytes": target.stat().st_size, "sha256": digest(target), "published_utc": now()}
    write_json(marker, saved)
    return saved


def reconcile(adapter, manifest, admission, wait=False):
    """Use the existing shot ID/receipt. No branch in this function submits."""
    directory = adapter.PRODUCTION / "shots" / manifest["first_shot_id"]
    receipt = read_json(directory / "receipt.json")
    if read_json(directory / "job.json") != read_json(adapter.PRODUCTION.parent / "first-job.json"):
        raise RuntimeError("Existing shot differs from the sealed first job")
    if receipt["status"] == "complete_media_verified":
        media = directory / "media.mp4"
        if media.stat().st_size != receipt["media_bytes"] or digest(media) != receipt["media_sha256"]:
            raise RuntimeError("Saved first-shot media differs from its receipt")
        return {**receipt, "result_package": ensure_result_package(adapter, directory, receipt)}
    ws = adapter.workspace()
    if ws.status()["server"] != "ready":
        raise RuntimeError("needs_reconcile: original server unavailable; nothing restarted or resubmitted")
    identity = receipt["prompt_id"]
    history = ws.client.get_json("/history/" + identity).get(identity)
    if history and history.get("status", {}).get("completed") is True:
        if history["status"].get("status_str") != "success":
            raise RuntimeError("Original prompt failed; a new take requires an explicit new job")
        adapter.finish(ws, directory, history)
        return reconcile(adapter, manifest, admission)
    queue = ws.client.get_json("/queue")
    present = any(len(entry) > 1 and str(entry[1]) == identity
                  for key in ("queue_running", "queue_pending") for entry in queue.get(key, []))
    if not present:
        raise RuntimeError("needs_reconcile: no original prompt in queue/history; nothing resubmitted")
    if wait:
        left = admission_check(admission)
        history = ws.client.wait_prompt(identity, timeout=left)
        adapter.finish(ws, directory, history)
        return reconcile(adapter, manifest, admission)
    return {**receipt, "observed_state": "original_prompt_active"}


class Progress:
    def __init__(self, root, admission):
        self.root, self.admission = Path(root), admission
        self.phase_started = time.monotonic()
        self.value = {"status": "starting", "started_utc": now(), "phases": {}}
        self.stopped = threading.Event()

    def phase(self, name):
        if name != "complete_media_verified":
            admission_check(self.admission)
        current = self.value["status"]
        self.value["phases"].setdefault(current, {})["seconds"] = round(time.monotonic() - self.phase_started, 3)
        self.phase_started = time.monotonic()
        self.value.update(status=name, updated_utc=now())
        self.value["phases"][name] = {"started_utc": now()}
        write_json(self.root / "progress.json", self.value)
        with (self.root / "events.jsonl").open("a") as log:
            log.write(json.dumps({"utc": now(), "event": name}) + "\n")
        print("VIDEO_BOOTSTRAP_PHASE", name, flush=True)

    def heartbeat(self):
        # Liveness is separate from phase progress or GPU utilization.
        while not self.stopped.wait(15):
            write_json(self.root / "heartbeat.json", {"utc": now(), "pid": os.getpid(),
                       "phase": self.value["status"], "phase_elapsed_seconds": round(time.monotonic() - self.phase_started, 1)})


def run_pipeline(root):
    root = Path(root).resolve()
    with exclusive(root / ".worker.lock"):
        manifest, admission = read_json(root / "deployment.json"), read_json(root / "allocation.json")
        admission_check(admission)
        progress = Progress(root, admission)
        heartbeat = threading.Thread(target=progress.heartbeat, daemon=True)
        heartbeat.start()
        try:
            # Check the extracted inventory again before executing project code.
            for name, expected in manifest["files"].items():
                if digest(root / name) != expected["sha256"]:
                    raise RuntimeError(f"Restored package differs: {name}")
            adapter = bind_adapter(root)
            install_submission_guard(adapter, admission, root / "first-post.json")
            adapter.PRODUCTION.mkdir(parents=True, exist_ok=True)
            job = read_json(root / "first-job.json")
            graph = adapter.graph_for_job(job)
            if graph != read_json(root / "workflow.api.json"):
                raise RuntimeError("Project adapter graph differs from the prepared graph")
            shot = adapter.PRODUCTION / "shots" / manifest["first_shot_id"]
            if shot.exists():
                progress.phase("reconciling_original_shot")
                result = reconcile(adapter, manifest, admission, wait=True)
            else:
                progress.phase("hardware_preflight")
                adapter.hardware()
                if not shutil.which("ffmpeg") or not shutil.which("ffprobe"):
                    raise RuntimeError("ffmpeg and ffprobe must already be installed")
                ws = adapter.workspace()
                write_json(adapter.PRODUCTION / "plan.json", ws.plan("h3-omni-int8"))
                state = ws.status()["server"]
                if state == "starting_or_unhealthy":
                    raise RuntimeError("Original server is starting/unhealthy; inspect before any restart")
                if state == "ready":
                    models = read_json(ws.state / "h3-omni-int8-models.json")
                    if models["status"] != "verified" or models["assets"] != ws.plan("h3-omni-int8")["assets"]:
                        raise RuntimeError("Running server has no matching verified model evidence")
                    progress.phase("reusing_ready_server")
                else:
                    progress.phase("restoring_environment" if manifest["environment_mode"] == "offline" else "installing")
                    ws.install(environment=root / "environment" if manifest["environment_mode"] == "offline" else None)
                # Stage after checkout, including the ready-server path. These are
                # exact sealed input names; no upload or controller round trip.
                for name in job["reference_images"]:
                    target = ws.comfy / "input" / relative(name)
                    source = root / "inputs" / name
                    if not target.resolve().is_relative_to((ws.comfy / "input").resolve()):
                        raise ValueError("Reference destination leaves ComfyUI/input")
                    if target.exists() and digest(target) != digest(source):
                        raise FileExistsError("Existing reference differs: " + name)
                    if not target.exists():
                        target.parent.mkdir(parents=True, exist_ok=True)
                        shutil.copyfile(source, target)
                if state != "ready":
                    progress.phase("downloading_models")
                    ws.download_models("h3-omni-int8", backend="hf", max_workers=2)
                    progress.phase("starting_server")
                    ws.start(timeout=min(240, admission_check(admission)))
                progress.phase("server_ready")
                ready_at = now()
                if admission_check(admission) < admission["completion_reserve_seconds"]:
                    raise TimeoutError("Insufficient time for full first-shot generation/save and stop reserve")
                progress.phase("first_shot")
                previous_argv = sys.argv
                try:
                    sys.argv = [str(root / "runtime/run_shot.py"), "--job", str(root / "first-job.json"),
                                "--deadline-utc", admission["deadline_utc"]]
                    runpy.run_path(sys.argv[0], run_name="__main__")
                finally:
                    sys.argv = previous_argv
                result = read_json(shot / "receipt.json")
                if result["status"] != "complete_media_verified":
                    raise RuntimeError("First-shot adapter returned without verified media; inspect original receipt")
                result["result_package"] = ensure_result_package(adapter, shot, result)
                progress.value["server_ready_utc"] = ready_at
                submitted_at = (read_json(root / "first-post.json")["post_started_utc"]
                                if (root / "first-post.json").is_file() else result["submitted_utc"])
                progress.value["ready_to_submission_seconds"] = (
                    dt.datetime.fromisoformat(submitted_at) - dt.datetime.fromisoformat(ready_at)).total_seconds()
                allocated = admission.get("allocation_started_epoch")
                if type(allocated) in (int, float) and math.isfinite(allocated):
                    progress.value["allocation_to_submission_seconds"] = (
                        dt.datetime.fromisoformat(submitted_at).timestamp() - allocated)
            progress.phase("complete_media_verified")
            progress.value.update(prompt_id=result["prompt_id"], content_review="not_run",
                                  receipt=str(shot / "receipt.json"), result_package=result["result_package"],
                                  completed_utc=now())
            write_json(root / "progress.json", progress.value)
            return progress.value
        except BaseException as error:
            progress.value.update(status="stopped_needs_inspection", error_type=type(error).__name__,
                                  updated_utc=now(), colab_allocation="unchanged; external guard must release")
            write_json(root / "progress.json", progress.value)
            raise
        finally:
            progress.stopped.set()
            heartbeat.join(timeout=1)


def status(root):
    root = Path(root).resolve()
    result = {"root": str(root), "colab_allocation": "not_queried"}
    for name in ("deployment.json", "worker.json", "progress.json", "heartbeat.json", "first-post.json"):
        if (root / name).is_file():
            result[name.removesuffix(".json")] = read_json(root / name)
    manifest = result.get("deployment")
    if manifest:
        receipt = root / "production/shots" / manifest["first_shot_id"] / "receipt.json"
        if receipt.is_file():
            result["first_shot"] = read_json(receipt)
        download = root / "production/state/download-progress.json"
        if download.is_file():
            result["download"] = read_json(download)
        # The inventory is useful to inspect once, not on each control heartbeat.
        result["deployment"].pop("files", None)
    worker = result.get("worker", {})
    result["worker_alive"] = bool(worker.get("identity") and process_identity(worker.get("pid")) == worker["identity"])
    return result


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    p = sub.add_parser("prepare", help="Offline package; never allocate or generate")
    p.add_argument("--runtime", type=Path, required=True)
    p.add_argument("--job", type=Path, required=True)
    p.add_argument("--input", action="append", default=[], metavar="COMFY_NAME=LOCAL_FILE")
    p.add_argument("--output", type=Path, required=True)
    p.add_argument("--id")
    p.add_argument("--environment", type=Path)
    p = sub.add_parser("inspect", help="Verify sealed package without executing it")
    p.add_argument("--package", type=Path, required=True)
    p = sub.add_parser("launch", help="Detach setup -> original first-shot adapter on an existing VM")
    p.add_argument("--package", type=Path, required=True)
    p.add_argument("--root", type=Path, required=True)
    p.add_argument("--admission", type=Path, required=True)
    for name in ("run", "status", "fetch"):
        p = sub.add_parser(name)
        p.add_argument("--root", type=Path, required=True)
    args = parser.parse_args(argv)
    if args.command == "prepare":
        inputs = {}
        for item in args.input:
            name, separator, path = item.partition("=")
            if not separator or name in inputs:
                parser.error("Each --input must be a distinct COMFY_NAME=LOCAL_FILE")
            inputs[relative(name)] = path
        result = prepare(args.runtime, args.job, inputs, args.output, args.id, args.environment)
        result.pop("files", None)
    elif args.command == "inspect":
        result = inspect_package(args.package)
        result = {**result, "file_count": len(result["files"])}
        result.pop("files")
    elif args.command == "launch":
        result = launch(args.package, args.root, args.admission)
    elif args.command == "run":
        result = run_pipeline(args.root)
    elif args.command == "fetch":
        with exclusive(args.root / ".worker.lock"):
            result = reconcile(bind_adapter(args.root), read_json(args.root / "deployment.json"),
                               read_json(args.root / "allocation.json"), wait=False)
    else:
        result = status(args.root)
    print(json.dumps(result, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
