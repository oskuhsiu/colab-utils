"""Measured PCM WAV identity and supplied speech timing; no ASR, TTS or models.

The importer measures the complete file, not speech: utterance boundaries and
sentence/word alignment come from the caller. Hashes cannot verify transcript,
speaker identity, naturalness or lip sync; those still require listening/review.
"""
from __future__ import annotations

import copy
import json
import math
import struct
import wave

from workflow import digest, identifier, local_path, sha256


BOUNDARIES = "Manual supplied utterance boundaries within measured PCM WAV; not detected speech or generated alignment."
LIMITATIONS = ("PCM frame count measures file duration only. Transcript, speaker/voice identity and supplied "
               "boundaries/alignment are not verified by this importer. Listen to the actual audio; "
               "review timing, intelligibility and any intended lip sync. Missing alignment is not synthesized.")
UTTERANCE_FIELDS = {"id", "character_id", "voice_id", "text", "start_seconds", "end_seconds"}
ALIGNMENT_FIELDS = {"utterance_id", "text", "start_seconds", "end_seconds"}


def _number(value, name, *, positive=False):
    if type(value) not in (int, float) or not math.isfinite(value) or value < 0 or (positive and value == 0):
        raise ValueError(f"{name} must be finite and {'positive' if positive else 'nonnegative'}")
    return float(value)


def _text(value, name):
    if not isinstance(value, str) or not value.strip() or "\x00" in value:
        raise ValueError(f"{name} must be nonempty text without NUL characters")
    return value


def _rows(value, name):
    if not isinstance(value, list) or any(not isinstance(row, dict) for row in value):
        raise ValueError(f"{name} must be a list of objects")
    return value


def _interval(row, duration, name):
    start = _number(row.get("start_seconds"), name + ".start_seconds")
    end = _number(row.get("end_seconds"), name + ".end_seconds", positive=True)
    if not start < end <= duration:
        raise ValueError(f"{name} interval is outside its measured audio/timeline duration")
    return start, end


def _asset(project, plan, asset_id):
    identifier(asset_id)
    assets = plan.get("assets", {})
    value = assets.get(asset_id) if isinstance(assets, dict) else None
    if not isinstance(value, dict) or value.get("role") != "audio" or value.get("status") != "ready":
        raise ValueError(f"Audio asset {asset_id} must exist with role=audio and status=ready")
    path = local_path(project, value.get("path"))
    if not path.is_file():
        raise ValueError(f"Audio asset {asset_id} is missing")
    return value, path


def _measure_wav(path):
    """Check RIFF extents and read every PCM frame, including the last one."""
    before = sha256(path)
    try:
        with path.open("rb") as stream:
            size = path.stat().st_size
            header = stream.read(12)
            if len(header) != 12:
                raise ValueError("Truncated PCM WAV header")
            riff, extent, kind = struct.unpack("<4sI4s", header)
            if riff != b"RIFF" or kind != b"WAVE" or extent + 8 != size:
                raise ValueError("PCM WAV needs complete RIFF/WAVE bytes, without truncation or trailing data")
            data_sizes, formats = [], []
            while stream.tell() < size:
                chunk = stream.read(8)
                if len(chunk) != 8:
                    raise ValueError("Truncated WAV chunk header")
                name, length = struct.unpack("<4sI", chunk)
                # A final odd data chunk from stdlib wave can omit its RIFF pad.
                end = stream.tell() + length
                if end > size or (end < size and end + (length % 2) > size):
                    raise ValueError("Truncated WAV chunk")
                if name == b"data":
                    data_sizes.append(length)
                if name == b"fmt ":
                    if length < 16:
                        raise ValueError("Truncated WAV format chunk")
                    formats.append(struct.unpack("<HHIIHH", stream.read(16)))
                stream.seek(min(size, end + length % 2))
            if len(data_sizes) != 1 or len(formats) != 1:
                raise ValueError("PCM WAV needs exactly one format and one data chunk")
            stream.seek(0)
            with wave.open(stream, "rb") as audio:
                channels, width, rate, frames, compression, _ = audio.getparams()
                if compression != "NONE" or width not in (1, 2, 3, 4) or channels < 1 or rate < 1 or frames < 1:
                    raise ValueError("A nonempty uncompressed PCM WAV is required")
                frame_bytes = channels * width
                if formats[0] != (1, channels, rate, rate * frame_bytes, frame_bytes, width * 8):
                    raise ValueError("PCM WAV format fields disagree about complete frames/sample rate")
                read_bytes = 0
                while block := audio.readframes(65536):
                    if len(block) % frame_bytes:
                        raise ValueError("WAV contains a partial PCM frame")
                    read_bytes += len(block)
                if read_bytes != frames * frame_bytes or read_bytes != data_sizes[0]:
                    raise ValueError("WAV frame count does not match the complete PCM data")
    except (wave.Error, EOFError, struct.error) as exc:
        raise ValueError(f"Invalid or unsupported PCM WAV: {exc}") from exc
    if sha256(path) != before:
        raise ValueError("Audio changed while it was being measured")
    return dict(sha256=before, channels=channels, sample_width_bytes=width,
                sample_rate_hz=rate, frame_count=frames, duration_seconds=frames / rate)


