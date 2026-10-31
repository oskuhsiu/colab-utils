#!/usr/bin/env python3
"""Bounded, pinned HF downloads with verified hardlinks into ComfyUI/models.

Importing this module requires only the standard library. Transfers lazily require
``huggingface_hub`` and ``hf_xet``; Xet keeps its official adaptive defaults.
The module does not clear the HF cache; the SDK owns partial-file lifetime.
Completed files can be reused. An interrupted file may restart from byte zero
after the process ends. Model files share the cache inode; keep them read-only.
"""
from __future__ import annotations

import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed
import hashlib
import importlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import sys
import tempfile
import threading
import time


class AssetDownloadError(RuntimeError):
    """A safe summary; the chained exception retains detailed SDK diagnostics."""


def _relative(value, label):
    if (not isinstance(value, str) or not value or "\\" in value
            or any(ord(char) < 32 for char in value)
            or PurePosixPath(value).is_absolute()
            or any(part in ("", ".", "..") for part in value.split("/"))):
        raise ValueError(f"{label} must be a relative POSIX file path")
    return value


def _target(root, destination):
    path = root / _relative(destination, "destination")
    if not path.resolve().is_relative_to(root):
        raise ValueError("Model destination leaves model_root")
    return path


def _asset(value):
    asset = {key: value[key] for key in ("repo", "revision", "file", "size", "sha256", "destination")}
    if not isinstance(asset["repo"], str) or not re.fullmatch(r"[\w.-]+/[\w.-]+", asset["repo"], re.ASCII):
        raise ValueError("repo must be a Hugging Face namespace/repository")
    if any(part in (".", "..") for part in asset["repo"].split("/")):
        raise ValueError("Invalid repository")
    if not isinstance(asset["revision"], str) or not re.fullmatch(r"[0-9a-f]{40}", asset["revision"]):
        raise ValueError("revision must be a full commit SHA")
    if not isinstance(asset["sha256"], str) or not re.fullmatch(r"[0-9a-f]{64}", asset["sha256"]):
        raise ValueError("sha256 must be a complete SHA-256")
    if type(asset["size"]) is not int or asset["size"] < 0:
        raise ValueError("size must be a nonnegative byte count")
    _relative(asset["file"], "file")
    _relative(asset["destination"], "destination")
    return asset


def _verify(path, asset):
    if not path.is_file() or path.stat().st_size != asset["size"]:
        raise RuntimeError("File size differs from the pinned asset")
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(8 * 1024 * 1024), b""):
            digest.update(chunk)
    if digest.hexdigest() != asset["sha256"]:
        raise RuntimeError("File SHA-256 differs from the pinned asset")


def _download(asset, cache):
    # Never replace an SDK error with another downloader. Missing/disabled Xet is
    # actionable, rather than an unnoticed change of transfer configuration.
    importlib.import_module("hf_xet")
    hub = importlib.import_module("huggingface_hub")
    constants = importlib.import_module("huggingface_hub.constants")
    if constants.HF_HUB_DISABLE_XET:
        raise RuntimeError("HF_HUB_DISABLE_XET is enabled; Xet is required")
    # HF owns transfer concurrency, cache locking, retries, and partial files.
    return Path(hub.hf_hub_download(repo_id=asset["repo"], filename=asset["file"],
                                   revision=asset["revision"], cache_dir=str(cache)))


def _error(exc, stage):
    # Exception messages can contain signed URLs and tokens. Persist only safe,
    # structured diagnostics; callers can inspect the chained original error.
    result = {"type": type(exc).__name__, "stage": stage}
    status = getattr(getattr(exc, "response", None), "status_code", None)
    if type(status) is int:
        result["http_status"] = status
    if type(getattr(exc, "errno", None)) is int:
        result["errno"] = exc.errno
    return result


class _Progress:
    def __init__(self, assets, path, workers):
        self.path = Path(path).expanduser().resolve() if path is not None else None
        self.lock = threading.Lock()
        self.value = {"schema_version": 1, "status": "in_progress", "max_workers": workers,
                      "total_bytes": sum(asset["size"] for asset in assets),
                      "verified_bytes": 0,
                      "assets": [{**asset, "status": "pending", "verified_bytes": 0}
                                 for asset in assets]}
        self.update()

    def update(self, index=None, **changes):
        with self.lock:
            if index is None:
                self.value.update(changes)
            else:
                self.value["assets"][index].update(changes)
            self.value["verified_bytes"] = sum(item["verified_bytes"] for item in self.value["assets"])
            self.value["updated_at"] = time.time()
            if self.path is None:
                return
            self.path.parent.mkdir(parents=True, exist_ok=True)
            descriptor, temporary = tempfile.mkstemp(prefix="." + self.path.name + ".", dir=self.path.parent)
            try:
                with os.fdopen(descriptor, "w", encoding="utf-8") as stream:
                    json.dump(self.value, stream, ensure_ascii=False, indent=2)
                    stream.write("\n")
                    stream.flush()
                    os.fsync(stream.fileno())
                os.replace(temporary, self.path)
            finally:
                Path(temporary).unlink(missing_ok=True)


