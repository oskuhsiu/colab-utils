#!/usr/bin/env python3
"""Bounded, no-render rehearsal on an already allocated Linux Colab VM.

No command allocates/releases a VM. Only installation, server GETs, and two
pinned VAE downloads are exercised. The external controller owns budget/release.
"""
from __future__ import annotations

import argparse
from contextlib import contextmanager
import fcntl
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import tempfile
import threading
import time

ASSETS = ("h3-audio-fp32", "h3-video-int8")
REQUIRED = ("comfyui_workspace.py", "comfyui_assets.py", "comfyui_environment.py",
            "comfyui_catalog.json", "fast_h3_client.py", "comfyui_workflows.py")


def write_json(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(prefix="." + path.name, dir=path.parent)
    try:
        with os.fdopen(fd, "w") as output:
            json.dump(value, output, indent=2)
            output.write("\n")
            output.flush()
            os.fsync(output.fileno())
        os.replace(temporary, path)
    finally:
        Path(temporary).unlink(missing_ok=True)


def read_json(path):
    try:
        return json.loads(Path(path).read_text())
    except FileNotFoundError:
        return None


def event(root, kind, **values):
    record = {"epoch": time.time(), "event": kind, **values}
    with (Path(root) / "events.jsonl").open("a") as output:
        output.write(json.dumps(record) + "\n")


def process_identity(pid, proc_root=Path("/proc")):
    if type(pid) is not int or pid <= 0:
        return None
    try:
        directory = Path(proc_root) / str(pid)
        stat = (directory / "stat").read_text().rsplit(") ", 1)[1].split()
        if stat[0] == "Z":
            return None
        return {"pid": pid, "start_ticks": int(stat[19]),
                "argv": (directory / "cmdline").read_bytes().decode(errors="replace").split("\0")[:-1]}
    except (FileNotFoundError, ProcessLookupError):
        return None


def terminate_owned(process, identity):
    """Never signal a reused PID or another process group."""
    current = process_identity(process.pid)
    if current is None:
        process.wait(timeout=5)
        return
    if current != identity or os.getpgid(process.pid) != process.pid:
        raise RuntimeError("Child identity changed; refusing to signal it")
    os.killpg(process.pid, signal.SIGTERM)
    try:
        process.wait(timeout=5)
    except subprocess.TimeoutExpired:
        if process_identity(process.pid) != identity:
            raise RuntimeError("Child identity changed before forced stop")
        os.killpg(process.pid, signal.SIGKILL)
        process.wait(timeout=5)


@contextmanager
def lock(path, nonblocking=False):
    with Path(path).open("a") as handle:
        fcntl.flock(handle, fcntl.LOCK_EX | (fcntl.LOCK_NB if nonblocking else 0))
        yield


def validate_paths(root, toolkit):
    root, toolkit = Path(root).resolve(), Path(toolkit).resolve()
    if root == Path("/") or root == toolkit or root in toolkit.parents:
        raise ValueError("Use a separate non-root probe directory")
    for name in REQUIRED:
        if not (toolkit / name).is_file():
            raise FileNotFoundError("Missing toolkit file: " + name)
    return root, toolkit


def snapshot(root):
    root = Path(root).resolve()
    owner = read_json(root / "worker.json")
    return {"root": str(root), "worker": owner,
            "worker_alive": bool(owner and process_identity(owner["pid"]) == owner["identity"]),
            "progress": read_json(root / "progress.json"),
            "heartbeat": read_json(root / "heartbeat.json"),
            "result": read_json(root / "result.json"),
            "download": read_json(root / "download-progress.json")}


def launch(root, toolkit, environment_rounds=False):
    root, toolkit = validate_paths(root, toolkit)
    root.mkdir(parents=True, exist_ok=True)
    with lock(root / ".launch.lock"):
        previous = read_json(root / "worker.json")
        if previous:
            current = process_identity(previous["pid"])
            if current == previous["identity"]:
                return {"status": "already_running", "pid": previous["pid"]}
            if current is not None:
                raise RuntimeError("Saved PID belongs to another process; inspect original state")
            if read_json(root / "result.json") is not None:
                return {"status": "already_finished", "result": read_json(root / "result.json")}
            raise RuntimeError("Original worker ended without result; inspect partial state before a new round")
        command = [sys.executable, str(Path(__file__).resolve()), "worker", "--root", str(root),
                   "--toolkit", str(toolkit)]
        if environment_rounds:
            command.append("--environment-rounds")
        with (root / "worker.log").open("a") as log:
            child = subprocess.Popen(command, stdin=subprocess.DEVNULL, stdout=log,
                                     stderr=subprocess.STDOUT, start_new_session=True)
        identity = process_identity(child.pid)
        if not identity:
            raise RuntimeError("Cannot identify launched worker; inspect worker.log")
        write_json(root / "worker.json", {"pid": child.pid, "identity": identity,
                                         "started_epoch": time.time(), "command": command})
        event(root, "worker_launched", identity=identity)
        return {"status": "launched", "pid": child.pid, "log": str(root / "worker.log")}


def network_rx():
    try:
        return sum(int(line.split(":", 1)[1].split()[0])
                   for line in Path("/proc/net/dev").read_text().splitlines()[2:]
                   if line.split(":", 1)[0].strip() != "lo")
    except (FileNotFoundError, ValueError):
        return None


def partial_inventory(cache):
    files = []
    for path in sorted(Path(cache).rglob("*.incomplete")):
        stat = path.stat()
        files.append({"path": str(path.relative_to(cache)), "bytes": stat.st_size,
                      "allocated_bytes": stat.st_blocks * 512, "mtime_ns": stat.st_mtime_ns})
    return files


class Probe:
    def __init__(self, root, toolkit):
        self.root, self.toolkit = validate_paths(root, toolkit)
        self.started = time.monotonic()
        self.deadline = self.started + 900
        self.timings = {}

    @contextmanager
    def phase(self, name):
        started, rx = time.monotonic(), network_rx()
        write_json(self.root / "progress.json", {"phase": name, "status": "running",
                   "epoch": time.time(), "timings": self.timings, "gpu_generation": "not_run"})
        event(self.root, "phase_started", phase=name)
        try:
            yield
        finally:
            end_rx = network_rx()
            self.timings[name] = {"seconds": round(time.monotonic() - started, 3),
                "network_rx_bytes": end_rx - rx if rx is not None and end_rx is not None else None}
            write_json(self.root / "timings.json", self.timings)
            event(self.root, "phase_finished", phase=name, **self.timings[name])

    def child(self, command, label, timeout=180, interrupt=False):
        remaining = self.deadline - time.monotonic()
        if remaining <= 1:
            raise TimeoutError("Probe total deadline reached")
        timeout = min(timeout, remaining)
        before = partial_inventory(self.root / "hf-cache")
        with (self.root / (label + ".log")).open("a") as log:
            process = subprocess.Popen(list(map(str, command)), stdin=subprocess.DEVNULL, stdout=log,
                                       stderr=subprocess.STDOUT, start_new_session=True)
            identity = process_identity(process.pid)
            if not identity:
                raise RuntimeError("Cannot identify probe child")
            write_json(self.root / "child.json", {"phase": label, "identity": identity})
            event(self.root, "child_started", phase=label, identity=identity)
            started, interrupted = time.monotonic(), False
            try:
                while process.poll() is None:
                    elapsed = time.monotonic() - started
                    partials = partial_inventory(self.root / "hf-cache")
                    if interrupt and (sum(p["allocated_bytes"] for p in partials) >= 64 * 2**20 or elapsed >= 45):
                        terminate_owned(process, identity)
                        interrupted = True
                        break
                    if elapsed >= timeout:
                        raise TimeoutError("Probe child deadline reached: " + label)
                    time.sleep(1)
            finally:
                if process.poll() is None:
                    terminate_owned(process, identity)
            result = {"exit_code": process.returncode, "interrupted": interrupted,
                      "before": before, "after": partial_inventory(self.root / "hf-cache")}
            write_json(self.root / (label + ".json"), result)
            event(self.root, "child_finished", phase=label, exit_code=process.returncode, interrupted=interrupted)
            if process.returncode and not interrupted:
                raise RuntimeError("Probe child failed; inspect " + label + ".log")
            return result

    def action(self, code, label, timeout=180):
        prefix = ("import sys,json;sys.path.insert(0," + repr(str(self.toolkit)) + ");"
                  "from comfyui_workspace import ComfyWorkspace;"
                  "w=ComfyWorkspace(" + repr(str(self.root / "workspace")) + ",port=8192,extensions=[]);"
                  "from fast_h3_client import ComfyClient;"
                  "ComfyClient.post_json=lambda *a,**k: (_ for _ in ()).throw(RuntimeError('No POST in preflight'));\n")
        return self.child([sys.executable, "-c", prefix + code], label, timeout)

    def downloads(self, label, model_root, interrupt=False):
        catalog = read_json(self.toolkit / "comfyui_catalog.json")
        spec = {"assets": [catalog["assets"][key] for key in ASSETS], "model_root": str(model_root),
                "cache_dir": str(self.root / "hf-cache"),
                "progress_path": str(self.root / "download-progress.json"), "max_workers": 2}
        spec_path = self.root / (label + "-spec.json")
        write_json(spec_path, spec)
        return self.child([self.root / "workspace/venv/bin/python", self.toolkit / "comfyui_assets.py",
                           "--spec", spec_path], label, 180, interrupt)

    def run(self, environment_rounds=False):
        with self.phase("install"):
            self.action("w.install()", "install", 240)
        with self.phase("install_reuse"):
            self.action("p=w.state/'installed.json';before=p.read_bytes();m=p.stat().st_mtime_ns;"
                        "w.install();assert p.read_bytes()==before and p.stat().st_mtime_ns==m", "install-reuse")
        with self.phase("server_start_and_reuse"):
            self.action("w.start(timeout=90);p=w._server_marker();w.start(timeout=15);"
                        "assert w._server_marker()==p;"
                        "q=w.client.get_json('/queue');h=w.client.get_json('/history');"
                        "assert not q.get('queue_running') and not q.get('queue_pending') and not h;"
                        "print(json.dumps({'server_identity':p,'queue_empty':True,'history_empty':True}));"
                        "w.stop()", "server-start-and-reuse", 150)
        models = self.root / "workspace/ComfyUI/models"
        with self.phase("download_interruption"):
            interruption = self.downloads("download-interruption", models, interrupt=True)
        with self.phase("download_restart"):
            self.downloads("download-restart", models)
        with self.phase("download_existing_reuse"):
            self.downloads("download-existing-reuse", models)
            progress = read_json(self.root / "download-progress.json")
            assert all(asset["reused"] for asset in progress["assets"])
        with self.phase("download_cache_republish"):
            other = self.root / "republished-models"
            self.downloads("download-cache-republish", other)
            catalog = read_json(self.toolkit / "comfyui_catalog.json")
            links = []
            for key in ASSETS:
                name = catalog["assets"][key]["destination"]
                first, second = (base / name for base in (models, other))
                a, b = first.stat(), second.stat()
                assert (a.st_dev, a.st_ino) == (b.st_dev, b.st_ino)
                links.append({"asset": key, "bytes": a.st_size, "same_inode": True, "links": a.st_nlink})
            write_json(self.root / "hardlinks.json", links)
        if environment_rounds:
            with self.phase("environment_build"):
                self.action("from comfyui_environment import build_environment;"
                            "build_environment(w," + repr(str(self.root / "environment")) + ")", "environment-build", 240)
            for index in (1, 2):
                with self.phase("environment_restore_" + str(index)):
                    self.action("from comfyui_environment import restore_environment;"
                                "r=ComfyWorkspace(" + repr(str(self.root / ("restore-" + str(index)))) + ",port=8193,extensions=[]);"
                                "restore_environment(r," + repr(str(self.root / "environment")) + ");"
                                "assert (r.state/'installed.json').is_file()", "environment-restore-" + str(index), 120)
        output_roots = (self.root / "workspace/ComfyUI/output", self.root / "workspace/runs")
        media = [str(path.relative_to(self.root)) for output in output_roots
                 for pattern in ("*.mp4", "*.webm", "*.mov") for path in output.rglob(pattern)]
        assert not media, "Unexpected media in no-render probe"
        return {"status": "passed", "gpu_generation": "not_run", "prompt_posts": 0,
                "media_files": media, "timings": self.timings, "download_interruption_injected": interruption["interrupted"],
                "partial_bytes_retained": sum(p["allocated_bytes"] for p in interruption["after"]),
                "cross_process_partial_reuse": "not_established", "completed_files_reuse": "verified",
                "environment_rounds": 2 if environment_rounds else 0,
                "limitations": ["No model loading or video inference was run", "Network RX includes control traffic",
                                "Restarting with the same cache does not establish cross-process byte resume; "
                                "only completed-file reuse was verified"]}


def worker(root, toolkit, environment_rounds=False):
    root, toolkit = validate_paths(root, toolkit)
    root.mkdir(parents=True, exist_ok=True)
    with lock(root / ".worker.lock", nonblocking=True):
        stop = threading.Event()
        def heartbeat():
            while not stop.is_set():
                write_json(root / "heartbeat.json", {"epoch": time.time(), "pid": os.getpid()})
                stop.wait(5)
        thread = threading.Thread(target=heartbeat, daemon=True)
        thread.start()
        probe = Probe(root, toolkit)
        try:
            result = probe.run(environment_rounds)
        except Exception as error:
            result = {"status": "failed", "error_type": type(error).__name__,
                      "timings": probe.timings, "gpu_generation": "not_run",
                      "detail": "Inspect last phase and its local log; no render retry was attempted"}
        finally:
            stop.set()
            thread.join(timeout=6)
        write_json(root / "result.json", result)
        event(root, "worker_finished", status=result["status"])
        write_json(root / "progress.json", {"phase": "finished", "status": result["status"],
                   "epoch": time.time(), "timings": probe.timings, "gpu_generation": "not_run"})
        return result


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("launch", "worker", "status", "snapshot"))
    parser.add_argument("--root", required=True, type=Path)
    parser.add_argument("--toolkit", type=Path, default=Path(__file__).resolve().parent)
    parser.add_argument("--environment-rounds", action="store_true")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args(argv)
    if args.command == "launch":
        result = launch(args.root, args.toolkit, args.environment_rounds)
    elif args.command == "worker":
        result = worker(args.root, args.toolkit, args.environment_rounds)
    else:
        result = snapshot(args.root)
    if args.output:
        write_json(args.output, result)
    else:
        print(json.dumps(result))
    return int(result.get("status") == "failed")


if __name__ == "__main__":
    raise SystemExit(main())
