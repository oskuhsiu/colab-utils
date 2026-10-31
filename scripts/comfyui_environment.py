#!/usr/bin/env python3
"""Build wheel-only ComfyUI overlays; restore them against an identical Linux base.

Build on a CPU host with the target VM's Python, Linux image and preinstalled
CUDA PyTorch distributions. No GPU is accessed. This is a directory artifact:
copy the whole directory, including hidden Git files, to the target VM.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import shutil
import subprocess
import sys
import tempfile
from urllib.parse import unquote, urlsplit
import zipfile
from email.parser import BytesParser


SCHEMA_VERSION = 1
PROBE = r'''
import ast, importlib.metadata as m, json, platform, sys, sysconfig
def canonical(name):
    import re
    return re.sub(r"[-_.]+", "-", name).lower()
packages = sorted([{'name': canonical(d.metadata['Name']), 'version': d.version}
                   for d in m.distributions() if d.metadata.get('Name')],
                  key=lambda d: (d['name'], d['version']))
cuda = None
try:
    tree = ast.parse(m.distribution('torch').locate_file('torch/version.py').read_text())
    for node in tree.body:
        targets = node.targets if isinstance(node, ast.Assign) else [node.target] if isinstance(node, ast.AnnAssign) else []
        if any(isinstance(t, ast.Name) and t.id == 'cuda' for t in targets):
            cuda = ast.literal_eval(node.value)
except (m.PackageNotFoundError, OSError, ValueError, SyntaxError):
    pass
print(json.dumps({'python': {'implementation': sys.implementation.name,
    'minor': list(sys.version_info[:2]), 'soabi': sysconfig.get_config_var('SOABI')},
    'platform': {'system': platform.system(), 'machine': platform.machine(),
                 'platform': sysconfig.get_platform(), 'libc': list(platform.libc_ver())},
    'distributions': packages,
    'effective': {n: m.version(n) for n in sorted({d['name'] for d in packages})},
    'torch_cuda': cuda}))
'''


def _canonical(name):
    return re.sub(r"[-_.]+", "-", name).lower()


def _gpu(name):
    return name in {"torch", "torchvision", "torchaudio", "triton"} or name.startswith(("nvidia-", "pytorch-triton"))


def _run(command, cwd=None):
    try:
        result = subprocess.run(list(map(str, command)), cwd=cwd, check=True,
                                stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    except subprocess.CalledProcessError as error:
        raise RuntimeError(f"Environment command failed: {error.stderr.strip()}") from error
    return result.stdout


def _probe(python=sys.executable):
    return json.loads(_run([python, "-c", PROBE]))


def _base():
    base = _probe()
    if base["platform"]["system"] != "Linux" or base["platform"]["machine"] != "x86_64":
        raise RuntimeError("Environment packs require Linux x86_64; build in the target VM's base image")
    packages = base["effective"]
    if "torch" not in packages or not base["torch_cuda"]:
        raise RuntimeError("A preinstalled CUDA PyTorch base is required (a GPU is not required)")
    return base


def _digest(path):
    value = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            value.update(chunk)
    return value.hexdigest()


def _json_digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True).encode()).hexdigest()


def _write_json(path, value):
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n")


def _relative(value):
    path = PurePosixPath(value)
    if not value or path.is_absolute() or ".." in path.parts or "\\" in value or str(path) != value:
        raise RuntimeError(f"Unsafe pack path: {value!r}")
    return path


def _files(root):
    result = {}
    for path in sorted(root.rglob("*")):
        if path.is_symlink():
            raise RuntimeError(f"Symlinks are not supported in environment packs: {path}")
        if path.is_file():
            result[path.relative_to(root).as_posix()] = {"sha256": _digest(path), "size": path.stat().st_size,
                                                       "mode": path.stat().st_mode & 0o777}
        elif not path.is_dir():
            raise RuntimeError(f"Unsupported pack file: {path}")
    return result


def _sources(workspace):
    sources = [{"path": "ComfyUI", **workspace.catalog["comfyui"]}]
    for name in workspace.extensions:
        spec = workspace.catalog["extensions"][name]
        _relative(spec["directory"])
        sources.append({"path": "ComfyUI/custom_nodes/" + spec["directory"], **spec})
    for spec in sources:
        if not re.fullmatch(r"[0-9a-f]{40}", spec["revision"]):
            raise RuntimeError("Source revisions must be full Git commit SHAs")
    return sources


def _checkout(spec, destination):
    destination.mkdir(parents=True, exist_ok=True)
    _run(["git", "init", destination])
    _run(["git", "-C", destination, "remote", "add", "origin", spec["repo"]])
    _run(["git", "-C", destination, "fetch", "--depth", "1", "origin", spec["revision"]])
    _run(["git", "-C", destination, "checkout", "--detach", "FETCH_HEAD"])
    if _run(["git", "-C", destination, "rev-parse", "HEAD"]).strip() != spec["revision"]:
        raise RuntimeError("Source checkout does not match its pinned revision")
    if _run(["git", "-C", destination, "status", "--porcelain", "--untracked-files=normal"]).strip():
        raise RuntimeError("Source checkout is dirty")
    if (destination / ".gitmodules").exists():
        raise RuntimeError("Git submodule sources need an explicit snapshot implementation")


def _wheel_metadata(path):
    with zipfile.ZipFile(path) as archive:
        metadata = [name for name in archive.namelist() if name.endswith(".dist-info/METADATA")]
        if len(metadata) != 1:
            raise RuntimeError(f"Invalid wheel metadata: {path.name}")
        value = BytesParser().parsebytes(archive.read(metadata[0]))
    return _canonical(value["Name"]), value["Version"]


def _validate_requirements(path, extra):
    # pip's only-binary setting does not forbid explicitly supplied sdist/VCS
    # URLs. Reject those before pip can execute any build backend for metadata.
    requirements = [line.split("#", 1)[0].strip() for line in path.read_text().splitlines()]
    for requirement in [*requirements, *extra]:
        if not requirement:
            continue
        if (not re.match(r"^[A-Za-z0-9][A-Za-z0-9_.-]*(?:\[|\s|[<>=!~;]|$)", requirement)
                or any(char in requirement for char in ("@", "/", "\\"))):
            raise RuntimeError(f"Only named index requirements are supported: {requirement}")


def build_environment(workspace, output_dir):
    """Resolve/download an overlay without installing packages or touching workspace."""
    from comfyui_workspace import DOWNLOAD_REQUIREMENTS

    base = _base()  # Reject unsupported build machines before any mutation/network.
    sources = _sources(workspace)
    output = Path(output_dir).expanduser().resolve()
    if output.exists() and (not output.is_dir() or any(output.iterdir())):
        raise RuntimeError("Environment output must be absent or an empty directory")
    output.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix=".comfy-environment-", dir=output.parent) as temporary:
        pack = Path(temporary) / "pack"
        pack.mkdir()
        for spec in sources:
            _checkout(spec, pack / "sources" / spec["path"])
        gpu = {name: version for name, version in base["effective"].items() if _gpu(name)}
        constraints = pack / "gpu-constraints.txt"
        constraints.write_text("".join(f"{name}=={version}\n" for name, version in sorted(gpu.items())))
        report_path = Path(temporary) / "resolution.json"
        requirements = [item for name in workspace.extensions
                        for item in workspace.catalog["extensions"][name]["requirements"]]
        requirements.extend(DOWNLOAD_REQUIREMENTS)
        _validate_requirements(pack / "sources/ComfyUI/requirements.txt", requirements)
        _run([sys.executable, "-m", "pip", "install", "--dry-run", "--report", report_path,
              "--disable-pip-version-check", "--only-binary=:all:", "-c", constraints,
              "-r", pack / "sources/ComfyUI/requirements.txt", *requirements])
        report = json.loads(report_path.read_text())
        wheelhouse = pack / "wheelhouse"
        wheelhouse.mkdir()
        locked = []
        for item in report["install"]:
            name, version = _canonical(item["metadata"]["name"]), item["metadata"]["version"]
            if _gpu(name):
                raise RuntimeError(f"Resolver attempted to replace the base GPU stack: {name}")
            url = item["download_info"]["url"]
            filename = unquote(urlsplit(url).path.rsplit("/", 1)[-1])
            if "/" in filename or "\\" in filename or not filename.endswith(".whl"):
                raise RuntimeError(f"Only wheel artifacts are supported: {name}")
            expected = item["download_info"].get("archive_info", {}).get("hashes", {}).get("sha256")
            if not expected or not re.fullmatch(r"[0-9a-f]{64}", expected):
                raise RuntimeError(f"Resolver did not provide a wheel SHA-256: {name}")
            _run([sys.executable, "-m", "pip", "download", "--disable-pip-version-check",
                  "--no-deps", "--only-binary=:all:", "--dest", wheelhouse, url])
            wheel = wheelhouse / filename
            if not wheel.is_file() or _digest(wheel) != expected or _wheel_metadata(wheel) != (name, version):
                raise RuntimeError(f"Downloaded wheel differs from the resolution: {name}")
            locked.append({"name": name, "version": version, "file": "wheelhouse/" + filename,
                           "sha256": expected})
        if len({item["name"] for item in locked}) != len(locked):
            raise RuntimeError("Resolver returned duplicate distributions")
        (pack / "requirements.lock").write_text("".join(
            f"{item['name']}=={item['version']} --hash=sha256:{item['sha256']}\n"
            for item in sorted(locked, key=lambda item: item["name"])))
        if _probe() != base:
            raise RuntimeError("Build base changed while resolving dependencies")
        manifest = {"schema_version": SCHEMA_VERSION, "signature": workspace._signature(),
                    "sources": sources, "base": base, "base_fingerprint": _json_digest(base),
                    "gpu_stack": gpu, "locked": locked, "files": _files(pack),
                    "gpu_generation": "not_run"}
        _write_json(pack / "manifest.json", manifest)
        if output.exists():
            output.rmdir()
        pack.rename(output)
    return manifest


def inspect_environment(environment_dir):
    """Read and verify every artifact locally; never executes pip/Git or contacts a remote."""
    root = Path(environment_dir).expanduser().resolve()
    if (root / "manifest.json").is_symlink():
        raise RuntimeError("Manifest cannot be a symlink")
    manifest = json.loads((root / "manifest.json").read_text())
    if manifest.get("schema_version") != SCHEMA_VERSION:
        raise RuntimeError("Unsupported environment pack schema")
    if manifest.get("base_fingerprint") != _json_digest(manifest["base"]):
        raise RuntimeError("Invalid base fingerprint")
    expected = manifest["files"]
    for name in expected:
        _relative(name)
    actual = _files(root)
    actual.pop("manifest.json", None)
    if actual != expected:
        raise RuntimeError("Environment pack integrity check failed (missing, changed or extra files)")
    return manifest


def _expected_distributions(manifest):
    # importlib.metadata can expose both base and overlay dist-info. Compare the
    # effective lookup as well as the complete base inventory at restore entry.
    expected = dict(manifest["base"]["effective"])
    expected.update({d["name"]: d["version"] for d in manifest["locked"]})
    return expected


def _verify_overlay(python, manifest):
    effective = json.loads(_run([python, "-c", "import importlib.metadata as m,json; "
        "names=" + repr(sorted(_expected_distributions(manifest))) + "; "
        "print(json.dumps({n:m.version(n) for n in names}))"]))
    if effective != _expected_distributions(manifest):
        raise RuntimeError("Installed distributions differ from the locked overlay; GPU stack must remain unchanged")
    return effective


def _preflight_destination(workspace, manifest):
    root = workspace.root
    if root.is_symlink():
        raise RuntimeError("Workspace root cannot be a symlink")
    for name, record in manifest["files"].items():
        if not name.startswith("sources/"):
            continue
        destination = root / name.removeprefix("sources/")
        for ancestor in (destination, *destination.parents):
            if ancestor.is_symlink():
                raise RuntimeError(f"Workspace contains a symlink: {ancestor}")
            if ancestor == root:
                break
        if destination.exists() and (not destination.is_file() or _digest(destination) != record["sha256"]
                                     or destination.stat().st_mode & 0o777 != record["mode"]):
            raise RuntimeError(f"Source conflicts with an existing workspace file: {destination}")
        if any(parent.exists() and not parent.is_dir() for parent in destination.parents if parent != root):
            raise RuntimeError(f"Source parent conflicts with a workspace file: {destination}")
    venv = root / "venv"
    if venv.is_symlink():
        raise RuntimeError("Workspace venv cannot be a symlink")
    receipt_path = workspace.state / "installed.json"
    receipt = json.loads(receipt_path.read_text()) if receipt_path.exists() else {}
    if venv.exists():
        if (receipt.get("signature") != manifest["signature"] or
                receipt.get("environment_pack") != _json_digest(manifest) or not workspace.python.is_file()):
            raise RuntimeError("Existing venv is not this environment pack; use a new workspace root")
        _verify_overlay(workspace.python, manifest)
        return receipt
    if receipt_path.exists():
        raise RuntimeError("Existing install receipt has no matching venv; use a new workspace root")
    for path in (workspace.state, receipt_path, workspace.state / "versions.txt",
                 workspace.state / "gpu-constraints.txt", workspace.state / "installed.json.tmp"):
        if path.is_symlink() or (path.exists() and path.is_file() and path != receipt_path):
            raise RuntimeError(f"State destination already exists: {path}")
    return None


def _publish_state_file(path, data, created):
    """Publish complete state without replacing a file another writer created."""
    descriptor, temporary = tempfile.mkstemp(prefix="." + path.name + ".", dir=path.parent)
    try:
        with os.fdopen(descriptor, "wb") as stream:
            stream.write(data)
        identity = Path(temporary).stat()
        os.link(temporary, path)
        created.append((path, identity.st_dev, identity.st_ino, hashlib.sha256(data).hexdigest()))
    finally:
        Path(temporary).unlink(missing_ok=True)


def _cleanup_state_files(created):
    for path, device, inode, digest in reversed(created):
        try:
            actual = path.lstat()
            if (not path.is_symlink() and (actual.st_dev, actual.st_ino) == (device, inode)
                    and _digest(path) == digest):
                path.unlink()
        except OSError:
            pass


def restore_environment(workspace, environment_dir):
    """Restore sources and create a fresh system-site-packages venv, fully offline."""
    pack = Path(environment_dir).expanduser().resolve()
    manifest = inspect_environment(pack)
    if workspace._signature() != manifest["signature"] or _sources(workspace) != manifest["sources"]:
        raise RuntimeError("Environment pack selection/source signature differs from the workspace")
    if _base() != manifest["base"]:
        raise RuntimeError("Base Python ABI/platform/distribution fingerprint mismatch; rebuild the pack for this base")
    if workspace._port_open():
        raise RuntimeError("Stop the ComfyUI server before restoring its environment")
    marker = workspace._server_marker()
    if marker and workspace._process_identity(marker.get("pid")) == marker.get("identity"):
        raise RuntimeError("Stop the existing workspace process before restoring its environment")
    receipt = _preflight_destination(workspace, manifest)
    if receipt:
        return receipt
    workspace.root.mkdir(parents=True, exist_ok=True)
    for name, record in manifest["files"].items():
        if name.startswith("sources/"):
            destination = workspace.root / name.removeprefix("sources/")
            if not destination.exists():
                destination.parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(pack / name, destination)
                destination.chmod(record["mode"])
    venv = workspace.root / "venv"
    created_state = []
    try:
        _run([sys.executable, "-m", "venv", "--system-site-packages", "--without-pip", venv])
        if manifest["locked"]:
            _run([workspace.python, "-m", "pip", "install", "--disable-pip-version-check", "--no-index",
                  "--no-deps", "--only-binary=:all:", "--require-hashes", "--find-links", pack / "wheelhouse",
                  "-c", pack / "gpu-constraints.txt", "-r", pack / "requirements.lock"])
        versions = _verify_overlay(workspace.python, manifest)
        if _probe() != manifest["base"]:
            raise RuntimeError("Base GPU stack/distributions changed during restore")
        workspace.state.mkdir(parents=True, exist_ok=True)
        _publish_state_file(workspace.state / "versions.txt",
                            "".join(f"{n}=={v}\n" for n, v in sorted(versions.items())).encode(), created_state)
        _publish_state_file(workspace.state / "gpu-constraints.txt",
                            (pack / "gpu-constraints.txt").read_bytes(), created_state)
        result = {"signature": workspace._signature(), "plan": workspace.plan(),
                  "environment": {"packages": versions, "cuda": manifest["base"]["torch_cuda"],
                                  "cuda_available": None, "gpu": None},
                  "environment_pack": _json_digest(manifest), "gpu_generation": "not_run"}
        # The receipt is the completion marker and is published last.
        _publish_state_file(workspace.state / "installed.json",
                            (json.dumps(result, indent=2, sort_keys=True) + "\n").encode(), created_state)
        return result
    except BaseException:
        _cleanup_state_files(created_state)
        # This venv was created by this attempt; leave restored sources reusable.
        if venv.is_dir() and not venv.is_symlink():
            shutil.rmtree(venv)
        raise


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    build = sub.add_parser("build", help="Resolve wheels on the matching Linux CPU base; no package installation")
    build.add_argument("output_dir")
    build.add_argument("--root", default="/content/comfyui-workspace")
    build.add_argument("--extensions", default="continuum,ref2va-vsa")
    inspect = sub.add_parser("inspect", help="Verify a pack locally without installing anything")
    inspect.add_argument("environment_dir")
    args = parser.parse_args(argv)
    if args.command == "inspect":
        result = inspect_environment(args.environment_dir)
    else:
        from comfyui_workspace import ComfyWorkspace
        result = build_environment(ComfyWorkspace(args.root, extensions=args.extensions), args.output_dir)
    print(json.dumps(result, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
