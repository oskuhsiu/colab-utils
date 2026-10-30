#!/usr/bin/env python3
"""Seal explicitly selected trial files and verify bytes without manual hashes."""
import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path


def owned(root, name):
    root = Path(root).resolve()
    path = root / name
    if Path(name).is_absolute() or path.is_symlink() or not path.resolve().is_relative_to(root):
        raise ValueError("Select regular files inside the trial directory")
    return path


def digest(path):
    value = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            value.update(block)
    return value.hexdigest()


def seal(root, names, manifest="manifest.json"):
    target = owned(root, manifest)
    if manifest in names or len(names) != len(set(names)):
        raise ValueError("Manifest cannot hash itself; select each evidence file once")
    files = []
    for name in names:
        path = owned(root, name)
        files.append({"path": name, "bytes": path.stat().st_size, "sha256": digest(path)})
    result = {"schema_version": 1, "sealed_utc": datetime.now(timezone.utc).isoformat(),
              "files": files, "scope": "Selected final evidence only; later changes invalidate the seal"}
    target.parent.mkdir(parents=True, exist_ok=True)
    with target.open("x") as stream:
        stream.write(json.dumps(result, indent=2, ensure_ascii=False) + "\n")
    return result


def verify(root, manifest="manifest.json"):
    result = json.loads(owned(root, manifest).read_text())
    errors = []
    for item in result["files"]:
        path = owned(root, item["path"])
        if not path.is_file() or path.stat().st_size != item["bytes"] or digest(path) != item["sha256"]:
            errors.append(item["path"])
    return {"verified": not errors, "file_count": len(result["files"]), "errors": errors}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("seal", "verify"))
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--manifest", default="manifest.json")
    parser.add_argument("--files", nargs="+")
    args = parser.parse_args()
    if args.action == "seal":
        if not args.files:
            parser.error("Choose final evidence with --files; do not include credentials or the manifest itself")
        seal(args.root, args.files, args.manifest)
    result = verify(args.root, args.manifest)
    print(json.dumps(result))
    if not result["verified"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
