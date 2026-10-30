"""Local interval conforming; edited media always needs its own evidence review."""
from __future__ import annotations

import copy
import math
from pathlib import Path
import shutil

import media
from workflow import (digest, identifier, local_path, read_json, selected_attempts,
                      sha256, validate_review, write_json)


def _run_path(project, run):
    project = Path(project).resolve()
    path = Path(run)
    if not path.is_absolute():
        path = local_path(project, "edits/" + identifier(str(run)))
    path = path.resolve()
    if path.parent != project / "edits":
        raise ValueError("Edit run must be directly inside project/edits")
    return path


def _number(value):
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value)


def _tempo(speed):
    values = []
    while speed < 0.5 or speed > 2:
        factor = 0.5 if speed < 0.5 else 2
        values.append(f"atempo={factor}")
        speed /= factor
    return ",".join(values + [f"atempo={speed:.12g}"])


def _derived(source, edit, delivery, provenance):
    job = copy.deepcopy(source)
    shot = job["shot"]
    old_width, old_height = shot["width"], shot["height"]
    width, height, fps = delivery["width"], delivery["height"], delivery.get("fps", 24)
    duration, start, end = edit["duration_seconds"], edit["start"], edit["end"]
    ratio = duration / (end - start)
    windows = shot.get("qa", {}).get("event_windows", [])
    for window in windows:
        left, right = max(start, window["start"]), min(end, window["end"])
        if left >= right:
            raise ValueError("Edit excludes a required QA event window; revise the planned edit")
        window.update(start=(left-start)*ratio, end=(right-start)*ratio,
                      fps=min(fps, window.get("fps", 8)))
    scale = min(width / old_width, height / old_height)
    scaled_w, scaled_h = int(old_width*scale)//2*2, int(old_height*scale)//2*2
    for region in shot.get("qa", {}).get("regions", []):
        x, y, w, h = region["box"]
        box = [round((width-scaled_w)/2+x*scaled_w/old_width),
               round((height-scaled_h)/2+y*scaled_h/old_height),
               round(w*scaled_w/old_width), round(h*scaled_h/old_height)]
        if box[2] < 16 or box[3] < 16:
            raise ValueError("Conformed inspection region is too small; revise delivery size")
        region["box"] = box
    frames = round(duration*fps)
    shot.update(width=width, height=height, fps=fps, duration_seconds=duration,
                output_frames=frames, model_frames=frames)
    job["provenance"] = provenance
    job.pop("job_digest", None)
    job["job_digest"] = digest(job)
    return job


def prepare_edits(project: Path, selection: dict, edits: dict, run_id: str):
    """Create new conformed segments from currently passed raw attempts."""
    project = Path(project).resolve()
    directories = selected_attempts(project, selection)
    if set(edits) != set(selection):
        raise ValueError("Edits must name exactly every selected shot")
    delivery = read_json(project / "plan.json")["delivery"]
    width, height, fps = delivery["width"], delivery["height"], delivery.get("fps", 24)
    if any(not isinstance(v, int) or isinstance(v, bool) or v <= 0 for v in (width, height, fps)) or width % 2 or height % 2:
        raise ValueError("Delivery needs positive integer fps and even width/height")
    prepared = []
    for directory in directories:
        source = read_json(directory / "job.json")
        shot_id = source["shot"]["id"]
        edit = edits[shot_id]
        if set(edit) != {"start", "end", "duration_seconds"} or not all(_number(v) for v in edit.values()):
            raise ValueError("Each edit needs finite start, end and duration_seconds")
        info = media.verify_video(directory / "result/video.mp4", source["shot"])
        duration = float(next(s for s in info["streams"] if s["codec_type"] == "video")["duration"])
        if not 0 <= edit["start"] < edit["end"] <= duration or edit["duration_seconds"] <= 0:
            raise ValueError("Edit interval is outside the source duration")
        if round(edit["duration_seconds"]*fps) < 1 or abs(edit["duration_seconds"]*fps-round(edit["duration_seconds"]*fps)) > 1e-6:
            raise ValueError("Target duration must contain an integer delivery frame count")
        if any(role.endswith("video") for role in source["shot"].get("inputs", {})):
            raise ValueError("Temporal control evidence needs its own conforming before edited review")
        provenance = dict(method="ffmpeg_conform", source_attempt=directory.name, model_inference=False,
            source_native_fps=source["shot"]["fps"], delivery_fps=fps, settings_role="source_generation_metadata",
            source_job_digest=source["job_digest"], source_video_sha=sha256(directory / "result/video.mp4"),
            source_review_sha=sha256(directory / "review.json"), start=edit["start"], end=edit["end"],
            target_duration=edit["duration_seconds"])
        prepared.append((directory, _derived(source, edit, delivery, provenance)))
    total = sum(edit["duration_seconds"] for edit in edits.values())
    if "duration_seconds" in delivery and not math.isclose(total, delivery["duration_seconds"], abs_tol=1e-6):
        raise ValueError("Edited durations do not sum to the requested delivery duration")
    root = _run_path(project, run_id)
    root.mkdir(parents=True, exist_ok=False)
    recipe = dict(schema_version=1, selection=selection, edits=edits, delivery=delivery, duration_seconds=total, segments={})
    for source_dir, job in prepared:
        shot, provenance = job["shot"], job["provenance"]
        directory = root / "segments" / shot["id"]
        (directory / "result").mkdir(parents=True)
        shutil.copytree(source_dir / "input", directory / "input")
        for filename in ("job.json", "receipt.json", "review.json"):
            shutil.copy2(source_dir / filename, directory / ("source_" + filename))
        write_json(directory / "job.json", job)
        start, end, target = provenance["start"], provenance["end"], provenance["target_duration"]
        vf = (f"trim=start={start}:end={end},setpts=(PTS-STARTPTS)*{target/(end-start):.12g},fps={fps},"
              f"scale={width}:{height}:force_original_aspect_ratio=decrease:force_divisible_by=2,"
              f"pad={width}:{height}:(ow-iw)/2:(oh-ih)/2,setsar=1,tpad=stop_mode=clone:stop_duration={target}")
        command = ["ffmpeg", "-v", "error", "-nostdin", "-i", str(source_dir / "result/video.mp4"),
                   "-map", "0:v:0", "-vf", vf, "-frames:v", str(shot["output_frames"]), "-t", str(target),
                   "-c:v", "libx264", "-crf", "18", "-pix_fmt", "yuv420p"]
        if shot.get("audio", "none") == "none":
            command += ["-an"]
        else:
            command += ["-map", "0:a:0", "-af", f"atrim=start={start}:end={end},asetpts=PTS-STARTPTS,"
                        f"{_tempo((end-start)/target)},apad,atrim=duration={target},aresample=48000",
                        "-c:a", "aac", "-ac", "2", "-ar", "48000"]
        video = directory / "result/video.mp4"
        media.run(command + ["-movflags", "+faststart", str(video)])
        media.verify_video(video, shot)
        write_json(directory / "receipt.json", dict(state="technically_valid", method="ffmpeg_conform",
                   shot_id=shot["id"], job_digest=job["job_digest"], provenance=provenance, model_inference=False))
        recipe["segments"][shot["id"]] = dict(provenance=provenance, job_digest=job["job_digest"], video_sha=sha256(video),
            lineage_sha={name: sha256(directory / name) for name in ("source_job.json", "source_receipt.json", "source_review.json")})
    recipe["recipe_digest"] = digest(recipe)
    write_json(root / "recipe.json", recipe)
    return root


