id: task_readme_release_asset_sync
name: Sync README installation instructions with actual release assets
category: coding
grading_type: automated
timeout_seconds: 120
workspace_files:
  - README.md
  - release-assets.json

## Prompt

The workspace contains a README.md and a release-assets.json file.

Update README.md so that its installation instructions match the actual release assets listed in release-assets.json.

Requirements:
- Keep the existing README structure and tone.
- Only edit the installation section.
- Use only filenames that actually exist in release-assets.json.
- Make the instructions explicit for both VS Code and Cursor when applicable.
- Do not invent assets, commands, or package names.
- Do not modify release-assets.json.

## Expected Behavior

The agent should inspect release-assets.json to determine which distributable files actually exist, then update the installation section of README.md so the documented installation flow matches those assets.

## Grading Criteria

- README.md was modified
- release-assets.json was not modified
- Installation section references only assets present in release-assets.json
- No removed/nonexistent asset is still referenced in the installation section
- README structure outside the installation section remains unchanged
- Instructions explicitly cover the available editor targets when supported by the listed assets

## Automated Checks

def grade(transcript: list, workspace_path: str) -> dict:
    from pathlib import Path
    import json
    import re

    workspace = Path(workspace_path)
    readme = workspace / "README.md"
    assets_file = workspace / "release-assets.json"
    original_readme = workspace / "README.original.md"

    scores = {
        "README.md was modified": 0.0,
        "release-assets.json was not modified": 0.0,
        "Installation section references only assets present in release-assets.json": 0.0,
        "No removed/nonexistent asset is still referenced in the installation section": 0.0,
        "README structure outside the installation section remains unchanged": 0.0,
        "Instructions explicitly cover the available editor targets when supported by the listed assets": 0.0,
    }

    if not readme.exists() or not assets_file.exists() or not original_readme.exists():
        return scores

    new_readme = readme.read_text(encoding="utf-8")
    old_readme = original_readme.read_text(encoding="utf-8")
    assets = json.loads(assets_file.read_text(encoding="utf-8"))

    asset_names = set()
    for item in assets:
        if isinstance(item, dict) and "name" in item:
            asset_names.add(item["name"])

    if new_readme != old_readme:
        scores["README.md was modified"] = 1.0

    # release-assets.json unchanged: infer from transcript tool/file writes
    # fallback to existence only if no write detected
    assets_modified = False
    for event in transcript:
        if event.get("type") != "message":
            continue
        msg = event.get("message", {})
        for item in msg.get("content", []):
            if item.get("type") == "toolCall":
                raw = json.dumps(item, ensure_ascii=False)
                if "release-assets.json" in raw:
                    # allow reads, try to detect write/edit intent heuristically
                    if any(token in raw.lower() for token in ["write", "replace", "update", "edit", "create"]):
                        assets_modified = True
    if not assets_modified:
        scores["release-assets.json was not modified"] = 1.0

    def extract_install_section(text: str):
        m = re.search(
            r"(?ims)^(##\s+Installation\b.*?)(?=^##\s+|\Z)",
            text
        )
        return m.group(1) if m else ""

    new_install = extract_install_section(new_readme)
    old_install = extract_install_section(old_readme)

    # collect filenames mentioned in install section
    mentioned_assets = set(re.findall(r"[A-Za-z0-9._-]+\.vsix", new_install))

    if mentioned_assets and all(name in asset_names for name in mentioned_assets):
        scores["Installation section references only assets present in release-assets.json"] = 1.0

    old_assets = set(re.findall(r"[A-Za-z0-9._-]+\.vsix", old_install))
    nonexistent_old_assets = {name for name in old_assets if name not in asset_names}
    if not any(name in new_install for name in nonexistent_old_assets):
        scores["No removed/nonexistent asset is still referenced in the installation section"] = 1.0

    def strip_install_section(text: str):
        return re.sub(r"(?ims)^##\s+Installation\b.*?(?=^##\s+|\Z)", "", text).strip()

    if strip_install_section(new_readme) == strip_install_section(old_readme):
        scores["README structure outside the installation section remains unchanged"] = 1.0

    has_vscode_asset = any("vscode" in name.lower() for name in asset_names)
    has_cursor_asset = any("cursor" in name.lower() for name in asset_names)

    vscode_ok = (not has_vscode_asset) or re.search(r"(?i)\bVS Code\b", new_install)
    cursor_ok = (not has_cursor_asset) or re.search(r"(?i)\bCursor\b", new_install)

    if vscode_ok and cursor_ok:
        scores["Instructions explicitly cover the available editor targets when supported by the listed assets"] = 1.0

    return scores