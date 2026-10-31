"""Shared native Omni job, evidence and media helpers; no GPU imports."""
from __future__ import annotations
import datetime as dt
import hashlib
from fractions import Fraction
import json
import math
import os
from pathlib import Path, PurePosixPath
import re
import shutil
import subprocess
import sys
import time
import zipfile

HERE = Path(__file__).resolve().parent
# Sealed deployments carry toolkit/; source checkouts use the parent scripts/.
sys.path.insert(0, str(HERE / 'toolkit' if (HERE / 'toolkit').is_dir() else HERE.parent))
from comfyui_workspace import ComfyWorkspace
from comfyui_workflows import build_graph, node
from fast_h3_client import PromptExecutionError, PromptTimeoutError

PRODUCTION = Path('/content/omni-production')
WORKSPACE = Path('/content/omni-workspace')
BUNDLE = 'h3-omni-int8'
PORT = 8190


def now():
    return dt.datetime.now(dt.timezone.utc).isoformat()


def write_json(path, value, immutable=False):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    if immutable:
        with path.open('x') as out:
            json.dump(value, out, indent=2, ensure_ascii=False)
            out.write('\n')
    else:
        temporary = path.with_suffix(path.suffix + '.tmp')
        temporary.write_text(json.dumps(value, indent=2, ensure_ascii=False) + '\n')
        os.replace(temporary, path)


def marker(event, **values):
    print('OMNI_' + event + ' ' + json.dumps({'utc': now(), **values}, ensure_ascii=False), flush=True)


def remaining(deadline_utc=None):
    if not deadline_utc:
        return None
    deadline = dt.datetime.fromisoformat(deadline_utc.replace('Z', '+00:00'))
    if deadline.tzinfo is None:
        raise ValueError('deadline_utc must include timezone')
    seconds = (deadline - dt.datetime.now(dt.timezone.utc)).total_seconds()
    if seconds <= 0:
        raise TimeoutError('deadline_utc reached; refusing new work')
    return seconds


def bounded_wait(seconds, deadline_utc=None):
    if type(seconds) not in (int, float) or not math.isfinite(seconds) or seconds <= 0:
        raise ValueError('timeout_seconds must be positive and finite')
    left = remaining(deadline_utc)
    return seconds if left is None else min(seconds, left)


def workspace():
    ws = ComfyWorkspace(root=WORKSPACE, port=PORT, extensions=[])
    # Canonical installer/server/model logs all live under production.
    ws.state = PRODUCTION / 'state'
    ws.state.mkdir(parents=True, exist_ok=True)
    return ws


def hardware():
    result = subprocess.run(['nvidia-smi', '--query-gpu=name,memory.total,uuid', '--format=csv,noheader'],
                            capture_output=True, text=True, timeout=20)
    evidence = {'utc': now(), 'command': result.args, 'exit_code': result.returncode,
                'stdout': result.stdout, 'stderr': result.stderr}
    write_json(PRODUCTION / 'hardware.json', evidence)
    lines = [line.strip() for line in result.stdout.splitlines() if line.strip()]
    if result.returncode or len(lines) != 1 or not re.search(r'\bA100\b', lines[0]):
        raise RuntimeError('Exactly one confirmed NVIDIA A100 required; see hardware.json')
    return evidence


def shot_id(value):
    if not isinstance(value, str) or not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_.-]{0,79}', value):
        raise ValueError('shot_id must be filename-safe, 1–80 characters')
    return value


def graph_for_job(job):
    """Bind Picture N to reference_images[N-1] without changing Subject tags."""
    identity = shot_id(job['shot_id'])
    if job.get('preset', BUNDLE) != BUNDLE:
        raise ValueError('This adapter requires the native h3-omni-int8 preset')
    context_keys = ('window_prompts', 'context_length', 'context_overlap', 'fuse_method',
                    'freenoise', 'split_conds_to_windows')
    if any(key in job for key in context_keys):
        raise ValueError('Context-window settings require a separate adapter')
    refs = job['reference_images']
    if not isinstance(refs, list) or not 1 <= len(refs) <= 9:
        raise ValueError('reference_images must contain 1–9 distinct input image filenames')
    for value in refs:
        if (not isinstance(value, str) or not value or '\\' in value or
                PurePosixPath(value).is_absolute() or
                any(part in ('', '.', '..') for part in value.split('/')) or
                PurePosixPath(value).suffix.lower() not in ('.png', '.jpg', '.jpeg', '.webp')):
            raise ValueError('Each reference must be a relative ComfyUI input image filename')
    if len(set(refs)) != len(refs):
        raise ValueError('reference_images must contain distinct input image filenames')
    prompt = job['prompt']
    if not isinstance(prompt, str):
        raise ValueError('prompt must be a final six-field string')
    tags = re.findall(r'<(Picture|Video|Audio)\s+(\d+)>', prompt, flags=re.I)
    if {(kind.lower(), int(number)) for kind, number in tags} != {('picture', i + 1) for i in range(len(refs))}:
        raise ValueError('Prompt Picture tags must match every supplied image, consecutively from 1')
    # The canonical builder validates one picture. Validate the same six fields
    # with equivalent Picture tags, then restore the exact multi-picture prompt.
    # Subject numbers are independent of image positions and remain untouched.
    single_prompt = re.sub(r'<Picture\s+\d+>', '<Picture 1>', prompt, flags=re.I)
    graph = build_graph(BUNDLE, prompt=single_prompt,
                        width=job.get('width', 768), height=job.get('height', 448),
                        duration_seconds=job['duration_seconds'], seed=job['seed'],
                        reference_image=refs[0], run_name=identity,
                        ref_image_size=job.get('ref_image_size'))
    graph['11']['inputs']['prompt'] = prompt
    for index, image in enumerate(refs[1:], start=1):
        node_id = str(max(int(key) for key in graph) + 1)
        graph[node_id] = node('LoadImage', image=image)
        # Pinned native io.Autogrow.TemplatePrefix prefix='ref_image_', max=9.
        graph['11']['inputs'][f'ref_images.ref_image_{index}'] = [node_id, 0]
    return graph


