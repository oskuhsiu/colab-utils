"""Decode media into time-indexed evidence; assemble only reviewed selections."""
from __future__ import annotations

import math
import re
import subprocess
import tempfile
from fractions import Fraction
from pathlib import Path

from workflow import (local_path, read_json, review_template, selected_attempts,
                      sha256, verify_evidence, write_json)


def run(command):
    result = subprocess.run(command, capture_output=True, text=True)
    if result.returncode:
        raise RuntimeError(f"{command[0]} failed: {result.stderr[-1200:]}")
    return result.stdout


def probe(path):
    import json
    return json.loads(run(["ffprobe", "-v", "error", "-count_frames", "-show_streams",
                          "-show_format", "-of", "json", str(path)]))


def verify_video(path, shot):
    info = probe(path)
    video = next(s for s in info["streams"] if s["codec_type"] == "video")
    audio = [s for s in info["streams"] if s["codec_type"] == "audio"]
    if (video["width"], video["height"]) != (shot["width"], shot["height"]):
        raise ValueError("Decoded dimensions do not match job")
    fps = float(Fraction(video["avg_frame_rate"]))
    if abs(fps - shot["fps"]) > 1e-6 or int(video["nb_read_frames"]) != shot["output_frames"]:
        raise ValueError("Decoded frame count/rate do not match job")
    if abs(float(video["duration"]) - shot["duration_seconds"]) > 1 / shot["fps"]:
        raise ValueError("Video stream duration does not match job")
    if shot.get("audio") in ("native", "separate") and not audio:
        raise ValueError("Required audio stream is missing")
    for stream in audio:
        if abs(float(stream["duration"]) - shot["duration_seconds"]) > max(0.06, 1 / shot["fps"]):
            raise ValueError("Audio stream duration does not match job")
    run(["ffmpeg", "-v", "error", "-xerror", "-i", str(path), "-f", "null", "-"])
    return info


def frame_times(path):
    import json
    value = json.loads(run(["ffprobe", "-v", "error", "-select_streams", "v:0",
                           "-show_frames", "-show_entries", "frame=best_effort_timestamp_time",
                           "-of", "json", str(path)]))
    return [float(f["best_effort_timestamp_time"]) for f in value["frames"]]


def scene_times(path):
    result = subprocess.run(["ffmpeg", "-hide_banner", "-i", str(path), "-vf",
        "select='gt(scene,0.30)',showinfo", "-an", "-f", "null", "-"], capture_output=True, text=True)
    if result.returncode:
        raise RuntimeError("Scene detection failed")
    return [float(x) for x in re.findall(r"pts_time:([0-9.]+)", result.stderr)]


def sample_indices(shot, times, cuts):
    """Uniform overview + dense required events + dense joins + detected cuts."""
    if len(times) != shot["output_frames"] or any(abs(t - n / shot["fps"]) > 0.002 for n, t in enumerate(times)):
        raise ValueError("Irregular frame timestamps; normalize timing before evidence review")
    indices = {0, len(times) - 1}

    def add(start, end, frequency):
        for k in range(math.ceil((end - start) * frequency) + 1):
            t = min(end, start + k / frequency)
            indices.add(min(len(times) - 1, round(t * shot["fps"])))

    add(0, times[-1], 2)
    add(0, min(0.5, times[-1]), 8)
    add(max(0, times[-1] - 0.5), times[-1], 8)
    for window in shot.get("qa", {}).get("event_windows", []):
        add(window["start"], min(window["end"], times[-1]), window.get("fps", 8))
    for cut in cuts:
        add(max(0, cut - 0.25), min(times[-1], cut + 0.25), shot["fps"])
    return sorted(indices)


