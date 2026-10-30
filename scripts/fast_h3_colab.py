#!/usr/bin/env python3
"""Prepare, run and fetch the L4 FastH3 notebook/ComfyUI flows with Colab CLI."""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import threading
import zipfile

from export_cells import export_section
from fast_h3_runtime import sha256, verify_media
from fast_h3_workflow import DEFAULT_PROMPT, build_graph

ROOT = Path(__file__).resolve().parents[1]
FILES = ("fast_h3_runtime.py", "fast_h3_workflow.py", "fast_h3_client.py", "fast_h3_nodes.py", "fast_h3_lock.json")
REMOTE_ROOT = "/content/fast-h3"


def redact(text):
    text = re.sub(r"(https?://[^\s?#]+)\?[^\s]*", r"\1?[redacted]", text)
    return re.sub(r"(?i)(bearer\s+)[\w.-]+", r"\1[redacted]", text)


def cli(args, *command, timeout=60, quiet=False):
    result = subprocess.run(["colab", "--auth", args.auth, *map(str, command)],
                            capture_output=True, text=True, timeout=timeout)
    output = redact(result.stdout + result.stderr)
    if not quiet:
        print(output, end="", flush=True)
    if result.returncode:
        raise RuntimeError("Colab CLI failed: " + " ".join(map(str, command[:2])) + "\n" + output[-1500:])
    return output


def settings(args):
    config = {"prompt": DEFAULT_PROMPT, "width": 864, "height": 480,
              "duration_seconds": 5, "seed": 123456662, "loras": [],
              "run_name": "fast_h3_" + args.backend,
              "generation_mode": "t2va", "reference_paths": []}
    if args.config:
        supplied = json.loads(args.config.read_text())
        unknown = supplied.keys() - config.keys()
        if unknown:
            raise ValueError("Unknown configuration fields: " + ", ".join(sorted(unknown)))
        config.update(supplied)
    if not isinstance(config["reference_paths"], list):
        raise ValueError("reference_paths must be a JSON list")
    build_graph(config["prompt"], config["width"], config["height"], config["duration_seconds"],
                config["seed"], run_name=config["run_name"], generation_mode=config["generation_mode"],
                reference_images=[f"reference_{i}.png" for i in range(len(config["reference_paths"]))])
    for value in config["reference_paths"]:
        if not isinstance(value, str) or not Path(value).expanduser().is_file():
            raise ValueError("reference_paths must name existing host-local image files")
    if not isinstance(config["loras"], list):
        raise ValueError("loras must be a JSON list")
    return config


def prepare(args):
    args.output.mkdir(parents=True, exist_ok=True)
    config = settings(args)
    (args.output / "config.json").write_text(json.dumps(config, indent=2, ensure_ascii=False) + "\n")
    archive = args.output / "fast-h3-toolkit.zip"
    with zipfile.ZipFile(archive, "w", compression=zipfile.ZIP_DEFLATED) as bundle:
        for name in FILES:
            file = ROOT / "scripts" / name
            if name.endswith(".py"):
                compile(file.read_text(), name, "exec")
            bundle.write(file, name)
    graph = build_graph(config["prompt"], config["width"], config["height"], config["duration_seconds"],
                        config["seed"], run_name=config["run_name"], generation_mode=config["generation_mode"],
                        reference_images=[f"reference_{i}.png" for i in range(len(config["reference_paths"]))])
    (args.output / "prepared-workflow.api.json").write_text(json.dumps(graph, indent=2, ensure_ascii=False) + "\n")
    print(archive)
    return archive


def start(args):
    output = cli(args, "sessions")
    current = next((line for line in output.splitlines() if line.startswith(f"[{args.session}]")), None)
    if current:
        if "Hardware: L4" not in current:
            raise RuntimeError("Existing named session is not L4; refusing to reuse it")
        print("Reusing L4 session", args.session)
        return
    cli(args, "usage")
    cli(args, "new", "-s", args.session, "--gpu", "L4", timeout=180)


def refresh(args):
    executable = shutil.which("colab")
    if not executable:
        raise RuntimeError("Colab CLI is not installed")
    first_line = Path(executable).read_text().splitlines()[0]
    interpreter = first_line[2:].strip() if first_line.startswith("#!") else ""
    if not interpreter or " " in interpreter or not Path(interpreter).is_file():
        raise RuntimeError("Run refresh_fast_h3_session.py using the Python environment that installed Colab CLI")
    result = subprocess.run([interpreter, str(ROOT / "scripts/refresh_fast_h3_session.py"),
                             "--session", args.session, "--auth", args.auth],
                            capture_output=True, text=True, timeout=60)
    if result.returncode:
        raise RuntimeError("Proxy refresh failed; preserve the original session and reconcile")
    data = json.loads(result.stdout)
    args.output.mkdir(parents=True, exist_ok=True)
    (args.output / "proxy-refresh.json").write_text(json.dumps(data, indent=2) + "\n")
    print(json.dumps(data))


