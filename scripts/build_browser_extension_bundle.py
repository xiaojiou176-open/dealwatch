#!/usr/bin/env python3
from __future__ import annotations

import json
import shutil
import zipfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
EXTENSION_ROOT = ROOT / "browser-extension"
DIST_ROOT = ROOT / "dist" / "browser-extension"


def main() -> int:
    manifest = json.loads((EXTENSION_ROOT / "manifest.json").read_text(encoding="utf-8"))
    version = manifest["version"]
    bundle_dir = DIST_ROOT / f"dealwatch-companion-{version}"
    archive_path = DIST_ROOT / f"dealwatch-companion-{version}.zip"

    if bundle_dir.exists():
        shutil.rmtree(bundle_dir)
    bundle_dir.mkdir(parents=True, exist_ok=True)

    for child in EXTENSION_ROOT.iterdir():
        if child.name.startswith("."):
            continue
        destination = bundle_dir / child.name
        if child.is_dir():
            shutil.copytree(child, destination, dirs_exist_ok=True)
        else:
            shutil.copy2(child, destination)

    if archive_path.exists():
        archive_path.unlink()

    with zipfile.ZipFile(archive_path, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        for path in sorted(bundle_dir.rglob("*")):
            if path.is_file():
                zf.write(path, path.relative_to(bundle_dir))

    print(f"browser_extension_bundle={archive_path.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
