#!/usr/bin/env python3
"""Compile all plugin directories into .atlas binary packages.

Scans plugins/ (including chemistry/ and prometheus/ group folders),
reads each plugin's manifest.json + wrapper.py, and writes a .atlas
binary alongside the source directory.

Usage:
    python scripts/compile_plugins.py [--encrypt]
"""
import json
import sys
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND_DIR))

from app.atlas_plugin_system.atlas_format import write_atlas  # noqa: E402


def discover_plugins(plugins_dir: Path):
    """Yield (plugin_dir, group_dir) for every plugin with manifest.json."""
    for item in sorted(plugins_dir.iterdir()):
        if not item.is_dir() or item.name.startswith("."):
            continue
        manifest = item / "manifest.json"
        if manifest.exists():
            yield item, plugins_dir
        else:
            # Group folder (chemistry/, prometheus/)
            for sub in sorted(item.iterdir()):
                if sub.is_dir() and (sub / "manifest.json").exists():
                    yield sub, item


def compile_plugin(plugin_dir: Path, output_dir: Path, passphrase=None):
    """Compile a single plugin directory into a .atlas file."""
    manifest_path = plugin_dir / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))

    entry_point = manifest.get("entry_point", "wrapper.py")
    wrapper_path = plugin_dir / entry_point
    if not wrapper_path.exists():
        print(f"  SKIP {plugin_dir.name}: {entry_point} not found")
        return None

    source_code = wrapper_path.read_text(encoding="utf-8")

    # Collect assets if any are declared in manifest
    assets_bytes = b""
    declared_artifacts = manifest.get("artifacts", [])
    if declared_artifacts:
        import io
        import zipfile
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
            for artifact_name in declared_artifacts:
                artifact_path = plugin_dir / artifact_name
                if artifact_path.exists():
                    zf.write(artifact_path, artifact_name)
                    print(f"    + asset: {artifact_name}")
        assets_bytes = buf.getvalue()

    output_path = output_dir / f"{manifest['name']}.atlas"
    write_atlas(
        output_path,
        manifest,
        source_code,
        assets_bytes=assets_bytes,
        passphrase=passphrase,
    )
    return output_path


def main():
    passphrase = None
    if "--encrypt" in sys.argv:
        import os
        passphrase = os.environ.get("ATLAS_PLUGIN_KEY")
        if not passphrase:
            print("ERROR: --encrypt requires ATLAS_PLUGIN_KEY env var")
            return 1

    plugins_dir = BACKEND_DIR / "plugins"
    if not plugins_dir.is_dir():
        print(f"Plugins directory not found: {plugins_dir}")
        return 1

    compiled = 0
    errors = 0

    for plugin_dir, group_dir in discover_plugins(plugins_dir):
        group_name = group_dir.name if group_dir != plugins_dir else ""
        label = f"{group_name}/{plugin_dir.name}" if group_name else plugin_dir.name
        print(f"Compiling {label}...")

        try:
            result = compile_plugin(plugin_dir, group_dir, passphrase)
            if result:
                size_kb = result.stat().st_size / 1024
                print(f"  -> {result.name} ({size_kb:.1f} KB)")
                compiled += 1
        except Exception as e:
            print(f"  ERROR: {e}")
            errors += 1

    print(f"\nDone: {compiled} compiled, {errors} errors")
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