def download_assets(assets, model_root, cache_dir, progress_path=None, max_workers=2):
    """Download exactly ``assets`` and return completed progress plus ``paths``.

    Each asset uses catalog keys repo/revision/file/size/sha256/destination. Only
    one or two simultaneous files are allowed. Both roots must share a filesystem
    (also checked at each destination); no copy fallback is attempted. Existing
    destinations are fully verified and reused, and different files are never
    replaced. This module does not clear HF's cache on failure; the SDK may
    remove temporary files, and retained partials do not guarantee byte resume.

    Progress is atomically written per stage, with verified byte counts rather
    than estimates of network bytes. Stale in_progress means the process may have
    stopped; re-running with the same spec verifies/reuses completed files. On
    failure AssetDownloadError chains the SDK/local exception. Files already in
    progress can finish; queued files are marked cancelled without downloading.
    """
    if type(max_workers) is not int or max_workers not in (1, 2):
        raise ValueError("max_workers must be 1 or 2")
    assets = [_asset(item) for item in assets]
    root, cache = (Path(path).expanduser().resolve() for path in (model_root, cache_dir))
    targets = [_target(root, asset["destination"]) for asset in assets]
    if len(set(path.resolve() for path in targets)) != len(targets):
        raise ValueError("Duplicate model destinations")
    if progress_path is not None and Path(progress_path).expanduser().resolve() in {path.resolve() for path in targets}:
        raise ValueError("progress_path must differ from model destinations")
    progress = _Progress(assets, progress_path, max_workers)
    try:
        root.mkdir(parents=True, exist_ok=True)
        cache.mkdir(parents=True, exist_ok=True)
        if root.stat().st_dev != cache.stat().st_dev:
            raise RuntimeError("cache_dir and model_root must share a filesystem")
    except Exception as exc:
        progress.update(status="failed", error=_error(exc, "preflight"))
        raise AssetDownloadError("Asset preflight failed; inspect progress and cache") from exc

    failed = threading.Event()

    def cancelled(index):
        progress.update(index, status="cancelled", stage="not_started", reason="another_asset_failed")

    def work(index):
        asset, target = assets[index], targets[index]
        stage = "existing_verification"
        try:
            # The worker itself checks the flag: a pool can pick up another
            # queued task before the coordinator observes the failed future.
            if failed.is_set():
                cancelled(index)
                return None
            # Re-evaluate containment at execution in case parents changed since
            # validation, and reject dangling symlinks rather than replacing them.
            target = _target(root, asset["destination"])
            if target.exists() or target.is_symlink():
                progress.update(index, status="verifying", stage=stage)
                _verify(target, asset)
                reused = True
            else:
                target.parent.mkdir(parents=True, exist_ok=True)
                if target.parent.stat().st_dev != cache.stat().st_dev:
                    raise RuntimeError("Cache and destination must share a filesystem")
                stage = "download"
                if failed.is_set():
                    cancelled(index)
                    return None
                progress.update(index, status="downloading", stage=stage)
                source = _download(asset, cache).resolve(strict=True)
                stage = "cache_verification"
                progress.update(index, status="verifying", stage=stage)
                if not source.is_relative_to(cache):
                    raise RuntimeError("HF returned a file outside cache_dir")
                _verify(source, asset)
                stage = "publication"
                progress.update(index, status="publishing", stage=stage)
                _target(root, asset["destination"])
                try:
                    # link creates the final entry atomically and cannot overwrite.
                    os.link(source, target)
                    reused = False
                except FileExistsError:
                    _verify(target, asset)
                    reused = True
            progress.update(index, status="completed", stage="verified", path=str(target),
                            verified_bytes=asset["size"], reused=reused)
            return str(target)
        except Exception as exc:
            failed.set()
            progress.update(index, status="failed", error=_error(exc, stage))
            raise AssetDownloadError(f"Asset {asset['destination']} failed during {stage}; inspect progress and cache") from exc

    paths, failures = [None] * len(assets), []
    with ThreadPoolExecutor(max_workers=max_workers) as pool:
        futures = {pool.submit(work, index): index for index in range(len(assets))}
        for future in as_completed(futures):
            try:
                paths[futures[future]] = future.result()
            except Exception as exc:
                failures.append(exc)
    progress.update(status="failed" if failures else "completed", paths=paths)
    if failures:
        raise failures[0]
    return progress.value


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--spec", required=True, type=Path, help="JSON containing download_assets keyword arguments")
    arguments = parser.parse_args(argv)
    # Set before lazy SDK import; do not alter Xet performance/concurrency flags.
    os.environ.setdefault("HF_HUB_DISABLE_PROGRESS_BARS", "1")
    try:
        spec = json.loads(arguments.spec.read_text(encoding="utf-8"))
        result = download_assets(**spec)
    except Exception as exc:
        # Do not print SDK exception text, which can contain signed URLs.
        print(json.dumps({"status": "failed", "error_type": type(exc).__name__,
                          "detail": "Inspect progress_path and retained cache; no downloader fallback was attempted"}),
              file=sys.stderr)
        return 1
    print(json.dumps({"status": result["status"], "paths": result["paths"],
                      "verified_bytes": result["verified_bytes"]}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
