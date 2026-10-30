#!/usr/bin/env python3
"""Package one local comic project for upload with the installed Colab CLI."""

from __future__ import annotations

import argparse
import json
import zipfile
from pathlib import Path


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("project_dir", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--worker", type=Path, default=Path("scripts/qwen_image21_worker.py"))
    args = parser.parse_args()
    project = args.project_dir.resolve()
    output = args.output.resolve()
    webtoon = (project / "webtoon_tasks.json").is_file()
    if webtoon:
        required = (
            "source.md",
            "project.json",
            "story_bible.json",
            "webtoon_storyboard.json",
            "webtoon_tasks.json",
        )
        task_data = json.loads((project / "webtoon_tasks.json").read_text(encoding="utf-8"))
        task_key = "panels"
    else:
        required = (
            "source.md",
            "project.json",
            "story_bible.json",
            "page_plan.json",
            "page_tasks.json",
        )
        task_data = json.loads((project / "page_tasks.json").read_text(encoding="utf-8"))
        task_key = "pages"
    carried_assets = {
        task_data.get("character_reference_path", ""),
        *(reference for task in task_data.get(task_key, []) for reference in task.get("references", [])),
    }
    # Carry forward canonical identity/style assets and already generated pages
    # so a later chapter or resumed run never regenerates approved references.
    carry_dirs = (
        ("results/references", "results/panels", "results/upscaled-panels")
        if webtoon
        else ("results/references", "results/pages")
    )
    for relative in carry_dirs:
        carried_assets.update(
            str(path.relative_to(project))
            for path in (project / relative).rglob("*")
            if path.is_file()
        )
    carried_assets.discard("")
    with zipfile.ZipFile(output, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=6) as archive:
        included: set[str] = set()
        for relative in required:
            path = project / relative
            if not path.is_file():
                raise FileNotFoundError(path)
            archive.write(path, relative)
            included.add(relative)
        references = project / "references"
        if references.is_dir():
            for path in sorted(references.rglob("*")):
                if path.is_file():
                    relative = str(path.relative_to(project))
                    if relative not in included:
                        archive.write(path, relative)
                        included.add(relative)
        for relative in sorted(carried_assets):
            path = project / relative
            if path.is_file() and relative not in included:
                archive.write(path, relative)
                included.add(relative)
        archive.write(args.worker.resolve(), "scripts/qwen_image21_worker.py")
    print(f"Packaged {project} -> {output} ({output.stat().st_size} bytes)")


if __name__ == "__main__":
    main()
