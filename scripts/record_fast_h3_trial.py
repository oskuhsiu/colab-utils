#!/usr/bin/env python3
"""Capture a trial command's actual clock, exit code and stdout/stderr files."""
from datetime import datetime, timezone
import argparse
import json
from pathlib import Path
import re
import subprocess
import time


def run(root, label, command):
    root = Path(root); root.mkdir(parents=True, exist_ok=True)
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_-]*", label) or not command:
        raise ValueError("Choose a safe unique label and an explicit command argument list")
    record_path = root / (label + ".command.json")
    files = [root / (label + suffix) for suffix in (".stdout.log", ".stderr.log", ".command.json")]
    if any(p.exists() for p in files):
        raise FileExistsError("Command label already recorded; choose a new label")
    record = {"label": label, "argv": command, "started_utc": datetime.now(timezone.utc).isoformat(),
              "stdout": files[0].name, "stderr": files[1].name, "scope": "Actual subprocess only"}
    started = time.perf_counter()
    try:
        with files[0].open("x") as out, files[1].open("x") as err:
            result = subprocess.run(command, stdout=out, stderr=err, check=False)
        record["exit_code"] = result.returncode
    except BaseException as error:
        record.update(exit_code=None, error_type=type(error).__name__)
        raise
    finally:
        record.update(finished_utc=datetime.now(timezone.utc).isoformat(),
                      phase_elapsed_seconds=time.perf_counter() - started)
        record_path.write_text(json.dumps(record, indent=2, ensure_ascii=False) + "\n")
        with (root / "commands.jsonl").open("a") as stream:
            stream.write(json.dumps(record, ensure_ascii=False) + "\n")
    return record


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--root", type=Path, required=True)
    p.add_argument("--label", required=True)
    p.add_argument("command", nargs=argparse.REMAINDER)
    args = p.parse_args()
    command = args.command[1:] if args.command[:1] == ["--"] else args.command
    if not command: p.error("Supply the actual command after --")
    result = run(args.root, args.label, command)
    print(json.dumps(result, ensure_ascii=False))
    raise SystemExit(result["exit_code"])


if __name__ == "__main__": main()
