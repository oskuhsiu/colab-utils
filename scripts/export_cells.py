#!/usr/bin/env python3
"""Export one notebook section for a persistent Colab CLI kernel (stdlib only)."""

import argparse
import json
from pathlib import Path


def export_section(notebook_path, section):
    notebook = json.loads(Path(notebook_path).read_text())
    cells = [cell for cell in notebook["cells"] if cell["cell_type"] == "code"
             and (section == "all" or section in cell.get("metadata", {}).get("tags", []))]
    if not cells:
        raise ValueError(f"No code cells tagged {section!r} in {notebook_path}")
    return "\n\n".join(
        f"# Notebook cell: {cell['id']}\n{''.join(cell['source']).rstrip()}" for cell in cells
    ) + "\n"


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("section", choices=("setup", "clip", "all"))
    parser.add_argument("--notebook", type=Path,
                        default=Path(__file__).resolve().parents[1] / "notebooks/MiniMax_H3_A100.ipynb")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.output.resolve() == args.notebook.resolve():
        parser.error("Output must not overwrite the notebook")
    source = export_section(args.notebook, args.section)
    compile(source, str(args.output), "exec")
    args.output.write_text(source)
    print(args.output)


if __name__ == "__main__":
    main()
