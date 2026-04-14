#!/usr/bin/env python3
"""Lint: verify that tasks/manifest.yaml and the task_*.md files are in sync.

Checks performed:
1. Every entry in the manifest has a corresponding .md file.
2. Every task_*.md file (excluding TASK_TEMPLATE.md) is listed in the manifest.
3. No duplicate entries in the manifest.
4. Each task file's frontmatter `id` matches its filename (without .md).

Exit code 0 on success, 1 on any mismatch.
"""

import re
import sys
from pathlib import Path

import yaml


def main() -> int:
    root = Path(__file__).resolve().parents[1]
    tasks_dir = root / "tasks"
    manifest_path = tasks_dir / "manifest.yaml"

    errors: list[str] = []

    # --- Load manifest ---
    if not manifest_path.exists():
        print(f"ERROR: manifest not found at {manifest_path}")
        return 1

    manifest = yaml.safe_load(manifest_path.read_text(encoding="utf-8"))
    manifest_ids: list[str] = manifest.get("tasks", [])

    # --- Check for duplicates ---
    seen: set[str] = set()
    for task_id in manifest_ids:
        if task_id in seen:
            errors.append(f"Duplicate manifest entry: {task_id}")
        seen.add(task_id)

    # --- Discover .md files ---
    md_files = {
        p.stem: p for p in sorted(tasks_dir.glob("task_*.md")) if p.name != "TASK_TEMPLATE.md"
    }

    # --- Cross-check ---
    manifest_set = set(manifest_ids)
    file_set = set(md_files.keys())

    for task_id in sorted(manifest_set - file_set):
        errors.append(f"In manifest but missing file: {task_id}.md")

    for task_id in sorted(file_set - manifest_set):
        errors.append(f"File exists but missing from manifest: {task_id}.md")

    # --- Frontmatter id check ---
    for stem, path in md_files.items():
        content = path.read_text(encoding="utf-8")
        fm_match = re.match(r"^---\s*\n(.*?)\n---", content, re.DOTALL)
        if not fm_match:
            errors.append(f"{path.name}: no YAML frontmatter found")
            continue
        try:
            fm = yaml.safe_load(fm_match.group(1))
        except yaml.YAMLError:
            errors.append(f"{path.name}: invalid YAML frontmatter")
            continue
        fm_id = fm.get("id", "")
        if fm_id != stem:
            errors.append(f"{path.name}: frontmatter id '{fm_id}' != expected '{stem}'")

    # --- Report ---
    if errors:
        print(f"Manifest lint: {len(errors)} error(s) found\n")
        for err in errors:
            print(f"  - {err}")
        return 1

    print(f"Manifest lint: OK ({len(manifest_ids)} tasks, all in sync)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
