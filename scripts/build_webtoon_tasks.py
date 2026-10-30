#!/usr/bin/env python3
"""Turn an approved vertical-scroll storyboard into reproducible Qwen panel tasks."""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SERIES_CONFIG = ROOT / "projects" / "pudding-hamster" / "series.json"
WIDTH_OPTIONS = (512, 640, 768, 896, 1024, 1280, 1536)
HEIGHT_MULTIPLIERS = {
    "peek": 0.5,
    "short": 0.75,
    "standard": 1.0,
    "tall": 1.25,
    "hero": 1.5,
}


def read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def panel_height(width: int, composition_class: str) -> int:
    if composition_class not in HEIGHT_MULTIPLIERS:
        raise ValueError(f"Unknown panel composition_class: {composition_class}")
    raw = width * HEIGHT_MULTIPLIERS[composition_class]
    return max(256, round(raw / 64) * 64)


def build_prompt(
    bible: dict,
    panel: dict,
    segment: dict,
    project: dict,
    reference_roles: list[str],
) -> str:
    hero = next(item for item in bible["characters"] if item["id"] == "hamster-pudding")
    identity = "; ".join(hero["identity_markers"])
    style = bible["visual_style"]
    roles = "\n".join(f"Image {index}: {role}." for index, role in enumerate(reference_roles, 1))
    return f"""Create ONE finished standalone full-color webtoon illustration panel for a phone-first vertical-scroll comic.
This is a single image for one moment, never a comic page, contact sheet, multi-panel layout, collage, or tiled grid.

STORY MOMENT
{segment['story_beat']}
{panel['visual_prompt_en']}

CAMERA AND SCROLL COMPOSITION
{panel['camera']}.
Composition class: {panel['composition_class']}. Leave safe visual breathing room near the listed lettering positions, but do not draw any lettering there.
The image must read clearly by itself at narrow phone width and lead the eye vertically. Use one dominant action or reveal only.

CANONICAL CHARACTER
The only protagonist is the same tiny juvenile male pudding hamster: {identity}.
Natural hamster anatomy, tiny paws, whiskers, rounded ears and soft dense fur; never add clothes, a collar, human-like limbs, or a second golden hamster. Keep him tiny against human hands and household objects. Respect the chapter's continuity state and the described right-cheek sunflower-seed pouch.

FIXED REFERENCE ROLES
{roles}
Use references only for their named purpose. Preserve the character identity and established visual treatment; do not copy their page layout, panel borders, scene, pose, speech balloons, or text.

LOCKED SERIES STYLE
{style['medium']}; {style['linework']}; {style['shading']}.
Palette: {style['palette']}.
Camera language: {style['camera_language']}.
Keep fur edges smooth and readable, clean expressive ink contours, soft cel-like color shading and restrained hatching. Warm cream, pudding gold, caramel, soft amber light and deep blue-black shadows.

ART-ONLY OUTPUT
Do not render words, letters, numbers, captions, dialogue, speech balloons, sound-effect glyphs, signs, logos, signatures, watermarks, borders or gutters. Text will be typeset after generation. No extra animals, props, limbs, fingers or scene details beyond the described moment. No injury or graphic content."""


def build_tasks(project_dir: Path, width: int | None = None) -> dict:
    project_dir = project_dir.resolve()
    project = read_json(project_dir / "project.json")
    bible = read_json(project_dir / "story_bible.json")
    storyboard = read_json(project_dir / "webtoon_storyboard.json")
    series = read_json(SERIES_CONFIG)
    render_config = series["webtoon_generation"]
    width = int(width or render_config["panel_width_default_px"])
    if width not in WIDTH_OPTIONS:
        raise ValueError(f"Width must be one of {WIDTH_OPTIONS}; got {width}.")

    chapter_match = re.fullmatch(r"ch(\d+)", project["chapter_id"])
    if not chapter_match:
        raise ValueError("Webtoon seed derivation requires a chapter id like ch01.")
    chapter_number = int(chapter_match.group(1))

    identity_path = project.get("character_reference_path", series["character_identity_asset"])
    style_path = project.get("style_reference_path", series["style_anchor_page"])
    location_path = project.get("continuity_reference_path")
    reference_roles = [
        (identity_path, "canonical hamster identity; preserve coat, face, proportions and species"),
        (style_path, "fixed cross-chapter ink line, palette and shading reference; ignore its old page layout and lettering"),
    ]
    if location_path:
        reference_roles.append((location_path, "established transparent habitat and prop layout only; do not copy composition"))
    for relative, _role in reference_roles:
        if not (project_dir / relative).is_file():
            raise FileNotFoundError(f"Missing webtoon reference image: {project_dir / relative}")

    panel_number = 0
    panels = []
    for segment in storyboard["segments"]:
        for panel in segment["panels"]:
            panel_number += 1
            seed = int(render_config["series_seed"]) + chapter_number * 10000 + panel_number
            references = [relative for relative, _role in reference_roles]
            roles = [role for _relative, role in reference_roles]
            panels.append({
                "panel_id": panel["panel_id"],
                "segment_id": segment["segment_id"],
                "title": segment["story_beat"],
                "source_spans": segment["source_spans"],
                "adaptation": segment["adaptation"],
                "prompt": build_prompt(bible, panel, segment, project, roles),
                "references": references,
                "reference_roles": roles,
                "composition_class": panel["composition_class"],
                "width": width,
                "height": panel_height(width, panel["composition_class"]),
                "num_inference_steps": int(render_config["num_inference_steps"]),
                "seed": seed,
                "output_path": f"results/panels/{panel['panel_id']}.png",
                "lettering": panel.get("lettering", []),
                "camera": panel["camera"],
            })

    return {
        "schema": "webtoon-tasks.v1",
        "project_id": project["project_id"],
        "chapter_id": project["chapter_id"],
        "title": storyboard["title"],
        "episode_promise": storyboard["episode_promise"],
        "episode_hook": storyboard["episode_hook"],
        "reading_profile": storyboard["reading_profile"],
        "segments": storyboard["segments"],
        "generation": {
            "model_id": "Qwen/Qwen-Image-2.1",
            "backend": "QwenImage21Pipeline on the persistent Colab kernel",
            "mode": "image_edit_with_references",
            "panel_width_px": width,
            "height_by_composition_class": HEIGHT_MULTIPLIERS,
            "num_inference_steps": int(render_config["num_inference_steps"]),
            "dtype": "bfloat16",
            "cpu_offload": True,
            "series_seed": int(render_config["series_seed"]),
            "seed_policy": "effective_seed = series_seed + 10000 * chapter_number + 1_based_panel_number; same panel reruns keep the same seed; different chapters and panels get distinct seeds",
            "upscaler_model_id": render_config["upscaler_model_id"],
            "upscaler_license": render_config["upscaler_license"],
            "upscaler_stage": "optional explicit post-review job; never runs during draft generation",
        },
        "character_reference_path": identity_path,
        "panels": panels,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("project_dir", type=Path)
    parser.add_argument("--width", type=int, choices=WIDTH_OPTIONS)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    target = args.output or args.project_dir / "webtoon_tasks.json"
    tasks = build_tasks(args.project_dir, args.width)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(tasks, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"Built {len(tasks['panels'])} panel tasks at {tasks['generation']['panel_width_px']}px: {target}")


if __name__ == "__main__":
    main()
