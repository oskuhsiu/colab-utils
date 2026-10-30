#!/usr/bin/env python3
"""Manage one persistent Colab session for Qwen comic generation."""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
import zipfile
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
NOTEBOOK = ROOT / "notebooks" / "Qwen_Image_2_1_Comic_Colab.ipynb"
UPSCALER_NOTEBOOK = ROOT / "notebooks" / "Qwen_Webtoon_2x_Upscaler_Colab.ipynb"
SERIES_FILE = ROOT / "projects" / "pudding-hamster" / "series.json"
PANEL_WIDTH_OPTIONS = (512, 640, 768, 896, 1024, 1280, 1536)
SUPPORTED_GPUS = ("T4", "L4", "G4", "H100", "A100")


def run(command: list[str], *, check: bool = True, capture: bool = False) -> subprocess.CompletedProcess:
    result = subprocess.run(
        command,
        cwd=ROOT,
        text=True,
        stdout=subprocess.PIPE if capture else None,
        stderr=subprocess.STDOUT if capture else None,
    )
    if capture and result.stdout:
        print(result.stdout, end="")
    if check and result.returncode:
        raise SystemExit(result.returncode)
    return result


def series_config() -> dict:
    return json.loads(SERIES_FILE.read_text(encoding="utf-8"))


def colab(auth: str, *args: str) -> list[str]:
    return ["colab", "--auth", auth, *args]


def active_session(auth: str, session_name: str) -> bool:
    result = run(colab(auth, "sessions"), check=False, capture=True)
    if result.returncode:
        raise SystemExit("Could not inspect Colab sessions; refusing to allocate another runtime.")
    return any(line.startswith(f"[{session_name}]") for line in (result.stdout or "").splitlines())


def notebook_exec(
    auth: str,
    session_name: str,
    action: str,
    timeout: int,
    *,
    notebook_path: Path = NOTEBOOK,
    **env_vars: str,
) -> None:
    command = colab(auth, "exec", "-s", session_name)
    env = {
        "QWEN_ACTION": action,
        "QWEN_SESSION_NAME": session_name,
        "QWEN_MODEL_ID": "Qwen/Qwen-Image-2.1",
        **env_vars,
    }
    for key, value in env.items():
        command.extend(["--env", f"{key}={value}"])
    command.extend(["-f", str(notebook_path), "--timeout", str(timeout)])
    run(command)


def start(args: argparse.Namespace) -> None:
    session_name = args.session or series_config()["remote_runtime"]["session_name"]
    if active_session(args.auth, session_name):
        print(f"Using existing Colab session: {session_name}")
    else:
        command = colab(args.auth, "new", "-s", session_name, "--gpu", args.gpu)
        if args.high_mem:
            command.append("--high-mem")
        run(command)
    # Warm the model now so later submit calls only send panel work.
    notebook_exec(args.auth, session_name, "start", args.start_timeout)


def status(args: argparse.Namespace) -> None:
    session_name = args.session or series_config()["remote_runtime"]["session_name"]
    run(colab(args.auth, "status", "-s", session_name))
    notebook_exec(args.auth, session_name, "status", args.status_timeout)


def safe_extract(zip_path: Path, destination: Path) -> None:
    destination = destination.resolve()
    with zipfile.ZipFile(zip_path) as archive:
        for member in archive.infolist():
            target = (destination / member.filename).resolve()
            if not target.is_relative_to(destination):
                raise ValueError(f"Unsafe path in result archive: {member.filename}")
        archive.extractall(destination)


