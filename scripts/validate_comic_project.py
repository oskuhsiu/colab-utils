#!/usr/bin/env python3
"""Validate source anchors, character canon, and page-task handoffs."""

from __future__ import annotations

import json
import sys
from pathlib import Path


def load(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def main() -> int:
    if len(sys.argv) != 2:
        print("usage: validate_comic_project.py PROJECT_DIR", file=sys.stderr)
        return 2
    root = Path(sys.argv[1])
    source = (root / "source.md").read_text(encoding="utf-8")
    project = load(root / "project.json")
    bible = load(root / "story_bible.json")
    plan = load(root / "page_plan.json")
    tasks = load(root / "page_tasks.json")
    errors = []
    if project["chapter_id"] != plan["chapter_id"] or project["chapter_id"] != tasks["chapter_id"]:
        errors.append("chapter_id differs between project, page plan, and tasks")
    planned = plan["pages"]
    generated = tasks["pages"]
    canonical_reference = tasks.get("character_reference_path", "")
    if len(planned) != len(generated):
        errors.append(f"page count mismatch: {len(planned)} plan vs {len(generated)} tasks")
    if len({p["page_id"] for p in generated}) != len(generated):
        errors.append("page_id values are not unique")
    character_ids = {c["id"] for c in bible["characters"]}
    if "hamster-pudding" not in character_ids:
        errors.append("canonical protagonist hamster-pudding is missing")
    for page in planned:
        for anchor in page["source_anchors"]:
            if anchor not in source:
                errors.append(f"page {page['page']} source anchor not found: {anchor}")
    for task in generated:
        if not task["prompt"].strip():
            errors.append(f"{task['page_id']} has an empty prompt")
        if not task["references"] or task["references"][0] != canonical_reference:
            errors.append(f"{task['page_id']} does not reference the canonical hamster image first")
        for item in task["exact_text"]:
            if item["text"] not in task["prompt"]:
                errors.append(f"{task['page_id']} prompt omits exact text: {item['text']}")
    if errors:
        print("FAIL")
        for error in errors:
            print(f"- {error}")
        return 1
    print(f"PASS: {len(planned)} pages, {len(character_ids)} character records, all source anchors and text tasks valid")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
