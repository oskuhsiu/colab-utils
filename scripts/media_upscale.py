#!/usr/bin/env python3
"""Standalone tiled AI enlargement. Heavy dependencies are imported only for inference."""
from __future__ import annotations

import argparse
from fractions import Fraction
import hashlib
import json
import math
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import time
import urllib.request

ROOT = Path(__file__).resolve().parents[1]
CATALOG = Path(__file__).with_name("media_upscale_models.json")
DEFAULT_MODEL_DIR = ROOT / "artifacts/media-upscale/models"


def sha256(path):
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def load_catalog(path=CATALOG):
    data = json.loads(Path(path).read_text())
    if data.get("schema_version") != 1 or not isinstance(data.get("models"), dict):
        raise ValueError("Unsupported model catalog schema")
    for name, entry in data["models"].items():
        required = {"file", "url", "sha256", "size", "scale", "license", "source"}
        if not required.issubset(entry):
            raise ValueError(f"Incomplete catalog entry: {name}")
        if Path(entry["file"]).name != entry["file"] or entry["file"] in ("", ".", ".."):
            raise ValueError(f"Unsafe model filename: {name}")
        if entry["scale"] not in (2, 4) or not isinstance(entry["size"], int) or entry["size"] <= 0:
            raise ValueError(f"Invalid model size/scale: {name}")
        if len(entry["sha256"]) != 64 or any(c not in "0123456789abcdef" for c in entry["sha256"]):
            raise ValueError(f"Invalid model digest: {name}")
        if not entry["url"].startswith("https://"):
            raise ValueError(f"Model download requires HTTPS: {name}")
    return data["models"]


def verify_model(path, entry):
    if Path(path).stat().st_size != entry["size"] or sha256(path) != entry["sha256"]:
        raise ValueError(f"Model size/hash mismatch: {path}; remove the invalid cache and download again")


def download_model(entry, model_dir):
    directory = Path(model_dir)
    directory.mkdir(parents=True, exist_ok=True)
    destination = directory / entry["file"]
    if destination.exists():
        verify_model(destination, entry)
        return destination
    fd, temporary = tempfile.mkstemp(prefix=".model-", suffix=".part", dir=directory)
    try:
        with os.fdopen(fd, "wb") as output, urllib.request.urlopen(entry["url"], timeout=60) as response:
            total = 0
            while True:
                chunk = response.read(1024 * 1024)
                if not chunk:
                    break
                total += len(chunk)
                if total > entry["size"]:
                    raise ValueError("Downloaded model exceeds catalog size")
                output.write(chunk)
        verify_model(temporary, entry)
        # Publish without overwriting a cache another process may have created.
        try:
            os.link(temporary, destination)
        except FileExistsError:
            verify_model(destination, entry)
        return destination
    finally:
        Path(temporary).unlink(missing_ok=True)


def load_descriptor(path):
    import torch
    from spandrel import ImageModelDescriptor, ModelLoader
    state = torch.load(path, map_location="cpu", weights_only=True)
    for key in ("params_ema", "params", "state_dict"):
        if isinstance(state, dict) and isinstance(state.get(key), dict):
            state = state[key]
            break
    descriptor = ModelLoader(device="cpu").load_from_state_dict(state)
    if not isinstance(descriptor, ImageModelDescriptor):
        raise ValueError("Weights are not a spandrel image model")
    return descriptor