def _utterances(value, duration, *, allow_empty=False):
    rows = _rows(value, "utterances")
    if not rows and not allow_empty:
        raise ValueError("At least one utterance with supplied boundaries is required")
    result, ids = [], set()
    for row in rows:
        if set(row) != UTTERANCE_FIELDS:
            raise ValueError("Each utterance needs exactly id, character_id, voice_id, text, start_seconds and end_seconds")
        item = {key: identifier(row[key]) for key in ("id", "character_id", "voice_id")}
        if item["id"] in ids:
            raise ValueError("Utterance IDs must be unique")
        ids.add(item["id"])
        start, end = _interval(row, duration, item["id"])
        item.update(text=_text(row["text"], "utterance.text"), start_seconds=start, end_seconds=end)
        result.append(item)
    return result


def _alignment(value, utterances, duration):
    if value is None:
        return dict(status="unavailable", method="unavailable", provenance="No sentence or word timing supplied.",
                    sentences=[], words=[])
    if not isinstance(value, dict) or set(value) - {"method", "provenance", "sentences", "words"}:
        raise ValueError("alignment needs method, provenance and optional sentence/word timing lists")
    method, provenance = (_text(value.get(key), "alignment." + key) for key in ("method", "provenance"))
    if method == "unavailable":
        raise ValueError("Omit alignment when no sentence/word timing is available")
    by_id = {row["id"]: row for row in utterances}
    result = dict(status="supplied", method=method, provenance=provenance)
    for level in ("sentences", "words"):
        result[level], last_end, texts = [], {}, {}
        for row in _rows(value.get(level, []), "alignment." + level):
            if set(row) != ALIGNMENT_FIELDS:
                raise ValueError("Alignment entries need a known utterance_id, text, start_seconds and end_seconds")
            utterance_id = identifier(row["utterance_id"])
            if utterance_id not in by_id:
                raise ValueError("Alignment entries need a known utterance_id")
            parent = by_id[utterance_id]
            start, end = _interval(row, duration, "alignment." + level)
            if start < parent["start_seconds"] or end > parent["end_seconds"]:
                raise ValueError("Alignment interval is outside its utterance")
            if start < last_end.get(parent["id"], parent["start_seconds"]):
                raise ValueError("Alignment intervals must be ordered and nonoverlapping within each utterance")
            last_end[parent["id"]] = end
            text = _text(row["text"], "alignment.text")
            texts.setdefault(parent["id"], []).append(text)
            result[level].append(dict(utterance_id=parent["id"], text=text, start_seconds=start, end_seconds=end))
        for utterance_id, parts in texts.items():
            # Only whitespace/tokenization may differ; stale or partial text is rejected.
            if "".join("".join(parts).split()) != "".join(by_id[utterance_id]["text"].split()):
                raise ValueError(f"{level} text must cover the complete matching utterance text")
    if not result["sentences"] and not result["words"]:
        raise ValueError("Supplied alignment must contain sentence or word timing; otherwise omit alignment")
    return result


def create_artifact(project, plan, spec):
    """Return a manifest for an existing ready audio asset; never write files."""
    from reference_resolver import voice_binding

    if not isinstance(spec, dict) or set(spec) - {"asset_id", "utterances", "alignment"}:
        raise ValueError("Audio import needs asset_id, utterances and optional alignment")
    asset_id = identifier(spec.get("asset_id"))
    asset, path = _asset(project, plan, asset_id)
    audio = dict(path=asset["path"], **_measure_wav(path))
    utterances = _utterances(spec.get("utterances"), audio["duration_seconds"])
    bindings = {}
    for row in utterances:
        binding = voice_binding(plan, row["character_id"])
        if binding["character_id"] != row["character_id"] or binding["voice_id"] != row["voice_id"]:
            raise ValueError("Utterance character_id/voice_id must match the actual canonical character voice binding")
        bindings[row["character_id"]] = {key: binding[key] for key in ("character_id", "voice_id")}
    manifest = dict(schema_version=1, asset_id=asset_id, audio=audio, utterances=utterances,
                    voice_bindings=sorted(bindings.values(), key=lambda row: row["character_id"]),
                    utterance_timing_provenance=BOUNDARIES)
    manifest["artifact_digest"] = digest(manifest)
    manifest["alignment"] = _alignment(spec.get("alignment"), utterances, audio["duration_seconds"])
    manifest["alignment_digest"] = digest(manifest["alignment"])
    manifest["limitations"] = LIMITATIONS
    return manifest


