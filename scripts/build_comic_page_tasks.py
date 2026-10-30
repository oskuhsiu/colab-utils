#!/usr/bin/env python3
"""Build model-neutral, page-level Qwen image tasks from a comic page plan."""

from __future__ import annotations

import argparse
import json
from pathlib import Path


def read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def build_prompt(story_bible: dict, page: dict, reference_roles: list[str]) -> str:
    style = story_bible["visual_style"]
    hero = next(c for c in story_bible["characters"] if c["id"] == "hamster-pudding")
    panels = "\n".join(
        f"{item['panel']}. {item['beat']}" for item in page["panels"]
    )
    exact_text = "\n".join(
        f"- {item['kind']} ({item.get('speaker', 'narrator')}): 「{item['text']}」"
        for item in page["exact_text"]
    )
    reference_instructions = "\n".join(
        f"Image {index}: {role}." for index, role in enumerate(reference_roles, 1)
    )
    identity = "; ".join(hero["identity_markers"])
    return f"""Create ONE finished full-color manga page as a single portrait image, not a contact sheet.
Page {page['page']} — {page['title']}.

PAGE PURPOSE
{page['purpose']}

REFERENCE IMAGE ROLES
{reference_instructions}
The protagonist is the same juvenile male pudding hamster in every page: {identity}.
Keep his body tiny compared with human hands and household objects. His right cheek pouch contains one striped sunflower seed on pages where the story says it is still present. No clothes, collar, or human-like anatomy.

PAGE DESIGN
- Format: portrait 2:3, {len(page['panels'])} clear manga panels with intentional varied panel sizes, clean gutters, readable right-to-left flow.
- Medium: {style['medium']}; {style['linework']}; {style['shading']}.
- Palette: {style['palette']}.
- Camera: {style['camera_language']}.
- Use a small hamster-scale point of view; make the human and box feel enormous without making the hamster look like a different species.
- Render the listed Traditional Chinese text exactly in clear manga captions/dialogue balloons. Do not add other readable text, labels, logos, signatures, or watermarks.
- Every panel must contain its described scene; do not leave any panel blank, solid black, or filled only with a speech balloon.
- Keep faces, whiskers, paws, sunflower seed, and panel reading order unobstructed. No injury or graphic content.

PANEL BEATS, IN ORDER
{panels}

EXACT TEXT TO INCLUDE
{exact_text}

SOURCE ANCHORS (preserve these events and meanings)
{'; '.join(page['source_anchors'])}
"""


def build_tasks(project_dir: Path) -> dict:
    bible = read_json(project_dir / "story_bible.json")
    plan = read_json(project_dir / "page_plan.json")
    project = read_json(project_dir / "project.json")
    generation = {
        "model_id": "Qwen/Qwen-Image-2.1",
        "backend": "Diffusers QwenImage21Pipeline via Colab CLI",
        "mode": "image_edit_with_references",
        "width": 1696,
        "height": 2528,
        "num_inference_steps": 40,
        "dtype": "bfloat16",
        "cpu_offload": True,
        "seed_base": 2392401,
        "note": "Native Qwen 2K portrait 2:3 canvas (1696x2528); reduce to 1024x1536 only if a runtime reports OOM.",
    }
    character = next(c for c in bible["characters"] if c["id"] == "hamster-pudding")
    ref_prompt = f"""Create a clean visual identity reference for one recurring manga character, with no words and no panel borders.
A single juvenile male pudding hamster, full body in a gentle three-quarter front pose on a plain warm ivory background. Canonical identity: {'; '.join(character['identity_markers'])}. Natural hamster anatomy, soft dense fur, tiny paws and whiskers, alert but dignified expression. Warm full-color hand-inked manga linework with subtle halftone shadows. Center the whole hamster with empty margin around him; no props, no clothes, no cage, no scenery, no text, no watermark."""
    character_reference_path = project.get(
        "character_reference_path",
        "results/references/hamster-character.png",
    )
    reference_task = None
    if not project.get("character_reference_path"):
        reference_task = {
            "prompt": ref_prompt,
            "width": 1024,
            "height": 1024,
            "num_inference_steps": 40,
            "seed": generation["seed_base"],
            "output_path": character_reference_path,
        }
    pages = []
    for page in plan["pages"]:
        page_id = f"page-{page['page']:02d}"
        style_path = project.get("style_reference_path")
        if not style_path and page["page"] > 1:
            style_path = "results/pages/page-01.png"
        continuity_path = project.get("continuity_reference_path") if page["page"] == 1 else None
        if page["page"] > 1:
            continuity_path = f"results/pages/page-{page['page'] - 1:02d}.png"
        references = [character_reference_path]
        reference_roles = ["canonical hamster identity; preserve coat pattern, face, proportions, and species"]
        if style_path and style_path not in references:
            references.append(style_path)
            reference_roles.append("approved visual style/color/linework reference; do not copy its scene composition")
        if continuity_path and continuity_path not in references:
            references.append(continuity_path)
            reference_roles.append("previous accepted page for continuity only; do not repeat its panel content")
        pages.append(
            {
                "page_id": page_id,
                "page_number": page["page"],
                "title": page["title"],
                "prompt": build_prompt(bible, page, reference_roles),
                "references": references,
                "reference_roles": reference_roles,
                "width": generation["width"],
                "height": generation["height"],
                "num_inference_steps": generation["num_inference_steps"],
                "seed": generation["seed_base"] + page["page"],
                "output_path": f"results/pages/{page_id}.png",
                "source_anchors": page["source_anchors"],
                "exact_text": page["exact_text"],
            }
        )
    return {
        "project_id": project["project_id"],
        "chapter_id": project["chapter_id"],
        "generation": generation,
        "character_reference": reference_task,
        "character_reference_path": character_reference_path,
        "pages": pages,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("project_dir", type=Path)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    target = args.output or args.project_dir / "page_tasks.json"
    tasks = build_tasks(args.project_dir)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(tasks, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"Built {len(tasks['pages'])} page tasks: {target}")


if __name__ == "__main__":
    main()