def evidence(directory):
    directory = Path(directory).resolve()
    job = read_json(directory / "job.json")
    video = directory / "result" / "video.mp4"
    info = verify_video(video, job["shot"])
    root = directory / "evidence"
    root.mkdir(exist_ok=False)
    (root / "frames").mkdir()
    times = frame_times(video)
    cuts = scene_times(video)
    indices = sample_indices(job["shot"], times, cuts)
    expression = "+".join(f"eq(n,{n})" for n in indices)
    run(["ffmpeg", "-v", "error", "-i", str(video), "-vf", f"select='{expression}'",
         "-fps_mode", "vfr", "-q:v", "2", str(root / "frames" / "%06d.jpg")])
    files = sorted((root / "frames").glob("*.jpg"))
    if len(files) != len(indices):
        raise ValueError("Evidence extraction returned the wrong number of frames")
    items = []
    for n, path in zip(indices, files):
        items.append(dict(id=f"f{n:06d}", path=str(path.relative_to(root)), kind="frame",
                          frame_index=n, seconds=times[n], sha256=sha256(path)))
    # Keep original identity baselines visible alongside model inputs.
    (root / "assets").mkdir()
    for name, asset in job["assets"].items():
        source = directory / "input" / "assets" / (name + Path(asset["path"]).suffix.lower())
        if not source.is_file() or sha256(source) != asset["sha256"]:
            raise ValueError(f"Missing/changed staged asset: {name}")
        if source.suffix.lower() not in (".jpg", ".jpeg", ".png", ".webp"):
            continue
        target = root / "assets" / f"{name}.jpg"
        run(["ffmpeg", "-v", "error", "-i", str(source), "-vf",
             "scale=w='min(1600,iw)':h='min(1600,ih)':force_original_aspect_ratio=decrease",
             "-frames:v", "1", "-q:v", "2", str(target)])
        items.append(dict(id="asset_" + name, path=str(target.relative_to(root)), kind="asset",
                          asset_id=name, role=asset["role"], source_sha256=asset["sha256"], sha256=sha256(target)))
    # Supply the actual control timeline beside generated frames, on the same clock.
    for role in ("control_video", "pose_video", "face_video", "mask_video", "background_video"):
        name = job["shot"].get("inputs", {}).get(role)
        if not name:
            continue
        source = directory / "input" / "assets" / (name+Path(job["assets"][name]["path"]).suffix.lower())
        folder = root / role
        folder.mkdir()
        width,height = (512,512) if role == "face_video" else (job["shot"]["width"],job["shot"]["height"])
        scale = "neighbor" if role == "mask_video" else "lanczos"
        filters = (f"fps={job['shot']['fps']},scale={width}:{height}:flags={scale},"
                   f"setsar=1,tpad=stop_mode=clone:stop_duration={job['shot']['model_frames']/job['shot']['fps']},"
                   f"select='{expression}'")
        run(["ffmpeg","-v","error","-i",str(source),"-vf",filters,"-fps_mode","vfr",
             "-frames:v",str(len(indices)),"-q:v","2",str(folder / "%06d.jpg")])
        controls = sorted(folder.glob("*.jpg"))
        if len(controls) != len(indices):
            raise ValueError("Control evidence returned the wrong frame count")
        for n,path in zip(indices,controls):
            items.append(dict(id=f"{role}_f{n:06d}",path=str(path.relative_to(root)),kind="control",
                              input_role=role,frame_index=n,seconds=times[n],sha256=sha256(path),
                              source_sha256=job["assets"][name]["sha256"]))
    write_json(root / "media.json",info)
    items.append(dict(id="technical",kind="technical",path="media.json",sha256=sha256(root / "media.json")))
    for roi in job["shot"].get("qa", {}).get("regions", []):
        name = roi["id"]
        from workflow import identifier
        identifier(name)
        x, y, w, h = roi["box"]
        if any(not isinstance(v, int) for v in (x, y, w, h)) or x < 0 or y < 0 or w < 16 or h < 16 or x+w > job["shot"]["width"] or y+h > job["shot"]["height"]:
            raise ValueError("ROI must be a valid source-pixel crop")
        for frame in list(items):
            if frame["kind"] != "frame":
                continue
            target = root / "frames" / (frame["id"] + "_" + name + ".jpg")
            run(["ffmpeg", "-v", "error", "-i", str(root / frame["path"]), "-vf",
                 f"crop={w}:{h}:{x}:{y}", "-frames:v", "1", "-q:v", "2", str(target)])
            items.append(dict(id=frame["id"] + "_" + name, path=str(target.relative_to(root)), kind="crop",
                              frame_index=frame["frame_index"], seconds=frame["seconds"], region=name,
                              box=[x,y,w,h], sha256=sha256(target)))
    if any(s["codec_type"] == "audio" for s in info["streams"]):
        target = root / "audio.wav"
        run(["ffmpeg", "-v", "error", "-i", str(video), "-vn", "-ar", "16000", "-ac", "1", str(target)])
        items.append(dict(id="audio", kind="audio", path="audio.wav", start=0,
                          end=job["shot"]["duration_seconds"], sha256=sha256(target)))
    manifest = dict(schema_version=1, job_digest=job["job_digest"], video_sha256=sha256(video),
        shot_id=job["shot"]["id"], native_fps=job["shot"]["fps"],
        decoded_frames=len(times), sampled_frames=len(indices), scene_changes=cuts,
        event_windows=job["shot"].get("qa", {}).get("event_windows", []), items=items,
        coverage="Sampled visual evidence; audio file is extracted, not automatically listened to or transcribed.")
    write_json(root / "manifest.json", manifest)
    write_json(root / "review-template.json", review_template(directory))
    receipt = read_json(directory / "receipt.json")
    receipt["state"] = "needs_review"
    write_json(directory / "receipt.json", receipt)
    return manifest