class TileEngine:
    """Keep only one padded tile on the inference device; output stays in CPU RAM."""
    def __init__(self, descriptor, native_scale, scale=2, tile=192, tile_pad=16,
                 device="auto", precision="auto"):
        import torch
        if scale not in (2, 4) or scale > native_scale:
            raise ValueError("Requested scale must be 2/4 and cannot exceed the model's native AI scale")
        if tile <= 0 or tile_pad < 0:
            raise ValueError("tile must be positive and tile-pad nonnegative")
        if descriptor.scale != native_scale or descriptor.input_channels != 3 or descriptor.output_channels != 3:
            raise ValueError("Model descriptor scale/channels do not match catalog RGB contract")
        if device == "auto":
            device = "cuda" if torch.cuda.is_available() else "cpu"
        if device not in ("cpu", "cuda") or device == "cuda" and not torch.cuda.is_available():
            raise ValueError("Requested CUDA device is unavailable")
        if precision == "auto":
            precision = "fp16" if device == "cuda" and descriptor.supports_half else "fp32"
        if precision not in ("fp32", "fp16"):
            raise ValueError("Unsupported precision")
        if precision == "fp16" and (device != "cuda" or not descriptor.supports_half):
            raise ValueError("FP16 requires CUDA and a model supporting half precision; use fp32")
        self.descriptor = descriptor.to(device).eval()
        if precision == "fp16":
            self.descriptor.half()
        else:
            self.descriptor.float()
        self.device, self.precision = device, precision
        self.native_scale, self.scale = native_scale, scale
        self.tile, self.tile_pad = tile, tile_pad
        self.frames = self.tiles = 0
        self.inference_seconds = 0.0

    def upscale(self, rgb):
        import numpy as np
        import torch
        from PIL import Image
        if rgb.dtype != np.uint8 or rgb.ndim != 3 or rgb.shape[2] != 3:
            raise ValueError("Tile engine requires RGB uint8 pixels")
        height, width, _ = rgb.shape
        native = self.native_scale
        output = np.empty((height * native, width * native, 3), dtype=np.uint8)
        started = time.perf_counter()
        with torch.inference_mode():
            for top in range(0, height, self.tile):
                bottom = min(top + self.tile, height)
                for left in range(0, width, self.tile):
                    right = min(left + self.tile, width)
                    x0, x1 = max(0, left - self.tile_pad), min(width, right + self.tile_pad)
                    y0, y1 = max(0, top - self.tile_pad), min(height, bottom + self.tile_pad)
                    pixels = np.ascontiguousarray(rgb[y0:y1, x0:x1].transpose(2, 0, 1))
                    tensor = torch.from_numpy(pixels).unsqueeze(0).to(
                        device=self.device, dtype=torch.float16 if self.precision == "fp16" else torch.float32)
                    tensor.div_(255)
                    result = self.descriptor(tensor)
                    expected = (1, 3, (y1 - y0) * native, (x1 - x0) * native)
                    if tuple(result.shape) != expected or not torch.isfinite(result).all().item():
                        raise ValueError("Model returned invalid tile dimensions or nonfinite pixels")
                    crop = result[0, :, (top-y0)*native:(bottom-y0)*native,
                                  (left-x0)*native:(right-x0)*native]
                    crop = crop.clamp(0, 1).mul(255).round().to(torch.uint8).cpu().numpy().transpose(1, 2, 0)
                    output[top*native:bottom*native, left*native:right*native] = crop
                    self.tiles += 1
                    del tensor, result, crop
        self.inference_seconds += time.perf_counter() - started
        self.frames += 1
        if self.scale != native:
            output = np.asarray(Image.fromarray(output).resize(
                (width*self.scale, height*self.scale), Image.Resampling.LANCZOS))
        return output


def check_paths(source, output):
    source, output = Path(source).resolve(), Path(output).resolve()
    if not source.is_file():
        raise FileNotFoundError(source)
    if source == output:
        raise ValueError("Input and output must be different paths")
    receipt = Path(str(output) + ".upscale.json")
    if output.exists() or receipt.exists():
        raise FileExistsError(f"Refusing to overwrite output or receipt: {output}")
    output.parent.mkdir(parents=True, exist_ok=True)
    return source, output


def temporary_output(output):
    fd, name = tempfile.mkstemp(prefix=".upscale-", suffix=output.suffix, dir=output.parent)
    os.close(fd)
    return Path(name)


def publish(temporary, output, receipt):
    sidecar = Path(str(output) + ".upscale.json")
    fd, name = tempfile.mkstemp(prefix=".receipt-", suffix=".json", dir=output.parent)
    try:
        with os.fdopen(fd, "w") as handle:
            json.dump(receipt, handle, indent=2)
            handle.write("\n")
        os.link(name, sidecar)
        try:
            os.link(temporary, output)
        except BaseException:
            sidecar.unlink()
            raise
    finally:
        Path(name).unlink(missing_ok=True)


