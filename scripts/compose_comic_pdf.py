#!/usr/bin/env python3
"""Assemble reviewed full-page PNGs into a local PDF and contact sheet."""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

from PIL import Image, ImageDraw


def chapter_pdf_name(chapter_id: str) -> str:
    match = re.fullmatch(r"ch(\d+)", chapter_id)
    return f"chapter-{int(match.group(1)):02d}.pdf" if match else f"{chapter_id}.pdf"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("project_dir", type=Path)
    parser.add_argument("--output-dir", type=Path)
    args = parser.parse_args()
    project = args.project_dir.resolve()
    output_dir = (args.output_dir or project / "deliverables").resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    tasks = json.loads((project / "page_tasks.json").read_text(encoding="utf-8"))
    page_paths = [project / page["output_path"] for page in tasks["pages"]]
    missing = [path for path in page_paths if not path.is_file()]
    if missing:
        raise FileNotFoundError("Missing generated pages:\n" + "\n".join(map(str, missing)))
    pages = []
    for path in page_paths:
        with Image.open(path) as image:
            pages.append(image.convert("RGB"))
    pdf_path = output_dir / chapter_pdf_name(tasks["chapter_id"])
    pages[0].save(pdf_path, "PDF", save_all=True, append_images=pages[1:], resolution=150.0)

    thumb_w = 288
    margin = 24
    gap = 20
    thumbs = []
    for index, image in enumerate(pages, 1):
        h = round(image.height * thumb_w / image.width)
        thumb = image.resize((thumb_w, h), Image.Resampling.LANCZOS)
        framed = Image.new("RGB", (thumb_w, h + 30), "white")
        framed.paste(thumb, (0, 30))
        ImageDraw.Draw(framed).text((4, 8), f"Page {index}", fill="#222222")
        thumbs.append(framed)
    cols = 3
    rows = (len(thumbs) + cols - 1) // cols
    cell_h = max(item.height for item in thumbs)
    sheet = Image.new("RGB", (margin * 2 + cols * thumb_w + (cols - 1) * gap,
                               margin * 2 + rows * cell_h + (rows - 1) * gap), "#e8e5df")
    for index, thumb in enumerate(thumbs):
        x = margin + (index % cols) * (thumb_w + gap)
        y = margin + (index // cols) * (cell_h + gap)
        sheet.paste(thumb, (x, y))
    contact_path = output_dir / "contact-sheet.png"
    sheet.save(contact_path, optimize=True)
    print(json.dumps({"pdf": str(pdf_path), "pages": len(pages), "bytes": pdf_path.stat().st_size,
                      "contact_sheet": str(contact_path)}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