def load_artifact(project, plan, asset_id):
    """Recheck the manifest, current complete WAV bytes and speaker dependencies."""
    asset, _ = _asset(project, plan, asset_id)
    path = local_path(project, asset.get("audio_artifact"))
    try:
        manifest = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise ValueError(f"Cannot read audio artifact for {asset_id}: {exc}") from exc
    if not isinstance(manifest, dict) or manifest.get("schema_version") != 1 or manifest.get("asset_id") != asset_id:
        raise ValueError("Audio artifact schema or asset identity changed")
    alignment = manifest.get("alignment")
    if not isinstance(alignment, dict):
        raise ValueError("Audio artifact needs explicit alignment availability")
    spec = dict(asset_id=asset_id, utterances=manifest.get("utterances"))
    if alignment.get("status") != "unavailable":
        spec["alignment"] = {key: value for key, value in alignment.items() if key != "status"}
    expected = create_artifact(project, plan, spec)
    if digest(manifest) != digest(expected):
        raise ValueError("Audio artifact changed or its current WAV/voice dependencies no longer match; import a new revision")
    return expected


def bind_timing(project, plan, asset_id, timing_spec):
    """Hydrate the old timing planner without guessing identities or durations.

    Every manifest utterance must be represented exactly once. The returned
    timeline retains IDs, source digests and supplied alignment; planner-only
    input drops the new identity fields. Caller owns model duration constraints.
    """
    manifest = load_artifact(project, plan, asset_id)
    if not isinstance(timing_spec, dict):
        raise ValueError("dialogue_timing must be an object")
    hydrated = copy.deepcopy(timing_spec)
    lines = _rows(hydrated.get("utterances"), "dialogue_timing.utterances")
    by_id = {row["id"]: row for row in manifest["utterances"]}
    seen = set()
    for line in lines:
        if set(line) & {"voice_mode", "delivery", "rate_multiplier"}:
            raise ValueError("Separate recorded audio does not apply voice_mode, delivery or rate_multiplier: "
                             "put visible mouth/expression/staging intent in shot.prompt and record performance changes in a new audio revision")
        line_id = identifier(line.get("id"))
        if line_id not in by_id or line_id in seen:
            raise ValueError("Dialogue utterance IDs must match the artifact exactly once")
        seen.add(line_id)
        row = by_id[line_id]
        if any(line.get(key) != row[field] for key, field in
               (("speaker", "character_id"), ("voice_id", "voice_id"), ("text", "text"))):
            raise ValueError("Dialogue text, speaker or voice differs from the audio artifact")
        if "planned_utterance_seconds" in line or "not_before_seconds" in line:
            raise ValueError("Artifact timing cannot be combined with planned duration or not_before_seconds")
        duration = row["end_seconds"] - row["start_seconds"]
        for key, value in (("start_seconds", row["start_seconds"]), ("measured_utterance_seconds", duration)):
            if key in line and not math.isclose(_number(line[key], key), value, rel_tol=0, abs_tol=1e-9):
                raise ValueError(f"Dialogue {key} conflicts with supplied artifact boundaries")
            line[key] = value
        for key in ("id", "voice_id", "voice_description"):
            line.pop(key, None)
        line["timing_note"] = BOUNDARIES
    if seen != set(by_id):
        raise ValueError("Dialogue must include every utterance in the full audio track")
    hydrated["timing_mode"] = "explicit"
    policy = hydrated.get("policy", {})
    if not isinstance(policy, dict):
        raise ValueError("Speech policy must be an object")
    hydrated["policy"] = {"lead_seconds": 0, "tail_seconds": 0, "turn_gap_seconds": 0, **policy}
    timeline = copy.deepcopy(manifest)
    duration = manifest["audio"]["duration_seconds"]
    hydrated["action_end_seconds"] = max(_number(hydrated.get("action_end_seconds", 0), "action_end_seconds"), duration)
    if "clip_seconds" in hydrated:
        clip = _number(hydrated["clip_seconds"], "clip_seconds", positive=True)
        if clip < duration:
            raise ValueError("Clip would truncate the complete measured audio track")
        duration = clip
    timeline.update(duration_seconds=duration, transforms=[])
    return hydrated, timeline