def base_receipt(source, temporary, output, engine, model_id, entry, input_sha, started):
    if sha256(source) != input_sha:
        raise ValueError("Source changed while processing; result was not published")
    return dict(schema_version=1, status="complete", input=dict(path=str(source), sha256=input_sha),
                output=dict(path=str(output), sha256=sha256(temporary)),
                model=dict(id=model_id, sha256=entry["sha256"], native_scale=engine.native_scale,
                           requested_scale=engine.scale, license=entry["license"], source=entry["source"]),
                device=engine.device, precision=engine.precision, tile=engine.tile, tile_pad=engine.tile_pad,
                inference=dict(frames=engine.frames, tiles=engine.tiles, seconds=engine.inference_seconds),
                elapsed_seconds=time.perf_counter()-started)


def upscale_image(source, output, engine, model_id, entry):
    import numpy as np
    from PIL import Image, ImageOps
    source, output = check_paths(source, output)
    if output.suffix.lower() != ".png":
        raise ValueError("Image output must be PNG")
    started, input_sha = time.perf_counter(), sha256(source)
    temporary = temporary_output(output)
    try:
        with Image.open(source) as encoded_image:
            if getattr(encoded_image, "n_frames", 1) != 1:
                raise ValueError("Animated images are unsupported; choose a single frame explicitly")
            encoded_size = encoded_image.size
            exif_orientation = encoded_image.getexif().get(274, 1)
            image = ImageOps.exif_transpose(encoded_image)
            # Pillow may expose 16-bit RGB PNG as RGB, so inspect its IHDR bit depth too.
            with source.open("rb") as handle:
                header = handle.read(26)
            if (header[:8] == b"\x89PNG\r\n\x1a\n" and header[24] == 16) or image.mode not in ("RGB", "RGBA", "L", "LA", "P"):
                raise ValueError("16-bit/high-depth or unsupported image mode; convert explicitly to 8-bit RGB/RGBA")
            image.load()
            alpha = image.convert("RGBA").getchannel("A") if image.mode in ("RGBA", "LA") or "transparency" in image.info else None
            result = Image.fromarray(engine.upscale(np.asarray(image.convert("RGB"))))
            if alpha is not None:
                result.putalpha(alpha.resize(result.size, Image.Resampling.LANCZOS))
            result.save(temporary, format="PNG")
            expected_size, expected_mode = result.size, result.mode
        with Image.open(temporary) as verified:
            verified.load()
            if verified.size != expected_size or verified.mode != expected_mode:
                raise ValueError("PNG validation failed")
        receipt = base_receipt(source, temporary, output, engine, model_id, entry, input_sha, started)
        receipt.update(media=dict(kind="image", input_width=image.width, input_height=image.height,
                                 encoded_input_width=encoded_size[0], encoded_input_height=encoded_size[1],
                                 input_exif_orientation=exif_orientation,
                                 orientation_normalized=exif_orientation in range(2, 9),
                                 output_width=expected_size[0], output_height=expected_size[1], mode=expected_mode),
                       validation=dict(complete_decode=True, dimensions=True, source_unchanged=True,
                                       scope="Technical checks only; image quality has not been reviewed"))
        publish(temporary, output, receipt)
        return receipt
    finally:
        temporary.unlink(missing_ok=True)


def require_ffmpeg():
    for program in ("ffmpeg", "ffprobe"):
        if not shutil.which(program):
            raise RuntimeError(f"{program} is required for video")


def probe_video(path):
    require_ffmpeg()
    command = ["ffprobe", "-v", "error", "-count_frames", "-show_streams", "-show_format", "-of", "json", str(path)]
    result = subprocess.run(command, capture_output=True, text=True)
    if result.returncode or result.stderr.strip():
        raise ValueError(f"ffprobe failed: {result.stderr.strip()}")
    return json.loads(result.stdout)


def video_stream(info):
    streams = [s for s in info["streams"] if s["codec_type"] == "video"]
    if len(streams) != 1:
        raise ValueError("Exactly one video stream is required")
    return streams[0]