def pull_state(args):
    destination = args.output / "state"
    destination.mkdir(parents=True, exist_ok=True)
    for filename in ("progress.json", "telemetry.json", "action-result.json", "hardware.json",
                     "kernel-preflight.json", "kernel-preflight.log", "server.log", "install.log"):
        staging = destination / (filename + ".incoming")
        try:
            cli(args, "download", "-s", args.session, f"{REMOTE_ROOT}/state/{filename}", staging,
                timeout=40, quiet=True)
            staging.replace(destination / filename)
        except (RuntimeError, subprocess.TimeoutExpired):
            if staging.exists():
                staging.unlink()
    stamp = destination / "fetched-at.txt"
    stamp.write_text(datetime.now(timezone.utc).isoformat() + "\n")


def execute(args, source, label):
    args.output.mkdir(parents=True, exist_ok=True)
    script = args.output / (label + ".py")
    # Colab CLI can return zero after a remote Python exception. The action-result
    # file is rewritten with a unique identity before and after each action.
    action_id = os.urandom(8).hex()
    body = args.output / (label + "-body.py")
    body.write_text(source)
    remote_body = f"/content/fast-h3-action-{action_id}.py"
    cli(args, "upload", "-s", args.session, body, remote_body, timeout=180)
    wrapper = "import json,sys,traceback\nfrom pathlib import Path\n"
    wrapper += f"action_id={action_id!r}\n"
    wrapper += f"_result_path=Path({REMOTE_ROOT!r})/'state/action-result.json'\n_result_path.parent.mkdir(parents=True,exist_ok=True)\n"
    wrapper += f"_result_path.write_text(json.dumps({{'action_id': action_id, 'status': 'running'}}))\n"
    wrapper += f"try:\n    exec(compile(Path({remote_body!r}).read_text(), {remote_body!r}, 'exec'), globals())\n"
    wrapper += "except Exception as _error:\n"
    wrapper += f"    _result_path.write_text(json.dumps({{'action_id': action_id, 'status': 'failed'}}|{{'error_type':type(_error).__name__}}))\n    raise\n"
    wrapper += "else:\n"
    wrapper += f"    _result_path.write_text(json.dumps({{'action_id': action_id, 'status': 'pass'}}))\n    print('FAST_H3_ACTION_PASS {action_id}',flush=True)\n"
    script.write_text(wrapper)
    stop_event = threading.Event()
    def watcher():
        while not stop_event.is_set():
            pull_state(args)
            file = args.output / "state/progress.json"
            if file.exists():
                progress = json.loads(file.read_text())
                print("REMOTE", progress.get("phase"), progress.get("elapsed_seconds", ""), flush=True)
            stop_event.wait(30)
    thread = threading.Thread(target=watcher, daemon=True)
    thread.start()
    try:
        output = cli(args, "exec", "-s", args.session, "-f", script, "--timeout", str(args.timeout),
                     timeout=args.timeout + 60)
        (args.output / (label + ".log")).write_text(output)
    finally:
        stop_event.set()
        thread.join(timeout=60)
        pull_state(args)
    file = args.output / "state/action-result.json"
    if not file.exists():
        raise RuntimeError("Remote action result unavailable; reconcile the original job before retrying")
    result = json.loads(file.read_text())
    if result.get("action_id") != action_id or result.get("status") != "pass":
        raise RuntimeError(f"Remote action did not pass: {result}; inspect state/logs before retrying")


def bootstrap_source():
    return '''import sys,zipfile
from pathlib import Path
target=Path('/content/fast-h3-toolkit');target.mkdir(exist_ok=True)
with zipfile.ZipFile('/content/fast-h3-toolkit.zip') as z:
    allowed=set('fast_h3_runtime.py fast_h3_workflow.py fast_h3_client.py fast_h3_nodes.py fast_h3_lock.json'.split())
    assert set(z.namelist())==allowed
    for name in z.namelist():
        (target/name).write_bytes(z.read(name))
sys.path.insert(0,str(target))
for module in ('fast_h3_runtime','fast_h3_workflow','fast_h3_client','fast_h3_nodes'):
    sys.modules.pop(module,None)
from fast_h3_runtime import FastH3Runtime
'''


def setup(args):
    archive = prepare(args)
    cli(args, "upload", "-s", args.session, archive, "/content/fast-h3-toolkit.zip", timeout=180)
    if args.backend == "notebook":
        source = "import sys\nfor _module in ('fast_h3_runtime','fast_h3_workflow','fast_h3_client','fast_h3_nodes'):\n    sys.modules.pop(_module,None)\n_FAST_H3_RUNTIME=None\n"
        source += export_section(ROOT / "notebooks/MiniMax_H3_A100.ipynb", "setup")
    else:
        source = bootstrap_source() + f"\nFAST_H3_AGENT_RUNTIME=FastH3Runtime()\nFAST_H3_AGENT_SETUP=FAST_H3_AGENT_RUNTIME.setup(loras={settings(args)['loras']!r})\n"
    execute(args, source, "setup-" + args.backend)


