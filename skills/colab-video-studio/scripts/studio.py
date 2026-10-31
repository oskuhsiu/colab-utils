#!/usr/bin/env python3
"""Colab video studio: prepare, render, inspect, review, and assemble."""
from __future__ import annotations

import argparse
import json
import re
import shutil
import stat
import subprocess
import sys
import tempfile
import zipfile
from pathlib import Path

from workflow import (SCRIPT_DIR, accept_review, compile_job, identifier, local_path,
    prepare, read_json, reserve, sha256, verify_current, write_json)
from media import assemble, evidence, joins, join_directories, verify_video


def colab(arguments, log=None):
    """CLI exit status is transport evidence; remote receipt determines success."""
    command = ["colab", "--auth", "oauth2", *arguments]
    process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
    lines = []
    for line in process.stdout:
        clean = re.sub(r"https?://\S+", "[URL]", line)
        lines.append(clean)
        if log:
            with Path(log).open("a") as stream:
                stream.write(clean)
        if "STUDIO_PROGRESS" in line or "STUDIO_GENERATED" in line:
            print(clean.strip(), flush=True)
    code = process.wait()
    if code:
        raise RuntimeError(f"Colab {arguments[0]} exited {code}; reconcile this attempt before any retry")
    return "".join(lines)


def pack(project, directory, job):
    project, directory = Path(project).resolve(), Path(directory).resolve()
    root = directory / "input"
    root.mkdir(exist_ok=False)
    (root / "assets").mkdir()
    (root / "scripts").mkdir()
    (root / "loras").mkdir()
    for name, asset in job["assets"].items():
        target = root / "assets" / (name + Path(asset["path"]).suffix.lower())
        shutil.copy2(local_path(project, asset["path"]), target)
        if sha256(target) != asset["sha256"]:
            raise ValueError("Source changed while packaging; prepare a new attempt")
    for index, adapter in enumerate(job["settings"]["loras"]):
        target = root / "loras" / f"{index:03d}.safetensors"
        shutil.copy2(local_path(project,adapter["path"]), target)
        if sha256(target) != adapter["sha256"]:
            raise ValueError("LoRA changed during packaging")
    for name, expected in job["code"].items():
        shutil.copy2(SCRIPT_DIR / name, root / "scripts" / name)
        if sha256(root / "scripts" / name) != expected:
            raise ValueError("Inference scripts changed while packaging")
    write_json(root / "job.json", dict(job, attempt_id=directory.name))
    archive = directory / "input.zip"
    with zipfile.ZipFile(archive,"x",zipfile.ZIP_STORED) as bundle:
        for path in sorted(root.rglob("*")):
            if path.is_file():
                bundle.write(path, arcname=str(path.relative_to(root)))
    return archive


def reserve_and_pack(project, shot):
    directory, job = reserve(project, shot)
    pack(project, directory, job)
    return directory


def submit(project, attempt, session, timeout=3600):
    project = Path(project).resolve()
    directory = project / "attempts" / identifier(attempt)
    job = verify_current(project, directory)
    receipt = read_json(directory / "receipt.json")
    if receipt["state"] != "reserved":
        raise ValueError("Only an unsubmitted reserved attempt may be submitted. Fetch/reconcile existing work.")
    identifier(session)
    remote = f"/content/video-studio/{job['project_id']}/{attempt}"
    receipt.update(state="uploading", session=session, remote_directory=remote)
    write_json(directory / "receipt.json", receipt)
    archive_path = f"/content/{job['project_id']}_{attempt}.zip"
    source = (
        "from pathlib import Path\nimport zipfile,stat\n"
        f"_studio_target=Path({remote!r}) / 'input'\n"
        "_studio_target.mkdir(parents=True,exist_ok=True)\n"
        f"with zipfile.ZipFile({archive_path!r}) as _studio_zip:\n"
        "    for _studio_item in _studio_zip.infolist():\n"
        "        _studio_path=(_studio_target / _studio_item.filename).resolve()\n"
        "        if not _studio_path.is_relative_to(_studio_target.resolve()) or stat.S_ISLNK(_studio_item.external_attr >> 16):\n"
        "            raise ValueError('Unsafe input archive')\n"
        "    _studio_zip.extractall(_studio_target)\n"
        "exec(compile((_studio_target/'scripts'/'remote.py').read_text(), 'remote.py', 'exec'), globals())\n"
        "run_job(_studio_target/'job.json')\n")
    command_file = directory / "execute.py"
    command_file.write_text(source)
    try:
        colab(["upload", "-s",session,str(directory / "input.zip"),archive_path], directory / "transport.log")
        receipt["state"] = "submitted"
        write_json(directory / "receipt.json", receipt)
        colab(["exec", "-s", session,"-f",str(command_file),"--timeout",str(timeout)], directory / "transport.log")
        return fetch(project, attempt)
    except Exception:
        receipt["state"] = "needs_reconcile"
        write_json(directory / "receipt.json", receipt)
        raise


