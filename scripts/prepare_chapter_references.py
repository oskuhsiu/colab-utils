#!/usr/bin/env python3
"""Carry the approved character/style anchors from one chapter into the next."""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
from datetime import datetime, timezone
from pathlib import Path


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("previous_chapter", type=Path)
    parser.add_argument("next_chapter", type=Path)
    args = parser.parse_args()
    previous = args.previous_chapter.resolve()
    target = args.next_chapter.resolve()
    source_files = {
        "character": previous / "results/references/hamster-character.png",
        "style": previous / "results/pages/page-01.png",
        "chapter_transition": previous / "results/pages/page-06.png",
    }
    missing = [path for path in source_files.values() if not path.is_file()]
    if missing:
        raise FileNotFoundError("Generate and inspect the prior chapter first:\n" + "\n".join(map(str, missing)))

    references_dir = target / "references"
    references_dir.mkdir(parents=True, exist_ok=True)
    destinations = {
        "character": references_dir / "hamster-character.png",
        "style": references_dir / "chapter-01-page-01.png",
        "chapter_transition": references_dir / "chapter-01-page-06.png",
    }
    entries = {}
    for role, source in source_files.items():
        destination = destinations[role]
        shutil.copy2(source, destination)
        entries[role] = {
            "source": str(source),
            "path": str(destination.relative_to(target)),
            "sha256": sha256(destination),
            "bytes": destination.stat().st_size,
        }
    manifest = {
        "from_chapter": "ch01",
        "to_chapter": "ch02",
        "created_utc": datetime.now(timezone.utc).isoformat(),
        "assets": entries,
    }
    (references_dir / "continuity-manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps(manifest, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
