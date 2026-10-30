#!/usr/bin/env python3
"""Generate comic page tasks with a caller-owned Qwen Image 2.1 pipeline.

This module deliberately does not load a model. The Colab notebook owns the
persistent pipeline and passes the same instance to ``run_project`` for every
chapter submitted to that kernel.
"""

from __future__ import annotations

import importlib.metadata
import hashlib
import json
import platform
import re
import time
import traceback
from datetime import datetime, timezone
from pathlib import Path

import torch
from PIL import Image, ImageDraw


def package_version(name: str) -> str:
    try:
        return importlib.metadata.version(name)
    except importlib.metadata.PackageNotFoundError:
        return "not-installed"


def read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, value: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def load_reference(path: Path) -> Image.Image:
    if not path.is_file():
        raise FileNotFoundError(f"Required reference image is missing: {path}")
    with Image.open(path) as image:
        return image.convert("RGB")


def chapter_pdf_name(chapter_id: str) -> str:
    match = re.fullmatch(r"ch(\d+)", chapter_id)
    return f"chapter-{int(match.group(1)):02d}.pdf" if match else f"{chapter_id}.pdf"


def compose_deliverables(project_dir: Path, task_data: dict) -> dict | None:
    image_paths = [project_dir / task["output_path"] for task in task_data["pages"]]
    if any(not path.is_file() for path in image_paths):
        return None
    deliverables_dir = project_dir / "results" / "deliverables"
    deliverables_dir.mkdir(parents=True, exist_ok=True)
    pages = []
    for path in image_paths:
        with Image.open(path) as image:
            pages.append(image.convert("RGB"))
    pdf_path = deliverables_dir / chapter_pdf_name(task_data["chapter_id"])
    pages[0].save(pdf_path, "PDF", save_all=True, append_images=pages[1:], resolution=150.0)

    thumb_width, margin, gap, columns = 288, 24, 20, 3
    thumbs = []
    for index, image in enumerate(pages, 1):
        height = round(image.height * thumb_width / image.width)
        thumb = image.resize((thumb_width, height), Image.Resampling.LANCZOS)
        framed = Image.new("RGB", (thumb_width, height + 32), "white")
        framed.paste(thumb, (0, 32))
        ImageDraw.Draw(framed).text((6, 8), f"Page {index}", fill="#222222")
        thumbs.append(framed)
    rows = (len(thumbs) + columns - 1) // columns
    cell_height = max(item.height for item in thumbs)
    sheet = Image.new(
        "RGB",
        (margin * 2 + columns * thumb_width + (columns - 1) * gap,
         margin * 2 + rows * cell_height + (rows - 1) * gap),
        "#e8e5df",
    )
    for index, thumb in enumerate(thumbs):
        x = margin + (index % columns) * (thumb_width + gap)
        y = margin + (index // columns) * (cell_height + gap)
        sheet.paste(thumb, (x, y))
    contact_path = deliverables_dir / "contact-sheet.png"
    sheet.save(contact_path, optimize=True)
    return {
        "pdf": str(pdf_path.relative_to(project_dir)),
        "pdf_bytes": pdf_path.stat().st_size,
        "contact_sheet": str(contact_path.relative_to(project_dir)),
        "page_count": len(pages),
    }


def render(pipe, prompt: str, *, width: int, height: int, steps: int, seed: int, images=None):
    generator = torch.Generator(device="cuda").manual_seed(seed)
    kwargs = {
        "prompt": prompt,
        "width": width,
        "height": height,
        "num_inference_steps": steps,
        "generator": generator,
    }
    if images:
        kwargs["image"] = images[0] if len(images) == 1 else images
    with torch.inference_mode():
        result = pipe(**kwargs)
    return result.images[0].convert("RGB")


def run_project(
    pipe,
    project_dir: Path,
    *,
    phase: str = "all",
    force_pages: set[str] | None = None,
    model_instance_id: str | None = None,
    model_load_seconds: float | None = None,
    model_reused: bool = True,
    session_name: str | None = None,
) -> dict:
    """Generate one project's pages without constructing or replacing a model."""
    if phase not in ("first-page", "all"):
        raise ValueError(f"Unsupported phase: {phase}")
    force_pages = force_pages or set()
    project_dir = project_dir.resolve()
    task_data = read_json(project_dir / "page_tasks.json")
    settings = task_data["generation"]
    results_dir = project_dir / "results"
    pages_dir = results_dir / "pages"
    pages_dir.mkdir(parents=True, exist_ok=True)
    character_ref = project_dir / task_data["character_reference_path"]
    run_started = time.perf_counter()
    if not torch.cuda.is_available():
        raise RuntimeError("CUDA is unavailable; this Colab session must have a GPU runtime.")

    props = torch.cuda.get_device_properties(0)
    manifest = {
        "status": "running",
        "project_id": task_data["project_id"],
        "chapter_id": task_data["chapter_id"],
        "started_utc": datetime.now(timezone.utc).isoformat(),
        "phase": phase,
        "model_id": settings["model_id"],
        "model_instance_id": model_instance_id,
        "model_reused": model_reused,
        "model_load_seconds": model_load_seconds,
        "session_name": session_name,
        "generation_settings": settings,
        "runtime": {
            "python": platform.python_version(),
            "torch": torch.__version__,
            "diffusers": package_version("diffusers"),
            "transformers": package_version("transformers"),
            "accelerate": package_version("accelerate"),
            "gpu": torch.cuda.get_device_name(0),
            "gpu_memory_gib": round(props.total_memory / 2**30, 2),
        },
        "reference_image": str(character_ref.relative_to(project_dir)),
        "pages": [],
    }

    try:
        ref_task = task_data.get("character_reference")
        if ref_task and not character_ref.exists():
            started = time.perf_counter()
            reference = render(
                pipe,
                ref_task["prompt"],
                width=ref_task["width"],
                height=ref_task["height"],
                steps=ref_task["num_inference_steps"],
                seed=ref_task["seed"],
            )
            character_ref.parent.mkdir(parents=True, exist_ok=True)
            reference.save(character_ref, format="PNG", optimize=True)
            manifest["character_reference_seconds"] = round(time.perf_counter() - started, 2)
            manifest["character_reference_seed"] = ref_task["seed"]
            print(f"Saved canonical character reference: {character_ref}", flush=True)
        elif not character_ref.is_file():
            raise FileNotFoundError(f"Canonical character reference is missing: {character_ref}")

        page_tasks = task_data["pages"][:1] if phase == "first-page" else task_data["pages"]
        for task in page_tasks:
            output_path = project_dir / task["output_path"]
            if output_path.exists() and task["page_id"] not in force_pages:
                manifest["pages"].append(
                    {"page_id": task["page_id"], "status": "skipped_existing", "output_path": task["output_path"]}
                )
                continue
            image_refs = [load_reference(project_dir / relative) for relative in task["references"]]
            torch.cuda.empty_cache()
            torch.cuda.reset_peak_memory_stats()
            started = time.perf_counter()
            try:
                image = render(
                    pipe,
                    task["prompt"],
                    width=task["width"],
                    height=task["height"],
                    steps=task["num_inference_steps"],
                    seed=task["seed"],
                    images=image_refs,
                )
                output_path.parent.mkdir(parents=True, exist_ok=True)
                image.save(output_path, format="PNG", optimize=True)
                torch.cuda.synchronize()
                page_record = {
                    "page_id": task["page_id"],
                    "title": task["title"],
                    "status": "generated",
                    "seed": task["seed"],
                    "references": task["references"],
                    "width": image.width,
                    "height": image.height,
                    "seconds": round(time.perf_counter() - started, 2),
                    "peak_cuda_allocated_gib": round(torch.cuda.max_memory_allocated() / 2**30, 2),
                    "output_path": task["output_path"],
                    "output_bytes": output_path.stat().st_size,
                }
            except Exception as exc:
                page_record = {
                    "page_id": task["page_id"],
                    "title": task["title"],
                    "status": "failed",
                    "seed": task["seed"],
                    "seconds": round(time.perf_counter() - started, 2),
                    "error": f"{type(exc).__name__}: {exc}",
                    "traceback": traceback.format_exc(),
                    "output_path": task["output_path"],
                }
            manifest["pages"].append(page_record)
            write_json(results_dir / "run_manifest.json", manifest)
            print(json.dumps(page_record, ensure_ascii=False), flush=True)
            if page_record["status"] == "failed" and task["page_number"] == 1:
                raise RuntimeError(f"First page failed: {page_record['error']}")

        failures = [item for item in manifest["pages"] if item["status"] == "failed"]
        generated = [item for item in manifest["pages"] if item["status"] in ("generated", "skipped_existing")]
        manifest["status"] = "partial" if failures else ("first_page_ready" if phase == "first-page" else "generated")
        manifest["generated_or_existing_pages"] = len(generated)
        manifest["failed_pages"] = len(failures)
        if phase == "all" and not failures:
            manifest["deliverables"] = compose_deliverables(project_dir, task_data)
        manifest["total_seconds"] = round(time.perf_counter() - run_started, 2)
        write_json(results_dir / "run_manifest.json", manifest)
        print(json.dumps(manifest, ensure_ascii=False, indent=2), flush=True)
        return manifest
    except Exception as exc:
        manifest["status"] = "failed"
        manifest["error"] = f"{type(exc).__name__}: {exc}"
        manifest["traceback"] = traceback.format_exc()
        manifest["total_seconds"] = round(time.perf_counter() - run_started, 2)
        write_json(results_dir / "run_manifest.json", manifest)
        raise


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def webtoon_task_fingerprint(task: dict) -> str:
    reproducibility_fields = {
        key: task.get(key)
        for key in ("prompt", "references", "reference_roles", "width", "height", "num_inference_steps", "seed")
    }
    encoded = json.dumps(reproducibility_fields, ensure_ascii=False, sort_keys=True).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def run_webtoon_project(
    pipe,
    project_dir: Path,
    *,
    phase: str = "all",
    force_panels: set[str] | None = None,
    model_instance_id: str | None = None,
    model_load_seconds: float | None = None,
    model_reused: bool = True,
    session_name: str | None = None,
    panel_width: int | None = None,
) -> dict:
    """Generate standalone webtoon panels without loading or replacing a model."""
    if phase not in ("first-panel", "all"):
        raise ValueError(f"Unsupported webtoon phase: {phase}")
    force_panels = force_panels or set()
    project_dir = project_dir.resolve()
    task_data = read_json(project_dir / "webtoon_tasks.json")
    settings = task_data["generation"]
    if settings["model_id"] != "Qwen/Qwen-Image-2.1":
        raise ValueError(f"Unsupported image model: {settings['model_id']}")
    selected_width = int(panel_width or settings["panel_width_px"])
    height_multipliers = settings["height_by_composition_class"]
    if selected_width % 64 or not 512 <= selected_width <= 1536:
        raise ValueError(f"Panel width must be a multiple of 64 between 512 and 1536; got {selected_width}.")
    if not torch.cuda.is_available():
        raise RuntimeError("CUDA is unavailable; this Colab session must have a GPU runtime.")

    results_dir = project_dir / "results"
    panel_dir = results_dir / "panels"
    panel_dir.mkdir(parents=True, exist_ok=True)
    manifest_path = results_dir / "webtoon_run_manifest.json"
    prior_records = {}
    if manifest_path.is_file():
        previous = read_json(manifest_path)
        prior_records = {record["panel_id"]: record for record in previous.get("panels", [])}

    device = torch.cuda.get_device_properties(0)
    reference_hashes = {}
    for relative in sorted({reference for task in task_data["panels"] for reference in task["references"]}):
        reference_path = project_dir / relative
        if not reference_path.is_file():
            raise FileNotFoundError(f"Required webtoon reference is missing: {reference_path}")
        reference_hashes[relative] = sha256_file(reference_path)

    manifest = {
        "status": "running",
        "schema": task_data["schema"],
        "project_id": task_data["project_id"],
        "chapter_id": task_data["chapter_id"],
        "title": task_data["title"],
        "started_utc": datetime.now(timezone.utc).isoformat(),
        "phase": phase,
        "model_id": settings["model_id"],
        "model_instance_id": model_instance_id,
        "model_reused": model_reused,
        "model_load_seconds": model_load_seconds,
        "session_name": session_name,
        "generation_settings": {**settings, "selected_panel_width_px": selected_width},
        "reference_hashes_sha256": reference_hashes,
        "runtime": {
            "python": platform.python_version(),
            "torch": torch.__version__,
            "diffusers": package_version("diffusers"),
            "transformers": package_version("transformers"),
            "accelerate": package_version("accelerate"),
            "gpu": torch.cuda.get_device_name(0),
            "gpu_memory_gib": round(device.total_memory / 2**30, 2),
        },
        "panels": [],
    }
    started_run = time.perf_counter()
    panel_tasks = task_data["panels"][:1] if phase == "first-panel" else task_data["panels"]

    try:
        for task in panel_tasks:
            render_task = dict(task)
            render_task["width"] = selected_width
            render_task["height"] = max(
                256,
                round(selected_width * float(height_multipliers[task["composition_class"]]) / 64) * 64,
            )
            output_path = project_dir / task["output_path"]
            fingerprint = webtoon_task_fingerprint(render_task)
            prior = prior_records.get(task["panel_id"], {})
            if (
                output_path.is_file()
                and prior.get("task_fingerprint") == fingerprint
                and task["panel_id"] not in force_panels
            ):
                record = {
                    "panel_id": task["panel_id"],
                    "segment_id": task["segment_id"],
                    "seed": task["seed"],
                    "task_fingerprint": fingerprint,
                    "status": "skipped_existing",
                    "output_path": task["output_path"],
                    "width": render_task["width"],
                    "height": render_task["height"],
                }
                manifest["panels"].append(record)
                print(json.dumps(record, ensure_ascii=False), flush=True)
                continue

            image_refs = [load_reference(project_dir / relative) for relative in task["references"]]
            torch.cuda.empty_cache()
            torch.cuda.reset_peak_memory_stats()
            started = time.perf_counter()
            try:
                image = render(
                    pipe,
                    task["prompt"],
                    width=render_task["width"],
                    height=render_task["height"],
                    steps=render_task["num_inference_steps"],
                    seed=render_task["seed"],
                    images=image_refs,
                )
                output_path.parent.mkdir(parents=True, exist_ok=True)
                image.save(output_path, format="PNG", optimize=True)
                torch.cuda.synchronize()
                record = {
                    "panel_id": task["panel_id"],
                    "segment_id": task["segment_id"],
                    "title": task["title"],
                    "status": "generated",
                    "seed": task["seed"],
                    "task_fingerprint": fingerprint,
                    "references": task["references"],
                    "width": image.width,
                    "height": image.height,
                    "seconds": round(time.perf_counter() - started, 2),
                    "peak_cuda_allocated_gib": round(torch.cuda.max_memory_allocated() / 2**30, 2),
                    "output_path": task["output_path"],
                    "output_bytes": output_path.stat().st_size,
                }
            except Exception as exc:
                record = {
                    "panel_id": task["panel_id"],
                    "segment_id": task["segment_id"],
                    "status": "failed",
                    "seed": task["seed"],
                    "task_fingerprint": fingerprint,
                    "seconds": round(time.perf_counter() - started, 2),
                    "error": f"{type(exc).__name__}: {exc}",
                    "traceback": traceback.format_exc(),
                    "output_path": task["output_path"],
                }
            manifest["panels"].append(record)
            write_json(manifest_path, manifest)
            print(json.dumps(record, ensure_ascii=False), flush=True)
            if record["status"] == "failed" and task["panel_id"] == task_data["panels"][0]["panel_id"]:
                raise RuntimeError(f"First webtoon panel failed: {record['error']}")

        failures = [record for record in manifest["panels"] if record["status"] == "failed"]
        complete = [record for record in manifest["panels"] if record["status"] in ("generated", "skipped_existing")]
        manifest["status"] = "partial" if failures else ("first_panel_ready" if phase == "first-panel" else "generated")
        manifest["generated_or_existing_panels"] = len(complete)
        manifest["failed_panels"] = len(failures)
        manifest["total_seconds"] = round(time.perf_counter() - started_run, 2)
        manifest["finished_utc"] = datetime.now(timezone.utc).isoformat()
        write_json(manifest_path, manifest)
        print(json.dumps(manifest, ensure_ascii=False, indent=2), flush=True)
        return manifest
    except Exception as exc:
        manifest["status"] = "failed"
        manifest["error"] = f"{type(exc).__name__}: {exc}"
        manifest["traceback"] = traceback.format_exc()
        manifest["total_seconds"] = round(time.perf_counter() - started_run, 2)
        write_json(manifest_path, manifest)
        raise


def run_webtoon_upscale(
    project_dir: Path,
    *,
    runtime_cache: dict,
    factor: int = 2,
    qwen_model_instance_id: str | None = None,
    session_name: str | None = None,
) -> dict:
    """Apply a separate x2 Swin2SR pass; it never loads or replaces Qwen."""
    if factor != 2:
        raise ValueError("The configured Swin2SR model performs exactly 2x super-resolution.")
    project_dir = project_dir.resolve()
    tasks = read_json(project_dir / "webtoon_tasks.json")
    model_id = tasks["generation"]["upscaler_model_id"]
    if not torch.cuda.is_available():
        raise RuntimeError("CUDA is unavailable; this Colab session must have a GPU runtime.")
    cached = runtime_cache.get("webtoon_swin2sr")
    if cached is None:
        from transformers import AutoImageProcessor, Swin2SRForImageSuperResolution

        processor = AutoImageProcessor.from_pretrained(model_id, cache_dir="/content/webtoon-upscaler-cache")
        model = Swin2SRForImageSuperResolution.from_pretrained(
            model_id, cache_dir="/content/webtoon-upscaler-cache"
        ).eval().to("cuda")
        cached = {"processor": processor, "model": model}
        runtime_cache["webtoon_swin2sr"] = cached

    output_dir = project_dir / "results" / "upscaled-panels"
    output_dir.mkdir(parents=True, exist_ok=True)
    manifest_path = project_dir / "results" / "upscale_manifest.json"
    gpu = torch.cuda.get_device_properties(0)
    manifest = {
        "status": "running",
        "chapter_id": tasks["chapter_id"],
        "started_utc": datetime.now(timezone.utc).isoformat(),
        "upscaler_model_id": model_id,
        "upscaler_license": tasks["generation"].get("upscaler_license"),
        "scale_factor": factor,
        "qwen_model_instance_id": qwen_model_instance_id,
        "qwen_model_reloaded": False,
        "session_name": session_name,
        "runtime": {
            "python": platform.python_version(),
            "torch": torch.__version__,
            "transformers": package_version("transformers"),
            "gpu": torch.cuda.get_device_name(0),
            "gpu_memory_gib": round(gpu.total_memory / 2**30, 2),
        },
        "panels": [],
    }
    started_run = time.perf_counter()
    previous_manifest = read_json(manifest_path) if manifest_path.is_file() else {}
    previous_upscale_records = {
        row["panel_id"]: row for row in previous_manifest.get("panels", [])
    }
    try:
        for task in tasks["panels"]:
            input_path = project_dir / task["output_path"]
            if not input_path.is_file():
                raise FileNotFoundError(f"Cannot upscale missing draft panel: {input_path}")
            output_path = output_dir / f"{task['panel_id']}.png"
            source_hash = sha256_file(input_path)
            previous = previous_upscale_records.get(task["panel_id"])
            if output_path.is_file() and previous and previous.get("source_sha256") == source_hash:
                manifest["panels"].append({
                    "panel_id": task["panel_id"], "status": "skipped_existing", "source_sha256": source_hash,
                    "seed": task["seed"], "output_path": str(output_path.relative_to(project_dir)),
                })
                continue

            with Image.open(input_path) as source_image:
                source_image = source_image.convert("RGB")
                target_width = source_image.width * factor
                target_height = source_image.height * factor
                inputs = cached["processor"](source_image, return_tensors="pt", do_resize=False)
                source_size = list(source_image.size)
            inputs = {key: value.to("cuda") for key, value in inputs.items()}
            torch.cuda.empty_cache()
            torch.cuda.reset_peak_memory_stats()
            started = time.perf_counter()
            with torch.inference_mode():
                outputs = cached["model"](**inputs)
            array = outputs.reconstruction.data.squeeze().float().cpu().clamp_(0, 1).numpy()
            import numpy as np

            array = np.moveaxis(array, source=0, destination=-1)
            array = (array * 255.0).round().astype(np.uint8)
            if array.shape[1] < target_width or array.shape[0] < target_height:
                raise RuntimeError(
                    f"Swin2SR output is smaller than 2x target: "
                    f"{array.shape[1]}x{array.shape[0]} vs {target_width}x{target_height}"
                )
            # Swin2SR pads its input for windowed attention; crop the extra
            # right/bottom pad to keep the final webtoon panel exactly 2x.
            array = array[:target_height, :target_width]
            Image.fromarray(array).save(output_path, format="PNG", optimize=True)
            torch.cuda.synchronize()
            record = {
                "panel_id": task["panel_id"],
                "status": "upscaled",
                "seed": task["seed"],
                "source_sha256": source_hash,
                "source_size": source_size,
                "output_size": [int(array.shape[1]), int(array.shape[0])],
                "seconds": round(time.perf_counter() - started, 2),
                "peak_cuda_allocated_gib": round(torch.cuda.max_memory_allocated() / 2**30, 2),
                "peak_cuda_reserved_gib": round(torch.cuda.max_memory_reserved() / 2**30, 2),
                "output_path": str(output_path.relative_to(project_dir)),
                "output_bytes": output_path.stat().st_size,
            }
            manifest["panels"].append(record)
            write_json(manifest_path, manifest)
            print(json.dumps(record, ensure_ascii=False), flush=True)
        manifest["status"] = "complete"
        manifest["total_seconds"] = round(time.perf_counter() - started_run, 2)
        manifest["finished_utc"] = datetime.now(timezone.utc).isoformat()
        write_json(manifest_path, manifest)
        print(json.dumps(manifest, ensure_ascii=False, indent=2), flush=True)
        return manifest
    except Exception as exc:
        manifest["status"] = "failed"
        manifest["error"] = f"{type(exc).__name__}: {exc}"
        manifest["traceback"] = traceback.format_exc()
        manifest["total_seconds"] = round(time.perf_counter() - started_run, 2)
        write_json(manifest_path, manifest)
        raise
