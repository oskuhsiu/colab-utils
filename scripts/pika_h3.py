#!/usr/bin/env python3
"""Offline planning and isolated Colab execution of the official Pika H3 Flex CLI.

Local imports require only Python 3.10+ stdlib. Install/generate are explicit;
this tool never allocates a Colab runtime or calls a hosted Pika API.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
from fractions import Fraction
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import sys
import time
import uuid

LOCK = json.loads(Path(__file__).with_name("pika_h3_lock.json").read_text())
TASKS = ("t2va", "i2va", "l2va", "fl2va", "ref2va")


def save_json(path, data):
    path = Path(path)
    pending = path.with_suffix(path.suffix + ".tmp")
    pending.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n")
    pending.replace(path)


def sha256(path):
    digest = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def request(*, prompt, task="t2va", resolution="480p", aspect="16:9", duration=5,
            seed=0, first_image=None, last_image=None, refs=(), cpu_offload=False):
    """Validate routing without reading media, downloading or touching the GPU.

    Source duration/format validation and reference hashes are supplied by the
    official CLI when it loads the real inputs.
    """
    if task not in TASKS:
        raise ValueError(f"Unknown Pika task: {task}")
    if not isinstance(prompt, str) or not prompt.strip() or len(prompt) > 8000:
        raise ValueError("Pika prompt must contain 1–8000 characters")
    if resolution not in LOCK["resolution_buckets"] or aspect not in LOCK["resolution_buckets"][resolution]:
        raise ValueError("Choose a supported Pika resolution/aspect bucket")
    if type(duration) is not int or not 5 <= duration <= 15:
        raise ValueError("Pika duration must be an integer from 5 to 15 seconds")
    if type(seed) is not int or not 0 <= seed < 2**63:
        raise ValueError("Pika seed must be an integer from 0 to 2**63 - 1")
    if type(cpu_offload) is not bool or not isinstance(refs, (list, tuple)):
        raise ValueError("cpu_offload must be boolean and refs must be an ordered list")
    first_image = str(first_image) if first_image else None
    last_image = str(last_image) if last_image else None
    if bool(first_image) != (task in ("i2va", "fl2va")):
        raise ValueError("first_image is required only for i2va/fl2va")
    if bool(last_image) != (task in ("l2va", "fl2va")):
        raise ValueError("last_image is required only for l2va/fl2va")
    counts = {"image": 0, "video": 0, "audio": 0}
    for ref in refs:
        kind, separator, path = ref.partition(":") if isinstance(ref, str) else ("", "", "")
        if kind not in counts or not separator or not path.strip():
            raise ValueError("References must use image:path, video:path or audio:path")
        counts[kind] += 1
    if task == "ref2va":
        if not counts["image"] + counts["video"]:
            raise ValueError("ref2va requires at least one image or video reference")
        if len(refs) > 12 or counts["image"] > 9 or counts["video"] > 3 or counts["audio"] > 3:
            raise ValueError("Pika limits: 9 images, 3 videos, 3 audio clips, 12 references total")
    elif refs:
        raise ValueError("References require task=ref2va; endpoint images use first_image/last_image")
    return dict(task=task, prompt=prompt, resolution=resolution, aspect=aspect, duration=duration,
                seed=seed, first_image=first_image, last_image=last_image,
                refs=list(refs), cpu_offload=cpu_offload)


def geometry(job):
    width, height = LOCK["resolution_buckets"][job["resolution"]][job["aspect"]]
    frames = ((job["duration"] * 24 - 5 + 16) // 17) * 17 + 5
    return dict(width=width, height=height, fps=24, frames=frames, seconds=frames / 24)


class PikaWorkspace:
    def __init__(self, root="/content/pika-h3"):
        self.root = Path(root).expanduser().resolve()
        self.source = self.root / "source"
        self.python = self.root / "venv/bin/python"
        self.executable = self.root / "venv/bin/pika-h3-pro"
        self.marker = self.root / "install.json"

    def plan(self):
        """Pure offline plan; Hugging Face's existing cache/environment is reused."""
        return dict(tool="pika", root=str(self.root), release=LOCK,
                    install_python="3.12 (isolated venv)",
                    tested_upstream_gpu="H100 80GB; local GPU validation not_run",
                    disk_note="Both tasks together: about 210 GB base + 5.5 GB adapters, plus staging/dependencies",
                    memory_note="CPU offload does not offload the text encoder or VAEs; check host RAM too",
                    tasks=list(TASKS), model_download="Selected task downloads on explicit generate only")

    def command(self, job, prompt_file, output):
        command = [str(self.executable), "--task", job["task"], "--prompt-file", str(prompt_file),
                   "--model-repo", LOCK["model_repo"], "--revision", LOCK["model_revision"],
                   "--resolution", job["resolution"], "--aspect", job["aspect"],
                   "--duration", str(job["duration"]), "--seed", str(job["seed"]), "--output", str(output)]
        for flag, value in (("--first-image", job["first_image"]), ("--last-image", job["last_image"])):
            if value:
                command.extend((flag, value))
        for ref in job["refs"]:
            command.extend(("--ref", ref))
        if job["cpu_offload"]:
            command.append("--cpu-offload")
        return command

    def prepare(self, **kwargs):
        job = request(**kwargs)
        directory = self.root / "runs/<new-run-id>"
        return dict(request=job, geometry=geometry(job),
                    command=self.command(job, directory / "prompt.txt", directory / "video.mp4"))

    def _installed(self):
        if not self.marker.is_file() or not self.executable.is_file():
            return False
        return json.loads(self.marker.read_text()).get("release") == LOCK

    def _verify_source(self):
        head = subprocess.check_output(["git", "-C", str(self.source), "rev-parse", "HEAD"], text=True).strip()
        dirty = subprocess.check_output(["git", "-C", str(self.source), "status", "--porcelain"], text=True).strip()
        if head != LOCK["code_revision"] or dirty:
            raise RuntimeError("Pika source differs from the pinned release; preserve it and use another workspace root")

    def install(self, python=None):
        if self._installed():
            self._verify_source()
            return dict(installed=True, reused=True, root=str(self.root))
        python = python or (sys.executable if sys.version_info[:2] == (3, 12) else shutil.which("python3.12"))
        if not python:
            raise RuntimeError("Official Pika requires Python 3.12; supply --python /path/to/python3.12")
        version = subprocess.check_output([str(python), "-c", "import sys; print('%d.%d' % sys.version_info[:2])"], text=True).strip()
        if version != LOCK["python"]:
            raise RuntimeError("Official Pika requires Python 3.12; existing environments are not modified")
        for program in ("git", "patch", "ffmpeg", "ffprobe", "cc", "nvidia-smi"):
            if not shutil.which(program):
                raise RuntimeError(f"Install prerequisite on the target GPU runtime: {program}")
        self.root.mkdir(parents=True, exist_ok=True)
        with (self.root / "install.log").open("a") as log:
            def run(args, cwd=None):
                subprocess.run(list(map(str, args)), cwd=cwd, stdout=log, stderr=subprocess.STDOUT, check=True)

            if not self.source.exists():
                run(["git", "clone", "--no-checkout", LOCK["code_repo"], self.source])
                run(["git", "checkout", "--detach", LOCK["code_revision"]], cwd=self.source)
            self._verify_source()
            run([python, "-m", "venv", self.root / "venv"])
            run([self.python, "-m", "pip", "install", "-r", self.source / "requirements.txt"])
            run([self.python, self.source / "tools/apply_diffusers_patches.py"], cwd=self.source)
            run([self.python, "-m", "pip", "install", "--no-deps", "-e", self.source])
            run([self.executable, "--help"])
        save_json(self.marker, dict(release=LOCK, installed_at=datetime.now(timezone.utc).isoformat()))
        return dict(installed=True, reused=False, root=str(self.root), log=str(self.root / "install.log"))

    def generate(self, **kwargs):
        job = request(**kwargs)
        for value in [job["first_image"], job["last_image"], *[ref.split(":", 1)[1] for ref in job["refs"]]]:
            if value and not Path(value).is_file():
                raise ValueError(f"Input file does not exist on this runtime: {value}")
        if not self._installed():
            raise RuntimeError("Run explicit install first; generate does not install or switch models")
        self._verify_source()
        directory = self.root / "runs" / (datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S") + "-" + uuid.uuid4().hex[:10])
        directory.mkdir(parents=True, exist_ok=False)
        prompt_file, output = directory / "prompt.txt", directory / "video.mp4"
        prompt_file.write_text(job["prompt"], encoding="utf-8")
        prepared = dict(request=job, geometry=geometry(job), release=LOCK,
                        command=self.command(job, prompt_file, output))
        save_json(directory / "request.json", prepared)
        receipt = dict(run_id=directory.name, status="starting", directory=str(directory),
                       started_at=datetime.now(timezone.utc).isoformat(), content_verdict="not_reviewed")
        receipt_path = directory / "receipt.json"
        save_json(receipt_path, receipt)
        started = time.monotonic()
        try:
            with (directory / "generation.log").open("w") as log:
                process = subprocess.Popen(prepared["command"], stdout=log, stderr=subprocess.STDOUT)
                receipt.update(status="running", pid=process.pid)
                save_json(receipt_path, receipt)
                if process.wait():
                    raise RuntimeError(f"Pika failed; inspect {directory / 'generation.log'}")
            metadata = output.with_suffix(".json")
            json.loads(metadata.read_text())
            probe = json.loads(subprocess.check_output([
                "ffprobe", "-v", "error", "-count_frames", "-show_streams", "-of", "json", str(output)
            ], text=True))
            video = next(stream for stream in probe["streams"] if stream["codec_type"] == "video")
            audio = next(stream for stream in probe["streams"] if stream["codec_type"] == "audio")
            expected = prepared["geometry"]
            if (video["width"], video["height"], int(video["nb_read_frames"])) != (expected["width"], expected["height"], expected["frames"]):
                raise RuntimeError("Pika output geometry/frame count differs from the requested bucket")
            if audio.get("channels") != 2 or int(audio.get("sample_rate", 0)) != 32000:
                raise RuntimeError("Pika output must contain 32 kHz stereo audio")
            if (Fraction(video["avg_frame_rate"]) != 24 or video["codec_name"] != "h264"
                    or audio["codec_name"] != "aac"
                    or abs(float(audio["duration"]) - expected["seconds"]) > 0.15):
                raise RuntimeError("Pika output must be 24fps H.264/AAC with a full-length soundtrack")
            subprocess.run(["ffmpeg", "-v", "error", "-xerror", "-i", str(output), "-f", "null", "-"],
                           stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, check=True)
            receipt.update(status="technically_valid", video=str(output), metadata=str(metadata),
                           video_sha256=sha256(output), metadata_sha256=sha256(metadata), media=probe)
        except (KeyboardInterrupt, SystemExit):
            receipt["status"] = "interrupted_needs_reconcile"
            raise
        except Exception as error:
            receipt.update(status="failed", error=str(error))
            raise
        finally:
            receipt.update(wall_seconds=time.monotonic() - started,
                           updated_at=datetime.now(timezone.utc).isoformat())
            save_json(receipt_path, receipt)
        return receipt

    def status(self):
        receipts = sorted((self.root / "runs").glob("*/receipt.json"))[-5:]
        return dict(root=str(self.root), installed=self._installed(),
                    recent_runs=[json.loads(path.read_text()) for path in receipts])


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="action", required=True)
    for action in ("plan", "install", "generate", "status"):
        sub = commands.add_parser(action)
        sub.add_argument("--root", default="/content/pika-h3")
        if action == "install":
            sub.add_argument("--python")
        if action == "generate":
            prompt = sub.add_mutually_exclusive_group(required=True)
            prompt.add_argument("--prompt")
            prompt.add_argument("--prompt-file", type=Path)
            sub.add_argument("--task", choices=TASKS, default="t2va")
            sub.add_argument("--resolution", choices=("480p", "768p"), default="480p")
            sub.add_argument("--aspect", choices=tuple(LOCK["resolution_buckets"]["480p"]), default="16:9")
            sub.add_argument("--duration", type=int, default=5)
            sub.add_argument("--seed", type=int, default=0)
            sub.add_argument("--first-image")
            sub.add_argument("--last-image")
            sub.add_argument("--ref", action="append", default=[], dest="refs")
            sub.add_argument("--cpu-offload", action="store_true")
    args = parser.parse_args()
    workspace = PikaWorkspace(args.root)
    if args.action == "generate":
        options = vars(args).copy()
        for name in ("action", "root", "prompt_file"):
            options.pop(name)
        if args.prompt_file:
            options["prompt"] = args.prompt_file.read_text(encoding="utf-8")
        result = workspace.generate(**options)
    elif args.action == "install":
        result = workspace.install(python=args.python)
    else:
        result = getattr(workspace, args.action)()
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
