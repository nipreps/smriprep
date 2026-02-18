#!/usr/bin/env python3
"""Check and normalize canonical NiPreps Python headers in src/ and test/."""

from __future__ import annotations

import argparse
import re
import subprocess
from pathlib import Path

HEADER_LINES = [
    '# emacs: -*- mode: python; py-indent-offset: 4; indent-tabs-mode: nil -*-',
    '# vi: set ft=python sts=4 ts=4 sw=4 et:',
    '#',
    '# Copyright The NiPreps Developers <nipreps@gmail.com>',
    '#',
    '# Licensed under the Apache License, Version 2.0 (the "License");',
    '# you may not use this file except in compliance with the License.',
    '# You may obtain a copy of the License at',
    '#',
    '#     http://www.apache.org/licenses/LICENSE-2.0',
    '#',
    '# Unless required by applicable law or agreed to in writing, software',
    '# distributed under the License is distributed on an "AS IS" BASIS,',
    '# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.',
    '# See the License for the specific language governing permissions and',
    '# limitations under the License.',
    '#',
    '# We support and encourage derived works from this project, please read',
    '# about our expectations at',
    '#',
    '#     https://www.nipreps.org/community/licensing/',
    '#',
]

CANONICAL_HEADER = '\n'.join(HEADER_LINES) + '\n'

legacy_header_lines = [re.escape(line) for line in HEADER_LINES]
legacy_header_lines[3] = (
    r'# Copyright [0-9]{4}(?:-[0-9]{4})? The NiPreps Developers <nipreps@gmail\.com>'
)
LEGACY_HEADER_WITH_YEAR = re.compile(r'^' + r'\n'.join(legacy_header_lines) + r'\n')

PARTIAL_EDITOR_HEADER = re.compile(
    r'^' + re.escape(HEADER_LINES[0]) + r'\n' + re.escape(HEADER_LINES[1]) + r'\n(?:#\n)?(?:\n)?'
)


def iter_python_files(root: Path) -> list[Path]:
    try:
        result = subprocess.run(
            ['git', 'ls-files', '--cached', '--others', '--exclude-standard', '--', 'src', 'test'],
            check=True,
            capture_output=True,
            text=True,
            cwd=root,
        )
    except (FileNotFoundError, subprocess.CalledProcessError):
        files: list[Path] = []
        for dirname in ('src', 'test'):
            folder = root / dirname
            if folder.exists():
                files.extend(folder.rglob('*.py'))
        return sorted(files, key=lambda path: path.as_posix())

    files = [root / relpath for relpath in result.stdout.splitlines() if relpath.endswith('.py')]
    return sorted(files, key=lambda path: path.as_posix())


def normalize_text(text: str) -> str:
    body = text
    if body.startswith('#!'):
        body = body.split('\n', 1)[1] if '\n' in body else ''

    while True:
        if body.startswith(CANONICAL_HEADER):
            body = body[len(CANONICAL_HEADER) :]
            continue

        year_header = LEGACY_HEADER_WITH_YEAR.match(body)
        if year_header:
            body = body[year_header.end() :]
            continue

        partial_header = PARTIAL_EDITOR_HEADER.match(body)
        if partial_header:
            body = body[partial_header.end() :]
            continue

        break

    return CANONICAL_HEADER + body


def check_files(files: list[Path], root: Path) -> int:
    non_compliant: list[Path] = []
    for path in files:
        text = path.read_text(encoding='utf-8')
        if normalize_text(text) != text:
            non_compliant.append(path)

    if non_compliant:
        for path in non_compliant:
            print(path.relative_to(root).as_posix())
        return 1

    print(f'All {len(files)} Python files have normalized headers.')
    return 0


def fix_files(files: list[Path], root: Path) -> int:
    changed: list[Path] = []
    for path in files:
        text = path.read_text(encoding='utf-8')
        normalized = normalize_text(text)
        if normalized != text:
            path.write_text(normalized, encoding='utf-8')
            changed.append(path)

    if changed:
        print(f'Updated {len(changed)} files:')
        for path in changed:
            print(path.relative_to(root).as_posix())
    else:
        print('No files needed updates.')

    return 0


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description='Check or normalize NiPreps Python headers in src/ and test/.'
    )
    parser.add_argument(
        '--fix',
        action='store_true',
        help='rewrite files to the canonical header format',
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    root = Path(__file__).resolve().parent.parent
    files = iter_python_files(root)
    if args.fix:
        return fix_files(files, root)
    return check_files(files, root)


if __name__ == '__main__':
    raise SystemExit(main())
