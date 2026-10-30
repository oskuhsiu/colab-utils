#!/usr/bin/env python3
"""Validate scroll-first storyboard traceability, references, seeds and panel tasks."""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path


def load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def main() -> int:
    if len(sys.argv) != 2:
        print("usage: validate_webtoon_project.py PROJECT_DIR", file=sys.stderr)
        return 2
    root = Path(sys.argv[1]).resolve()
    source = (root / "source.md").read_text(encoding="utf-8")
    project = load(root / "project.json")
    bible = load(root / "story_bible.json")
    storyboard = load(root / "webtoon_storyboard.json")
    tasks = load(root / "webtoon_tasks.json")
    errors: list[str] = []
    if storyboard.get("schema") != "webtoon-storyboard.v1":
        errors.append("unsupported storyboard schema")
    if tasks.get("schema") != "webtoon-tasks.v1":
        errors.append("unsupported task schema")
    for record in (storyboard, tasks):
        if record.get("project_id") != project["project_id"] or record.get("chapter_id") != project["chapter_id"]:
            errors.append("chapter identity differs between project, storyboard and tasks")
    if storyboard["reading_profile"].get("direction") != "vertical-scroll":
        errors.append("storyboard is not marked for vertical scrolling")
    if not storyboard.get("episode_promise") or not storyboard.get("episode_hook"):
        errors.append("episode promise or ending hook is missing")
    characters = {character["id"] for character in bible["characters"]}
    if "hamster-pudding" not in characters:
        errors.append("canonical pudding hamster is missing")

    planned_panels: list[dict] = []
    segment_ids: set[str] = set()
    for segment in storyboard.get("segments", []):
        segment_id = segment.get("segment_id", "")
        if segment_id in segment_ids:
            errors.append(f"duplicate segment id: {segment_id}")
        segment_ids.add(segment_id)
        if not segment.get("gap_after", {}).get("class") or not segment.get("gap_after", {}).get("reason"):
            errors.append(f"{segment_id} has an unreasoned scroll gap")
        if not segment.get("reader_knows_before") or not segment.get("reveal"):
            errors.append(f"{segment_id} is missing its reader-state transition")
        if not segment.get("adaptation"):
            errors.append(f"{segment_id} is missing its adaptation decision")
        for span in segment.get("source_spans", []):
            if span not in source:
                errors.append(f"{segment_id} source span not found in source.md: {span}")
        planned_panels.extend(segment.get("panels", []))

    task_panels = tasks.get("panels", [])
    planned_ids = [panel["panel_id"] for panel in planned_panels]
    task_ids = [panel["panel_id"] for panel in task_panels]
    if planned_ids != task_ids:
        errors.append("panel task order/IDs differ from the approved storyboard")
    if len(set(task_ids)) != len(task_ids):
        errors.append("panel IDs are not unique")
    seeds = [panel["seed"] for panel in task_panels]
    if len(set(seeds)) != len(seeds):
        errors.append("panel seeds repeat within this chapter")
    if len(planned_panels) != len(task_panels):
        errors.append(f"panel count mismatch: {len(planned_panels)} storyboard vs {len(task_panels)} tasks")

    width = tasks["generation"]["panel_width_px"]
    if width % 64 or not 512 <= width <= 1536:
        errors.append(f"invalid configured panel width: {width}")
    expected_chapter = re.fullmatch(r"ch(\d+)", project["chapter_id"])
    if not expected_chapter:
        errors.append("chapter id must follow chNN for namespaced seed calculation")
    else:
        series_seed = tasks["generation"]["series_seed"]
        chapter_num = int(expected_chapter.group(1))
        for index, panel in enumerate(task_panels, 1):
            if panel["seed"] != series_seed + chapter_num * 10000 + index:
                errors.append(f"{panel['panel_id']} does not follow the recorded seed policy")

    for task in task_panels:
        if not task.get("prompt", "").strip():
            errors.append(f"{task['panel_id']} has an empty prompt")
        if not task.get("references") or task["references"][0] != tasks.get("character_reference_path"):
            errors.append(f"{task['panel_id']} does not use the canonical hamster reference first")
        if any(not (root / relative).is_file() for relative in task["references"]):
            errors.append(f"{task['panel_id']} references a missing image")
        if not task.get("lettering"):
            errors.append(f"{task['panel_id']} has no post-lettering record")

    if errors:
        print("FAIL")
        for error in errors:
            print(f"- {error}")
        return 1
    print(f"PASS: {len(storyboard['segments'])} scroll segments, {len(task_panels)} panels, source spans, references and namespaced seeds valid")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