def generate(args):
    config = settings(args)
    for index, value in enumerate(config["reference_paths"]):
        source_image = Path(value).expanduser().resolve()
        target = "/content/fast_h3_ref_" + sha256(source_image) + source_image.suffix.lower()
        cli(args, "upload", "-s", args.session, source_image, target, timeout=180)
        config["reference_paths"][index] = target
    if args.backend == "notebook":
        notebook = json.loads((ROOT / "notebooks/MiniMax_H3_A100.ipynb").read_text())
        code = {cell["id"]: "".join(cell["source"]) for cell in notebook["cells"] if cell["cell_type"] == "code"}
        source = code["clip-settings"] + "\n"
        mapping = {"prompt": "FAST_H3_PROMPT", "width": "FAST_H3_WIDTH", "height": "FAST_H3_HEIGHT",
                   "duration_seconds": "FAST_H3_DURATION_SECONDS", "seed": "FAST_H3_SEED", "run_name": "FAST_H3_RUN_NAME",
                   "generation_mode": "FAST_H3_MODE"}
        source += "\n".join(f"{variable}={config[field]!r}" for field, variable in mapping.items())
        source += "\nFAST_H3_LORAS_JSON=" + repr(json.dumps(config["loras"])) + "\n"
        source += "FAST_H3_REFERENCES_JSON=" + repr(json.dumps(config["reference_paths"])) + "\n"
        source += "import IPython.display\n_previous_display=IPython.display.display\nIPython.display.display=lambda *a,**kw: print('Preview saved to MP4; CLI skips embedding')\n"
        source += "try:\n    exec(compile(" + repr(code["generate-video"]) + ", 'notebook-generate-video', 'exec'), globals())\nfinally:\n    IPython.display.display=_previous_display\n"
    else:
        source = bootstrap_source() + f"\nFAST_H3_AGENT_RUNTIME=FastH3Runtime()\nFAST_H3_AGENT_RESULT=FAST_H3_AGENT_RUNTIME.generate(**{config!r},timeout={args.timeout})\n"
    execute(args, source, "generate-" + args.backend)
    fetch(args)


def fetch(args):
    args.output.mkdir(parents=True, exist_ok=True)
    latest = args.output / "latest.json"
    cli(args, "download", "-s", args.session, REMOTE_ROOT + "/latest.json", latest, timeout=60)
    metrics = json.loads(latest.read_text())
    if metrics.get("status") != "technically_valid":
        raise RuntimeError("Latest generation has no technically valid receipt")
    archive_path = metrics["archive_path"]
    if not archive_path.startswith(REMOTE_ROOT + "/runs/") or not archive_path.endswith(".zip"):
        raise ValueError("Unexpected remote result archive")
    archive = args.output / Path(archive_path).name
    cli(args, "download", "-s", args.session, archive_path, archive, timeout=180)
    destination = args.output / archive.stem
    destination.mkdir(exist_ok=True)
    with zipfile.ZipFile(archive) as bundle:
        if bundle.testzip() is not None:
            raise ValueError("Result archive failed CRC verification")
        for item in bundle.infolist():
            if Path(item.filename).name != item.filename or item.is_dir():
                raise ValueError("Result archive entry must be a basename-only file")
            target = destination / item.filename
            content = bundle.read(item)
            if target.exists() and target.read_bytes() != content:
                raise ValueError("Existing result contains different bytes: " + item.filename)
            if not target.exists():
                with target.open("xb") as stream:
                    stream.write(content)
    receipt = json.loads((destination / "metrics.json").read_text())
    if receipt["prompt_id"] != metrics["prompt_id"] or sha256(destination / "video.mp4") != receipt["video_sha256"]:
        raise ValueError("Downloaded video/receipt identity or SHA256 mismatch")
    local_media = verify_media(destination / "video.mp4", width=receipt["width"], height=receipt["height"],
                               duration_seconds=receipt["duration_seconds"])
    (destination / "local-media.json").write_text(json.dumps(local_media, indent=2))
    print("LOCAL_MEDIA_PASS", destination / "video.mp4", flush=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("prepare", "start", "setup", "generate", "status", "fetch", "refresh", "stop"))
    parser.add_argument("--session", default="fast-h3-l4")
    parser.add_argument("--auth", default="oauth2", choices=("oauth2", "adc"))
    parser.add_argument("--backend", default="comfy", choices=("comfy", "notebook"))
    parser.add_argument("--config", type=Path)
    parser.add_argument("--output", type=Path, default=ROOT / "artifacts/fast-h3-l4")
    parser.add_argument("--timeout", type=int, default=1800)
    args = parser.parse_args()
    if not re.fullmatch(r"[A-Za-z0-9_-]+", args.session):
        parser.error("session may contain letters, digits, underscores and hyphens")
    if args.timeout <= 0 or args.timeout > 5400:
        parser.error("timeout must be within 1..5400 seconds")
    if args.action == "status":
        cli(args, "status", "-s", args.session)
        pull_state(args)
        for file in (args.output / "state").glob("*.json"):
            if file.name in ("progress.json", "hardware.json", "kernel-preflight.json"):
                print(file.name, file.read_text())
    elif args.action == "stop":
        cli(args, "stop", "-s", args.session)
        cli(args, "sessions")
        cli(args, "usage")
    else:
        globals()[args.action](args)


if __name__ == "__main__":
    main()