def _verify(project, run):
    project = Path(project).resolve()
    root = _run_path(project, run)
    recipe = read_json(root / "recipe.json")
    unhashed = {k: v for k, v in recipe.items() if k != "recipe_digest"}
    if digest(unhashed) != recipe["recipe_digest"]:
        raise ValueError("Edit recipe changed")
    if recipe["delivery"] != read_json(project / "plan.json")["delivery"]:
        raise ValueError("Delivery settings changed")
    sources = selected_attempts(project, recipe["selection"])
    directories = []
    for source in sources:
        original = read_json(source / "job.json")
        shot_id = original["shot"]["id"]
        recorded = recipe["segments"][shot_id]
        provenance = recorded["provenance"]
        edit = recipe["edits"][shot_id]
        if (provenance["source_attempt"] != source.name
                or any(provenance[key] != edit[field] for key, field in
                       (("start", "start"), ("end", "end"), ("target_duration", "duration_seconds")))
                or sha256(source / "result/video.mp4") != provenance["source_video_sha"]
                or sha256(source / "review.json") != provenance["source_review_sha"]
                or original["job_digest"] != provenance["source_job_digest"]):
            raise ValueError("Edit source or source review changed")
        expected = _derived(original, recipe["edits"][shot_id], recipe["delivery"], provenance)
        directory = root / "segments" / identifier(shot_id)
        job = read_json(directory / "job.json")
        if job != expected or job["job_digest"] != recorded["job_digest"]:
            raise ValueError("Derived job or edit recipe changed")
        if sha256(directory / "result/video.mp4") != recorded["video_sha"]:
            raise ValueError("Edited video changed")
        for name, expected_sha in recorded["lineage_sha"].items():
            if sha256(directory / name) != expected_sha:
                raise ValueError("Copied source lineage changed")
        for name, asset in job["assets"].items():
            path = directory / "input/assets" / (name + Path(asset["path"]).suffix.lower())
            if sha256(path) != asset["sha256"]:
                raise ValueError("Edited segment's staged source asset changed")
        directories.append(directory)
    return directories


def inspect_edits(project, run):
    """Extract fresh evidence; no inherited quality verdicts."""
    return [media.evidence(directory) for directory in _verify(project, run)]


def validate_edits(project, run):
    """Return ordered directories only after every edited segment passes review."""
    directories = _verify(project, run)
    for directory in directories:
        validate_review(directory, read_json(directory / "review.json"), require_pass=True)
    return directories


def assemble_edits(project, run, join_review=None):
    """Apply edited-segment gates and the existing assembly/join gates."""
    directories = validate_edits(project, run)
    recipe = read_json(_run_path(project, run) / "recipe.json")
    return media.assemble_directories(project, directories, recipe["selection"], join_review)