def joins(project, selection):
    project = Path(project).resolve()
    directories = selected_attempts(project, selection)
    return join_directories(project, directories, selection)


def join_directories(project, directories, selection):
    """Build joins for reviewed generated or explicitly conformed segments."""
    project = Path(project).resolve()
    directories = [Path(p).resolve() for p in directories]
    if any(not p.is_relative_to(project) for p in directories):
        raise ValueError("Join sources must be contained within the edit/project root")
    root = project / "joins"
    root.mkdir(exist_ok=True)
    pairs = []
    for left, right in zip(directories, directories[1:]):
        lm, rm = verify_evidence(left), verify_evidence(right)
        lj, rj = read_json(left / "job.json"), read_json(right / "job.json")
        left_id, right_id = lj["shot"]["id"], rj["shot"]["id"]
        pair_id = left_id + "__" + right_id
        items = []
        for prefix, directory, manifest, use in (("L",left,lm,"end"),("R",right,rm,"start")):
            duration = read_json(directory / "job.json")["shot"]["duration_seconds"]
            for item in manifest["items"]:
                near_join = item["kind"] in ("frame","crop") and (
                    (item["seconds"] >= duration - 0.6) if use == "end" else (item["seconds"] <= 0.6))
                if item["kind"] in ("asset", "audio") or near_join:
                    value = dict(item, id=prefix+"_"+item["id"], path=str((directory / "evidence" / item["path"]).relative_to(project)))
                    items.append(value)
        kinds = ["scene", "action", "audio"]
        if set(lj["shot"].get("characters", [])) & set(rj["shot"].get("characters", [])):
            kinds += ["identity", "wardrobe"]
        pairs.append(dict(id=pair_id, left_attempt=left.name, right_attempt=right.name,
            left_video=str((left / "result" / "video.mp4").relative_to(project)),
            right_video=str((right / "result" / "video.mp4").relative_to(project)),
            left_sha256=lm["video_sha256"], right_sha256=rm["video_sha256"],
            planned_left_end=lj["shot"]["end_state"], planned_right_start=rj["shot"]["start_state"],
            transition=rj["shot"].get("transition", "cut"), items=items,
            criteria=[dict(id=kind, verdict="unknown", evidence=[], reason="") for kind in kinds]))
    manifest = dict(schema_version=1, selection=selection, pairs=pairs)
    write_json(root / "manifest.json", manifest)
    write_json(root / "review-template.json", dict(manifest_sha256=sha256(root / "manifest.json"),
        reviewer={"name":"", "kind":"agent"}, pairs=[dict(id=p["id"], criteria=p["criteria"]) for p in pairs]))
    return manifest


def validate_joins(project, selection, review):
    project = Path(project)
    root = project / "joins"
    manifest = read_json(root / "manifest.json")
    if manifest["selection"] != selection or review.get("manifest_sha256") != sha256(root / "manifest.json"):
        raise ValueError("Join review belongs to an earlier selection/manifest")
    if not review.get("reviewer", {}).get("name"):
        raise ValueError("Join review needs an actual reviewer")
    if [p["id"] for p in review.get("pairs", [])] != [p["id"] for p in manifest["pairs"]]:
        raise ValueError("Review every adjacent pair in order")
    for pair, verdict in zip(manifest["pairs"], review["pairs"]):
        left_path = local_path(project,pair.get("left_video",f"attempts/{pair['left_attempt']}/result/video.mp4"))
        right_path = local_path(project,pair.get("right_video",f"attempts/{pair['right_attempt']}/result/video.mp4"))
        if sha256(left_path) != pair["left_sha256"] or sha256(right_path) != pair["right_sha256"]:
            raise ValueError("Join source video changed")
        valid = {item["id"] for item in pair["items"]}
        for item in pair["items"]:
            if sha256(local_path(project, item["path"])) != item["sha256"]:
                raise ValueError("Join evidence changed")
        if [c["id"] for c in verdict["criteria"]] != [c["id"] for c in pair["criteria"]]:
            raise ValueError("Review every join criterion")
        for criterion in verdict["criteria"]:
            if criterion.get("verdict") != "pass" or not criterion.get("reason") or not criterion.get("evidence") or not set(criterion["evidence"]).issubset(valid):
                raise ValueError("Unpassed/unresolved join criterion blocks final assembly")