def scan_cfr(path, fps, expected_count, time_base=Fraction(1, 1000000)):
    """Check every timestamp with bounded memory; avg_frame_rate alone cannot prove CFR."""
    with tempfile.TemporaryFile() as errors:
        process = subprocess.Popen(["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_frames",
                                    "-show_entries", "frame=best_effort_timestamp_time", "-of", "csv=p=0", str(path)],
                                   stdout=subprocess.PIPE, stderr=errors, text=True)
        count, first = 0, None
        try:
            for line in process.stdout:
                value = line.strip().split(",")[0]
                if not value:
                    continue
                try:
                    stamp = float(value)
                except ValueError as error:
                    raise ValueError("Video is missing frame timestamps") from error
                if not math.isfinite(stamp):
                    raise ValueError("Video has invalid frame timestamps")
                if first is None:
                    first = stamp
                if abs(stamp - (first + count / float(fps))) > max(0.000003, float(time_base) * 1.01):
                    raise ValueError("VFR input is unsupported; convert explicitly to CFR before enlargement")
                count += 1
            if process.wait() != 0:
                errors.seek(0)
                raise ValueError(f"Frame timestamp probe failed: {errors.read().decode(errors='replace')}")
            if count != expected_count or count == 0:
                raise ValueError("Frame timestamp count does not match complete probe decode")
            return first
        finally:
            process.stdout.close()
            stop_process(process)


def validate_input_video(path, info):
    video = video_stream(info)
    if video.get("color_transfer") in ("smpte2084", "arib-std-b67") or video.get("color_primaries") == "bt2020" or int(video.get("bits_per_raw_sample") or 0) > 8 or any(
            marker in video.get("pix_fmt", "") for marker in ("9", "10", "12", "14", "16", "48", "64", "f32")):
        raise ValueError("HDR/high-depth video is unsupported; tone-map explicitly to 8-bit SDR first")
    rotation = float(video.get("tags", {}).get("rotate", 0))
    for side in video.get("side_data_list", []):
        rotation = float(side.get("rotation", rotation))
    if rotation != 0:
        raise ValueError("Nonzero video rotation is unsupported; bake rotation into pixels first")
    if Fraction(video.get("sample_aspect_ratio", "1:1").replace(":", "/")) != 1:
        raise ValueError("Non-square video pixels are unsupported; convert explicitly to square pixels first")
    try:
        fps = Fraction(video["avg_frame_rate"])
        count = int(video["nb_read_frames"])
    except (KeyError, ValueError, ZeroDivisionError) as error:
        raise ValueError("Video requires a valid rational FPS and complete decoded frame count") from error
    if fps <= 0 or count <= 0:
        raise ValueError("Video has no decodable frames or valid FPS")
    time_base = Fraction(video["time_base"])
    first = scan_cfr(path, fps, count, time_base)
    if abs(stream_duration(video) - count / float(fps)) > max(0.000003, float(time_base) * 2):
        raise ValueError("Input video duration is not an exact CFR frame interval; conform explicitly before enlargement")
    return video, fps, count, first


def read_frame(pipe, size):
    """A pipe read may be short; EOF midway through a frame is an error."""
    data = bytearray(size)
    offset = 0
    while offset < size:
        chunk = pipe.read(size-offset)
        if not chunk:
            if offset:
                raise ValueError("Decoder returned a partial RGB frame")
            return None
        data[offset:offset+len(chunk)] = chunk
        offset += len(chunk)
    return data


def stop_process(process):
    if process is not None and process.poll() is None:
        process.terminate()
        try:
            process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait()