def file_digest(path):
    digest = hashlib.sha256()
    with Path(path).open('rb') as source:
        for block in iter(lambda: source.read(1024 * 1024), b''):
            digest.update(block)
    return digest.hexdigest()


def snapshot_references(ws, job, directory):
    base = (ws.comfy / 'input').resolve()
    evidence = []
    for index, name in enumerate(job['reference_images'], start=1):
        path = (base / name).resolve()
        if not path.is_relative_to(base) or not path.is_file() or path.stat().st_size == 0:
            raise FileNotFoundError(f'Reference missing or outside ComfyUI input: {name}')
        destination = directory / 'references' / f'picture-{index}{path.suffix.lower()}'
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(path, destination)
        evidence.append({'picture': index, 'input_filename': name, 'sha256': file_digest(path),
                         'bytes': path.stat().st_size, 'snapshot': str(destination.relative_to(directory))})
    write_json(directory / 'references.json', evidence, immutable=True)


def finish(ws, directory, history):
    """Fetch existing output, validate A/V fully, then publish result; never queue."""
    job = json.loads((directory / 'job.json').read_text())
    receipt_path = directory / 'receipt.json'
    receipt = json.loads(receipt_path.read_text())
    write_json(directory / 'history.json', history)
    outputs = ws.client.output_files(history)
    if len(outputs) != 1 or Path(outputs[0]['filename']).suffix.lower() != '.mp4':
        raise RuntimeError(f'Expected one MP4, found {len(outputs)} media outputs')
    media = directory / 'media.mp4'
    ws.client.download_output(outputs[0], media)
    if not media.is_file() or media.stat().st_size == 0:
        raise RuntimeError('Media is missing or empty')
    probe = subprocess.run(['ffprobe', '-v', 'error', '-show_streams', '-show_format',
                            '-of', 'json', str(media)], capture_output=True, text=True, timeout=60)
    (directory / 'ffprobe.stderr.log').write_text(probe.stderr)
    if probe.returncode:
        raise RuntimeError('ffprobe failed')
    info = json.loads(probe.stdout)
    write_json(directory / 'ffprobe.json', info)
    videos = [s for s in info['streams'] if s['codec_type'] == 'video']
    audios = [s for s in info['streams'] if s['codec_type'] == 'audio']
    graph = json.loads((directory / 'workflow.api.json').read_text())
    expected = graph['11']['inputs']
    if len(videos) != 1 or not audios or (videos[0]['width'], videos[0]['height']) != (expected['width'], expected['height']):
        raise RuntimeError('Expected canvas and both video/audio streams required')
    if Fraction(videos[0].get('avg_frame_rate', '0/1')) != 24:
        raise RuntimeError('Expected 24fps video')
    if int(videos[0].get('nb_frames', 0)) != expected['length']:
        raise RuntimeError('Video frame count differs from native frame grid')
    actual_duration = float(info['format']['duration'])
    if abs(actual_duration - expected['length'] / 24) > .25:
        raise RuntimeError('Media duration differs from native frame grid')
    # Map both streams explicitly and fail on decode errors, including late ones.
    with (directory / 'decode.log').open('w') as log:
        decoded = subprocess.run(['ffmpeg', '-v', 'error', '-xerror', '-err_detect', 'explode',
                                  '-i', str(media), '-map', '0:v:0', '-map', '0:a:0', '-f', 'null', '-'],
                                 stdout=log, stderr=subprocess.STDOUT, timeout=180)
    if decoded.returncode:
        raise RuntimeError('Full video/audio decode failed; see decode.log')
    receipt.update(status='complete_media_verified', completed_utc=now(), media_validation='ffprobe_and_full_decode_pass',
                   content_review='not_run', media_sha256=file_digest(media), media_bytes=media.stat().st_size,
                   output_item=outputs[0], actual_duration_seconds=actual_duration)
    write_json(receipt_path, receipt)
    result_dir = PRODUCTION / 'results'
    result_dir.mkdir(exist_ok=True)
    target = result_dir / (job['shot_id'] + '.zip')
    temp = target.with_suffix('.zip.tmp')
    with zipfile.ZipFile(temp, 'w', zipfile.ZIP_DEFLATED) as archive:
        for path in sorted(directory.rglob('*')):
            if path.is_file():
                archive.write(path, str(Path(job['shot_id']) / path.relative_to(directory)))
        for path in sorted((PRODUCTION / 'state').glob('*')):
            if path.is_file() and path.suffix in ('.json', '.txt', '.log'):
                archive.write(path, 'setup-evidence/' + path.name)
        for name in ('hardware.json', 'setup-status.json', 'plan.json', 'toolkit-manifest.json'):
            path = PRODUCTION / name
            if path.is_file():
                archive.write(path, 'setup-evidence/' + name)
    os.replace(temp, target)
    marker('SHOT_COMPLETE', shot_id=job['shot_id'], prompt_id=receipt['prompt_id'],
           zip_path=str(target), media_path=str(media), media_validation=receipt['media_validation'])
    return target