def assemble(project, selection, join_review=None):
    project = Path(project).resolve()
    directories = selected_attempts(project, selection)
    return assemble_directories(project,directories,selection,join_review)


def assemble_directories(project,directories,selection,join_review=None):
    """Export explicit reviewed directories; raw provenance is checked by caller."""
    project = Path(project).resolve()
    directories = [Path(p).resolve() for p in directories]
    if not directories or any(not p.is_relative_to(project) for p in directories):
        raise ValueError("Assembly sources must be contained within the edit/project root")
    from workflow import validate_review
    for directory in directories:
        validate_review(directory,read_json(directory / "review.json"),require_pass=True)
    if len(directories) > 1:
        if not join_review:
            raise ValueError("Multiple shots require an evidence-bound join review")
        join_manifest = read_json(project / "joins" / "manifest.json")
        expected_pairs = list(zip(directories,directories[1:]))
        if len(join_manifest["pairs"]) != len(expected_pairs):
            raise ValueError("Join manifest does not cover this exact assembly")
        for pair,(left,right) in zip(join_manifest["pairs"],expected_pairs):
            left_path = local_path(project,pair.get("left_video",f"attempts/{pair['left_attempt']}/result/video.mp4"))
            right_path = local_path(project,pair.get("right_video",f"attempts/{pair['right_attempt']}/result/video.mp4"))
            if left_path != left / "result" / "video.mp4" or right_path != right / "result" / "video.mp4":
                raise ValueError("Join review refers to different edited/selected directories")
        validate_joins(project, selection, read_json(join_review))
    plan = read_json(project / "plan.json")
    settings = plan["delivery"]
    width, height, fps = settings["width"], settings["height"], settings.get("fps", 24)
    total = sum(read_json(p / "job.json")["shot"]["duration_seconds"] for p in directories)
    if settings.get("duration_seconds") is not None and abs(total-settings["duration_seconds"])>1/fps:
        raise ValueError("Edited durations do not match required final duration")
    root = project / "deliverables"
    root.mkdir(exist_ok=True)
    target = root / "final.mp4"
    if target.exists():
        raise ValueError("Final already exists; choose a new project revision to preserve it")
    with tempfile.TemporaryDirectory(prefix="assemble-", dir=root) as temporary:
        chunks = []
        for index, directory in enumerate(directories):
            job = read_json(directory / "job.json")
            duration = job["shot"]["duration_seconds"]
            source = directory / "result" / "video.mp4"
            info = probe(source)
            have_audio = job["shot"].get("audio", "none") != "none" and any(s["codec_type"] == "audio" for s in info["streams"])
            output = Path(temporary) / f"clip{index:04d}.mp4"
            command = ["ffmpeg", "-v", "error", "-i", str(source)]
            if not have_audio:
                command += ["-f", "lavfi", "-i", "anullsrc=r=48000:cl=stereo"]
            command += ["-map", "0:v:0", "-map", "0:a:0" if have_audio else "1:a:0",
                "-vf", f"fps={fps},scale={width}:{height}:force_original_aspect_ratio=decrease,pad={width}:{height}:(ow-iw)/2:(oh-ih)/2,setsar=1",
                "-af", f"atrim=duration={duration},asetpts=PTS-STARTPTS,aresample=48000",
                "-t", str(duration), "-c:v", "libx264", "-crf", "18", "-pix_fmt", "yuv420p",
                "-c:a", "pcm_s16le", "-ac", "2", "-f", "matroska", str(output)]
            run(command)
            chunks.append(output)
        listing = Path(temporary) / "concat.txt"
        listing.write_text("".join(f"file '{p.name}'\n" for p in chunks))
        staged = Path(temporary) / "final.mp4"
        run(["ffmpeg", "-v", "error", "-f", "concat", "-safe", "1", "-i", str(listing),
             "-t", str(total), "-c:v", "libx264", "-crf", "18", "-pix_fmt", "yuv420p",
             "-c:a", "aac", "-ac", "2", "-ar", "48000", "-movflags", "+faststart", str(staged)])
        output_shot = dict(width=width,height=height,fps=fps,duration_seconds=total,
                           output_frames=round(total*fps),audio="separate")
        technical = verify_video(staged, output_shot)
        staged.replace(target)
    report = dict(status="assembled_from_reviewed_shots", file="final.mp4", sha256=sha256(target),
        duration_seconds=total, selection=selection, media=technical,
        reviews={p.name:sha256(p / "review.json") for p in directories},
        join_review_sha256=sha256(join_review) if join_review else None,
        final_content_review="pending; inspect export/join playback before claiming delivery acceptance")
    write_json(root / "delivery.json", report)
    return report