def stream_frames(source, temporary, engine, video, fps, expected_count, first, source_info):
    import numpy as np
    width, height = int(video["width"]), int(video["height"])
    out_width, out_height = width*engine.scale, height*engine.scale
    decoder = encoder = None
    with tempfile.TemporaryFile() as decode_errors, tempfile.TemporaryFile() as encode_errors:
        try:
            decoder = subprocess.Popen(["ffmpeg", "-v", "error", "-xerror", "-noautorotate", "-i", str(source),
                                        "-map", "0:v:0", "-an", "-sn", "-dn", "-fps_mode", "passthrough",
                                        "-f", "rawvideo", "-pix_fmt", "rgb24", "pipe:1"],
                                       stdout=subprocess.PIPE, stderr=decode_errors)
            command = ["ffmpeg", "-v", "error", "-xerror", "-y", "-f", "rawvideo", "-pix_fmt", "rgb24",
                       "-video_size", f"{out_width}x{out_height}", "-framerate", str(fps), "-i", "pipe:0",
                       "-copyts", "-itsoffset", str(-first), "-i", str(source), "-map", "0:v:0", "-map", "1:a?",
                       "-map_metadata", "-1", "-c:v", "libx264", "-crf", "18", "-preset", "medium", "-pix_fmt", "yuv420p",
                       "-fps_mode", "passthrough", "-video_track_timescale", str(fps.numerator)]
            # AAC is MP4-compatible; transcode other source audio explicitly.
            audio = [s for s in source_info["streams"] if s["codec_type"] == "audio"]
            for index, stream in enumerate(audio):
                command += [f"-c:a:{index}", "copy" if stream["codec_name"] == "aac" else "aac"]
            command += ["-movflags", "+faststart", str(temporary)]
            encoder = subprocess.Popen(command, stdin=subprocess.PIPE, stderr=encode_errors)
            count = 0
            last_progress = time.perf_counter()
            while True:
                frame = read_frame(decoder.stdout, width*height*3)
                if frame is None:
                    break
                pixels = np.frombuffer(frame, dtype=np.uint8).reshape(height, width, 3)
                enlarged = engine.upscale(pixels)
                encoder.stdin.write(enlarged.tobytes())
                count += 1
                now = time.perf_counter()
                if count == 1 or count == expected_count or now - last_progress >= 5:
                    print(f"Upscaled frames: {count}/{expected_count}", file=sys.stderr, flush=True)
                    last_progress = now
                del frame, pixels, enlarged
            decoder.stdout.close()
            if decoder.wait() != 0:
                decode_errors.seek(0)
                raise ValueError(f"Complete input decode failed: {decode_errors.read().decode(errors='replace')}")
            if count != expected_count:
                raise ValueError(f"Input decoded frame count mismatch: expected {expected_count}, got {count}")
            encoder.stdin.close()
            if encoder.wait() != 0:
                encode_errors.seek(0)
                raise ValueError(f"Video encoder failed: {encode_errors.read().decode(errors='replace')}")
            return count
        except BrokenPipeError as error:
            encode_errors.seek(0)
            raise ValueError(f"Video encoder pipe failed: {encode_errors.read().decode(errors='replace')}") from error
        finally:
            # Stop both children before closing pipes (which might otherwise block on flush).
            stop_process(decoder)
            stop_process(encoder)
            if decoder and decoder.stdout and not decoder.stdout.closed:
                decoder.stdout.close()
            if encoder and encoder.stdin and not encoder.stdin.closed:
                try:
                    encoder.stdin.close()
                except BrokenPipeError:
                    pass


def stream_duration(stream):
    if "duration" in stream:
        return float(stream["duration"])
    # Matroska stores duration in stream tags rather than the MP4 duration field.
    tagged = stream.get("tags", {}).get("DURATION")
    if tagged:
        hours, minutes, seconds = tagged.split(":")
        return int(hours)*3600 + int(minutes)*60 + float(seconds)
    raise ValueError("Cannot verify source/output stream duration")


def validate_output_video(source_info, output_info, scale, fps, count, first=0):
    source, output = video_stream(source_info), video_stream(output_info)
    if (output["width"], output["height"]) != (source["width"]*scale, source["height"]*scale):
        raise ValueError("Output dimensions do not match requested scale")
    if Fraction(output["avg_frame_rate"]) != fps or int(output["nb_read_frames"]) != count:
        raise ValueError("Output FPS/frame count mismatch")
    expected_duration = count / float(fps)
    if abs(float(output["duration"]) - expected_duration) > 0.0001:
        raise ValueError("Output video duration mismatch")
    source_audio = [s for s in source_info["streams"] if s["codec_type"] == "audio"]
    output_audio = [s for s in output_info["streams"] if s["codec_type"] == "audio"]
    if len(source_audio) != len(output_audio):
        raise ValueError("Output audio stream count mismatch")
    for before, after in zip(source_audio, output_audio):
        if after.get("codec_name") != "aac" or int(after["channels"]) != int(before["channels"]):
            raise ValueError("Output audio codec/channel mismatch")
        if abs(stream_duration(before)-stream_duration(after)) > 0.075:
            raise ValueError("Output audio duration mismatch")
        expected_start = float(before.get("start_time", 0)) - first
        if abs(float(after.get("start_time", 0)) - expected_start) > 0.075:
            raise ValueError("Output audio/video synchronization offset mismatch")
        if before["codec_name"] == "aac" and int(before["nb_read_frames"]) != int(after["nb_read_frames"]):
            raise ValueError("Copied AAC audio decoded frame count mismatch")
    if abs(float(source_info["format"]["duration"])-float(output_info["format"]["duration"])) > max(0.075, 1/float(fps)):
        raise ValueError("Output container duration mismatch")