def extract_results(archive, directory):
    """Reject traversal, duplicate entries, symlinks and overwrites with new bytes."""
    directory = Path(directory).resolve()
    with zipfile.ZipFile(archive) as bundle:
        names = [item.filename for item in bundle.infolist()]
        if len(names) != len(set(names)) or bundle.testzip() is not None:
            raise ValueError("Invalid result ZIP integrity/duplicate entries")
        for item in bundle.infolist():
            parts = Path(item.filename).parts
            if len(parts) != 2 or parts[0] != "result" or parts[1] in (".", "..") or stat.S_ISLNK(item.external_attr >> 16):
                raise ValueError("Unsafe result archive")
            target = local_path(directory, item.filename)
            data = bundle.read(item)
            import hashlib
            if target.exists():
                if sha256(target) != hashlib.sha256(data).hexdigest():
                    raise ValueError("Existing result differs; preserve both and reconcile")
            else:
                target.parent.mkdir(exist_ok=True)
                with target.open("xb") as output:
                    output.write(data)


def fetch(project, attempt):
    project = Path(project).resolve()
    directory = project / "attempts" / identifier(attempt)
    receipt = read_json(directory / "receipt.json")
    if "session" not in receipt or "remote_directory" not in receipt:
        raise ValueError("Attempt has no remote submission to fetch")
    with tempfile.TemporaryDirectory(prefix="fetch-",dir=directory) as temporary:
        archive = Path(temporary) / "result.zip"
        colab(["download", "-s",receipt["session"],receipt["remote_directory"]+"/result.zip",str(archive)], directory / "transport.log")
        extract_results(archive,directory)
    remote_receipt = read_json(directory / "result" / "receipt.json")
    if remote_receipt.get("attempt_id") != attempt or remote_receipt.get("job_digest") != receipt["job_digest"]:
        raise ValueError("Remote result belongs to a different job/attempt")
    receipt["remote"] = remote_receipt
    if remote_receipt["status"] == "generated":
        job = read_json(directory / "job.json")
        if sha256(directory / "result" / "video.mp4") != remote_receipt["video_sha256"]:
            raise ValueError("Result video differs from generation receipt")
        receipt["technical"] = verify_video(directory / "result" / "video.mp4",job["shot"])
        receipt["state"] = "technically_valid"
    else:
        receipt["state"] = "failed_generation"
    write_json(directory / "receipt.json", receipt)
    return receipt