def _timeline_rows(timeline):
    if not isinstance(timeline, dict):
        raise ValueError("Audio timeline must be an object")
    audio = timeline.get("audio", {})
    if not isinstance(audio, dict):
        raise ValueError("Timeline source audio metadata must be an object")
    duration = _number(timeline.get("duration_seconds", audio.get("duration_seconds")), "timeline duration", positive=True)
    utterances = _utterances(timeline.get("utterances"), duration, allow_empty=True)
    value = timeline.get("alignment")
    if not isinstance(value, dict) or value.get("status") not in ("supplied", "unavailable"):
        raise ValueError("Timeline needs explicit alignment availability")
    if value["status"] == "unavailable":
        if value.get("sentences") or value.get("words"):
            raise ValueError("Unavailable alignment cannot contain timed entries")
        alignment = copy.deepcopy(value)
    elif not value.get("sentences") and not value.get("words") and not utterances:
        alignment = copy.deepcopy(value)  # A trim can retain only silence.
    else:
        alignment = _alignment({key: item for key, item in value.items() if key != "status"}, utterances, duration)
    return duration, utterances, alignment


def map_timeline(timeline, start, end, target_duration):
    """Map trim/speed clocks; fail rather than retain full text for cut speech.

    Source audio metadata and digests stay unchanged. The transforms record the
    ordered clock changes; this does not create new measured/aligned audio.
    """
    duration, utterances, alignment = _timeline_rows(timeline)
    start, end = _number(start, "trim start"), _number(end, "trim end", positive=True)
    target = _number(target_duration, "target_duration", positive=True)
    if not start < end <= duration:
        raise ValueError("Trim interval is outside the source timeline")
    kept = []
    for row in utterances:
        if row["end_seconds"] <= start or row["start_seconds"] >= end:
            continue
        if row["start_seconds"] < start or row["end_seconds"] > end:
            raise ValueError(f"Edit cuts through utterance {row['id']}; preserve complete speech before exporting subtitles")
        kept.append(row)
    ids = {row["id"] for row in kept}
    ratio = target / (end - start)
    if not math.isfinite(ratio):
        raise ValueError("Timeline speed ratio must be finite")
    def mapped(row):
        return dict(row, start_seconds=max(0.0, min(target, (row["start_seconds"]-start)*ratio)),
                    end_seconds=max(0.0, min(target, (row["end_seconds"]-start)*ratio)))
    result = copy.deepcopy(timeline)
    result["utterances"] = [mapped(row) for row in kept]
    result["alignment"] = dict(alignment, **{level: [mapped(row) for row in alignment[level] if row["utterance_id"] in ids]
                                           for level in ("sentences", "words")})
    result["duration_seconds"] = target
    result.setdefault("transforms", []).append(dict(start_seconds=start, end_seconds=end, target_duration_seconds=target))
    return result


def srt_from_timeline(timeline):
    """Export supplied sentence intervals only (also accepts a loaded manifest).

    Word timestamps alone are not sentence boundaries. Overlapping speakers
    retain overlapping cues, which not every subtitle player displays equally.
    """
    _, utterances, alignment = _timeline_rows(timeline)
    sentences = alignment["sentences"]
    if not sentences or {row["utterance_id"] for row in sentences} != {row["id"] for row in utterances}:
        raise ValueError("SRT requires supplied sentence timing for every included utterance; no alignment is synthesized")
    def stamp(milliseconds):
        seconds, milliseconds = divmod(milliseconds, 1000)
        minutes, seconds = divmod(seconds, 60)
        hours, minutes = divmod(minutes, 60)
        return f"{hours:02d}:{minutes:02d}:{seconds:02d},{milliseconds:03d}"
    cues = []
    for index, row in enumerate(sorted(sentences, key=lambda row: (row["start_seconds"], row["end_seconds"], row["utterance_id"])), 1):
        start, end = (math.floor(row[key]*1000 + .5) for key in ("start_seconds", "end_seconds"))
        if end <= start:
            raise ValueError("Sentence interval is too short for SRT millisecond precision")
        cues.append(f"{index}\n{stamp(start)} --> {stamp(end)}\n{' '.join(row['text'].split())}\n")
    return "\n".join(cues)