def upscale_video(source, output, engine, model_id, entry):
    source, output = check_paths(source, output)
    if output.suffix.lower() != ".mp4":
        raise ValueError("Video output must be MP4")
    started, input_sha = time.perf_counter(), sha256(source)
    source_info = probe_video(source)
    video, fps, count, first = validate_input_video(source, source_info)
    temporary = temporary_output(output)
    try:
        stream_frames(source, temporary, engine, video, fps, count, first, source_info)
        output_info = probe_video(temporary)
        validate_output_video(source_info, output_info, engine.scale, fps, count, first)
        scan_cfr(temporary, fps, count, Fraction(video_stream(output_info)["time_base"]))
        # Decode every output video/audio packet locally; metadata checks alone are insufficient.
        complete = subprocess.run(["ffmpeg", "-v", "error", "-xerror", "-i", str(temporary),
                                   "-map", "0:v", "-map", "0:a?", "-f", "null", "-"], capture_output=True)
        if complete.returncode:
            raise ValueError(f"Complete output decode failed: {complete.stderr.decode(errors='replace')}")
        output_info["format"]["filename"] = str(output)
        receipt = base_receipt(source, temporary, output, engine, model_id, entry, input_sha, started)
        receipt.update(media=dict(kind="video", fps=str(fps), frames=count, input=source_info, output=output_info),
                       validation=dict(complete_input_decode=True, complete_output_decode=True, dimensions=True,
                                       fps=True, frame_count=True, frame_order="sequential decode/inference/encode; no interpolation",
                                       audio=True, durations=True, source_unchanged=True,
                                       scope="Technical checks only; temporal consistency and perceptual quality are not proven"))
        publish(temporary, output, receipt)
        return receipt
    finally:
        temporary.unlink(missing_ok=True)


def parser():
    shared = argparse.ArgumentParser(add_help=False)
    shared.add_argument("--model", default="realesrgan-x2plus")
    shared.add_argument("--model-dir", type=Path, default=DEFAULT_MODEL_DIR)
    shared.add_argument("--scale", type=int, choices=(2, 4), default=2)
    shared.add_argument("--tile", type=int, default=192)
    shared.add_argument("--tile-pad", type=int, default=16)
    shared.add_argument("--device", choices=("auto", "cuda", "cpu"), default="auto")
    shared.add_argument("--precision", choices=("auto", "fp32", "fp16"), default="auto")
    result = argparse.ArgumentParser(description=__doc__)
    commands = result.add_subparsers(dest="command", required=True)
    commands.add_parser("download", parents=[shared], help="Download and verify only the selected model")
    for command in ("image", "video"):
        child = commands.add_parser(command, parents=[shared])
        child.add_argument("input", type=Path)
        child.add_argument("--output", required=True, type=Path)
    return result


def main(argv=None):
    args = parser().parse_args(argv)
    try:
        models = load_catalog()
        if args.model not in models:
            raise ValueError(f"Unknown model {args.model!r}; choose from {', '.join(models)}")
        entry = models[args.model]
        if args.command == "download":
            print(download_model(entry, args.model_dir))
            return 0
        check_paths(args.input, args.output)
        if args.scale > entry["scale"]:
            raise ValueError("Requested factor exceeds model's native AI scale; select a native x4 model")
        model_path = args.model_dir / entry["file"]
        if not model_path.is_file():
            raise FileNotFoundError(f"Model is missing: {model_path}; run the download subcommand first")
        verify_model(model_path, entry)
        engine = TileEngine(load_descriptor(model_path), entry["scale"], args.scale,
                            args.tile, args.tile_pad, args.device, args.precision)
        function = upscale_image if args.command == "image" else upscale_video
        receipt = function(args.input, args.output, engine, args.model, entry)
        print(json.dumps(receipt, indent=2))
        return 0
    except (ValueError, RuntimeError, OSError, ImportError) as error:
        print(f"media-upscale: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