def status(project, attempt):
    directory = Path(project).resolve() / "attempts" / identifier(attempt)
    receipt = read_json(directory / "receipt.json")
    if receipt.get("remote_directory"):
        colab(["download", "-s",receipt["session"],receipt["remote_directory"]+"/result/progress.json",
               str(directory / "remote-progress.json")],directory / "transport.log")
        return read_json(directory / "remote-progress.json")
    return receipt


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command",required=True)
    init = sub.add_parser("init",help="Create an editable project from the packaged example")
    init.add_argument("--project",required=True,type=Path)
    init.add_argument("--request",required=True)
    init.add_argument("--kind",choices=("provided-person","photoreal","stylized"),default="photoreal")
    for name in ("prepare","reserve","submit","fetch","status","inspect","review","joins","assemble",
                 "edit-prepare","edit-inspect","edit-joins","edit-assemble"):
        command = sub.add_parser(name)
        command.add_argument("--project",required=True,type=Path)
        if name == "reserve":
            command.add_argument("--shot",required=True)
        if name in ("submit","fetch","status","inspect","review"):
            command.add_argument("--attempt",required=True)
        if name == "submit":
            command.add_argument("--session",required=True)
            command.add_argument("--timeout",type=int,default=3600)
        if name == "review":
            command.add_argument("--file",required=True,type=Path)
        if name in ("joins","assemble"):
            command.add_argument("--selection",required=True,type=Path)
        if name == "assemble":
            command.add_argument("--join-review",type=Path)
        if name == "edit-prepare":
            command.add_argument("--selection",required=True,type=Path)
            command.add_argument("--edits",required=True,type=Path)
            command.add_argument("--run",required=True)
        if name in ("edit-inspect","edit-joins","edit-assemble"):
            command.add_argument("--run",required=True)
        if name == "edit-assemble":
            command.add_argument("--join-review",type=Path)
    args = parser.parse_args()
    try:
        if args.command == "init":
            args.project.mkdir(parents=True,exist_ok=False)
            value = read_json(SCRIPT_DIR.parent / "assets" / "templates" / "new-film" / "plan.json")
            value["project_id"] = identifier(args.project.name)
            value["request"].update(text=args.request,kind=args.kind)
            write_json(args.project / "plan.json",value)
            (args.project / "assets").mkdir()
            result = {"project":str(args.project),"state":"draft", "next":"Supply/review anchors and edit shots/criteria, then prepare"}
        elif args.command.startswith("edit-"):
            import editing
            if args.command == "edit-prepare":
                run = editing.prepare_edits(args.project,read_json(args.selection),read_json(args.edits),args.run)
                result = {"run":str(run),"state":"conformed_needs_review"}
            elif args.command == "edit-inspect":
                result = [{"shot_id":m["shot_id"],"sampled_frames":m["sampled_frames"]}
                          for m in editing.inspect_edits(args.project,args.run)]
            elif args.command == "edit-joins":
                directories = editing.validate_edits(args.project,args.run)
                recipe = read_json(args.project.resolve()/"edits"/identifier(args.run)/"recipe.json")
                result = {"pairs":len(join_directories(args.project,directories,recipe["selection"])["pairs"])}
            else:
                result = editing.assemble_edits(args.project,args.run,args.join_review)
        elif args.command == "prepare":
            result = [{"shot_id":job["shot"]["id"],"job_digest":job["job_digest"],"settings":job["settings"]} for job in prepare(args.project)]
        elif args.command == "reserve":
            result = {"attempt":reserve_and_pack(args.project,args.shot).name}
        elif args.command == "submit":
            result = submit(args.project,args.attempt,args.session,args.timeout)
        elif args.command == "fetch":
            result = fetch(args.project,args.attempt)
        elif args.command == "status":
            result = status(args.project,args.attempt)
        elif args.command == "inspect":
            directory = args.project.resolve() / "attempts" / identifier(args.attempt)
            manifest = evidence(directory)
            result = {"evidence":str(directory / "evidence"),"sampled_frames":manifest["sampled_frames"],"state":"needs_review"}
        elif args.command == "review":
            result = accept_review(args.project.resolve() / "attempts" / identifier(args.attempt),args.file)
        elif args.command == "joins":
            manifest = joins(args.project,read_json(args.selection))
            result = {"pairs":len(manifest["pairs"]),"review_template":str(args.project / "joins" / "review-template.json")}
        else:
            result = assemble(args.project,read_json(args.selection),args.join_review)
        print(json.dumps(result,ensure_ascii=False,indent=2))
    except (ValueError,KeyError,FileNotFoundError,RuntimeError) as exc:
        parser.exit(1,f"{type(exc).__name__}: {exc}\n")


if __name__ == "__main__":
    main()
