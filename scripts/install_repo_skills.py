#!/usr/bin/env python3
"""Create repo-local skill discovery links without replacing user files.

No packages, credentials or global agent configuration are changed.
"""
from __future__ import annotations
import argparse
import os
from pathlib import Path


def install(root: Path, *, check: bool = False) -> list[str]:
    root = root.resolve()
    destination = root / '.agents' / 'skills'
    sources = sorted(p.parent for p in (root / 'skills').glob('*/SKILL.md'))
    if not sources:
        raise ValueError('No skills/*/SKILL.md found')
    # Do not follow an existing discovery-directory symlink outside this repo.
    for directory in (root / '.agents', destination):
        if directory.is_symlink():
            raise ValueError(f'Refusing symlink discovery directory: {directory}')
        if directory.exists() and not directory.is_dir():
            raise ValueError(f'Not a directory: {directory}')
    missing = []
    for source in sources:
        link = destination / source.name
        if link.is_symlink() and link.resolve() == source.resolve():
            continue
        if link.exists() or link.is_symlink():
            raise ValueError(f'Existing path has a different target; left unchanged: {link}')
        missing.append((source, link))
    if check:
        if missing:
            raise ValueError('Missing skill links: ' + ', '.join(source.name for source, _ in missing))
    else:
        destination.mkdir(parents=True, exist_ok=True)
        for source, link in missing:
            link.symlink_to(os.path.relpath(source, destination), target_is_directory=True)
    return [source.name for source in sources]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--check', action='store_true')
    args = parser.parse_args()
    try:
        names = install(Path(__file__).resolve().parents[1], check=args.check)
    except (ValueError, OSError) as exc:
        parser.exit(1, str(exc) + '\n')
    print(('Verified' if args.check else 'Installed') + ' repo skills: ' + ', '.join(names))


if __name__ == '__main__':
    main()