def submit(args: argparse.Namespace) -> None:
    project_dir = args.project_dir.resolve()
    project = json.loads((project_dir / "project.json").read_text(encoding="utf-8"))
    project_id = project["project_id"]
    chapter_id = project["chapter_id"]
    if not re.fullmatch(r"[a-zA-Z0-9_-]+", project_id) or not re.fullmatch(r"[a-zA-Z0-9_-]+", chapter_id):
        raise SystemExit("Project and chapter IDs may contain only letters, digits, underscore, and hyphen.")

    session_name = args.session or series_config()["remote_runtime"]["session_name"]
    if not active_session(args.auth, session_name):
        raise SystemExit(f"Colab session '{session_name}' is not active. Start it once with: python3 scripts/qwen_comic_colab.py start")

    webtoon = (project_dir / "webtoon_storyboard.json").is_file()
    if webtoon:
        if args.phase == "first-page":
            raise SystemExit("Webtoon storyboard projects use --phase first-panel or all.")
        run([sys.executable, "scripts/build_webtoon_tasks.py", str(project_dir), "--width", str(args.width)])
        run([sys.executable, "scripts/validate_webtoon_project.py", str(project_dir)])
    else:
        if args.phase == "first-panel":
            raise SystemExit("Page storyboard projects use --phase first-page or all.")
        run([sys.executable, "scripts/build_comic_page_tasks.py", str(project_dir)])
        run([sys.executable, "scripts/validate_comic_project.py", str(project_dir)])
    runs_dir = project_dir / "runs"
    runs_dir.mkdir(parents=True, exist_ok=True)
    job_archive = runs_dir / f"{project_id}-{chapter_id}-job.zip"
    run([
        sys.executable,
        "scripts/package_qwen_colab_job.py",
        str(project_dir),
        "--output",
        str(job_archive),
    ])

    remote_job = f"/content/{project_id}-{chapter_id}-job.zip"
    run(colab(args.auth, "upload", "-s", session_name, str(job_archive), remote_job))
    notebook_exec(
        args.auth,
        session_name,
        "submit",
        args.timeout,
        QWEN_PROJECT_ID=project_id,
        QWEN_CHAPTER_ID=chapter_id,
        QWEN_JOB_ARCHIVE=remote_job,
        QWEN_PHASE=args.phase,
        QWEN_FORCE_PAGES=args.force_pages,
        QWEN_FORCE_PANELS=args.force_panels,
        QWEN_PANEL_WIDTH=str(args.width),
    )

    result_zip = runs_dir / f"{project_id}-{chapter_id}-results.zip"
    remote_results = f"/content/{project_id}-{chapter_id}-results.zip"
    run(colab(args.auth, "download", "-s", session_name, remote_results, str(result_zip)))
    safe_extract(result_zip, project_dir)
    if webtoon:
        run([sys.executable, "scripts/compose_webtoon_reader.py", str(project_dir)])
    print(f"Local results are ready in {project_dir / 'results'}")


def upscale(args: argparse.Namespace) -> None:
    project_dir = args.project_dir.resolve()
    project = json.loads((project_dir / "project.json").read_text(encoding="utf-8"))
    project_id = project["project_id"]
    chapter_id = project["chapter_id"]
    tasks_path = project_dir / "webtoon_tasks.json"
    if not tasks_path.is_file():
        raise SystemExit("Generate or build webtoon_tasks.json before requesting the optional upscale pass.")
    run([sys.executable, "scripts/validate_webtoon_project.py", str(project_dir)])
    tasks = json.loads(tasks_path.read_text(encoding="utf-8"))
    missing = [
        str(project_dir / task["output_path"])
        for task in tasks["panels"]
        if not (project_dir / task["output_path"]).is_file()
    ]
    if missing:
        raise SystemExit("All draft panels must exist before upscaling:\n" + "\n".join(missing))

    runs_dir = project_dir / "runs"
    runs_dir.mkdir(parents=True, exist_ok=True)
    job_archive = runs_dir / f"{project_id}-{chapter_id}-upscale-job.zip"
    run([
        sys.executable,
        "scripts/package_qwen_colab_job.py",
        str(project_dir),
        "--output",
        str(job_archive),
    ])

    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    session_name = f"webtoon-upscale-{chapter_id}-{timestamp}"
    run(colab(args.auth, "new", "-s", session_name, "--gpu", args.gpu))
    remote_job = f"/content/{project_id}-{chapter_id}-upscale-job.zip"
    try:
        run(colab(args.auth, "upload", "-s", session_name, str(job_archive), remote_job))
        notebook_exec(
            args.auth,
            session_name,
            "upscale",
            args.timeout,
            notebook_path=UPSCALER_NOTEBOOK,
            QWEN_PROJECT_ID=project_id,
            QWEN_CHAPTER_ID=chapter_id,
            QWEN_JOB_ARCHIVE=remote_job,
            QWEN_UPSCALE_FACTOR=str(args.factor),
        )
        result_zip = runs_dir / f"{project_id}-{chapter_id}-upscaled-results.zip"
        remote_results = f"/content/{project_id}-{chapter_id}-results.zip"
        run(colab(args.auth, "download", "-s", session_name, remote_results, str(result_zip)))
        safe_extract(result_zip, project_dir)
    finally:
        run(colab(args.auth, "stop", "-s", session_name), check=False, capture=True)
    run([sys.executable, "scripts/compose_webtoon_reader.py", str(project_dir), "--prefer-upscaled"])
    print(f"Upscaled panels are ready in {project_dir / 'results' / 'upscaled-panels'}")


def stop(args: argparse.Namespace) -> None:
    session_name = args.session or series_config()["remote_runtime"]["session_name"]
    run(colab(args.auth, "stop", "-s", session_name))


def parser() -> argparse.ArgumentParser:
    root = argparse.ArgumentParser(description=__doc__)
    root.add_argument("--auth", default="oauth2", choices=("oauth2", "adc"))
    root.add_argument("--session", help="Override the stable session name from series.json")
    commands = root.add_subparsers(dest="command", required=True)

    start_parser = commands.add_parser("start", help="Allocate once and load the model into the persistent kernel (standard system RAM by default)")
    start_parser.add_argument("--gpu", choices=SUPPORTED_GPUS, default=series_config()["remote_runtime"]["gpu"])
    start_parser.add_argument("--high-mem", action=argparse.BooleanOptionalAction,
                              default=series_config()["remote_runtime"]["high_memory"])
    start_parser.add_argument("--start-timeout", type=int, default=7200)
    start_parser.set_defaults(func=start)

    submit_parser = commands.add_parser("submit", help="Build, upload, generate, and download one chapter")
    submit_parser.add_argument("project_dir", type=Path)
    submit_parser.add_argument("--phase", choices=("first-page", "first-panel", "all"), default="all")
    submit_parser.add_argument("--force-pages", default="")
    submit_parser.add_argument("--force-panels", default="")
    submit_parser.add_argument("--width", type=int, choices=PANEL_WIDTH_OPTIONS, default=768,
                               help="Webtoon panel output width in pixels; height follows the panel composition class.")
    submit_parser.add_argument("--timeout", type=int, default=7200)
    submit_parser.set_defaults(func=submit)

    upscale_parser = commands.add_parser("upscale", help="Apply separate T4 Swin2SR x2 pass after review")
    upscale_parser.add_argument("project_dir", type=Path)
    upscale_parser.add_argument("--gpu", choices=("T4",), default="T4")
    upscale_parser.add_argument("--factor", type=int, choices=(2,), default=2)
    upscale_parser.add_argument("--timeout", type=int, default=7200)
    upscale_parser.set_defaults(func=upscale)

    status_parser = commands.add_parser("status", help="Inspect both the Colab session and loaded model instance")
    status_parser.add_argument("--status-timeout", type=int, default=180)
    status_parser.set_defaults(func=status)

    stop_parser = commands.add_parser("stop", help="Explicitly release the fixed Colab session")
    stop_parser.set_defaults(func=stop)
    return root


def main() -> None:
    args = parser().parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
