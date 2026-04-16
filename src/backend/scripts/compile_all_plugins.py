#!/usr/bin/env python3
"""Batch-compile all directory plugins into .atlas packages.

Usage:
    python scripts/compile_all_plugins.py [--encrypt --key SECRET] [--output-dir DIR]

Reads every plugin directory under src/backend/plugins/, compiles each to
a .atlas binary, and writes them to the output directory (default: same
plugins/ folder so the registry picks them up automatically).
"""

from __future__ import annotations

import argparse
import io
import json
import os
import sys
import zipfile
from pathlib import Path

_backend_root = Path(__file__).resolve().parent.parent
if str(_backend_root) not in sys.path:
    sys.path.insert(0, str(_backend_root))

from app.atlas_plugin_system.atlas_format import write_atlas
from app.atlas_plugin_system.registry import PluginManifest


def _iter_plugin_dirs(root: Path) -> list[Path]:
    """Yield plugin directories from flat or one-level grouped layouts."""
    discovered: list[Path] = []
    for candidate in sorted(root.iterdir(), key=lambda item: item.name.lower()):
        if candidate.name.startswith(".") or not candidate.is_dir():
            continue
        manifest_path = candidate / "manifest.json"
        if manifest_path.exists():
            discovered.append(candidate)
            continue
        for sub in sorted(candidate.iterdir(), key=lambda item: item.name.lower()):
            if sub.name.startswith(".") or not sub.is_dir():
                continue
            if (sub / "manifest.json").exists():
                discovered.append(sub)
    return discovered


def _build_assets_bundle(plugin_dir: Path, manifest: dict) -> bytes:
    """Zip optional plugin assets declared in the manifest or assets/ folder."""
    asset_entries: list[tuple[Path, str]] = []
    seen_arc_names: set[str] = set()

    def _add_file(file_path: Path, arc_name: str) -> None:
        if not file_path.is_file():
            return
        normalized = arc_name.replace("\\", "/")
        if normalized in seen_arc_names:
            return
        seen_arc_names.add(normalized)
        asset_entries.append((file_path, normalized))

    for relative in manifest.get("artifacts", []):
        artifact_path = (plugin_dir / relative).resolve()
        if artifact_path.is_file():
            _add_file(artifact_path, str(Path(relative)))
        elif artifact_path.is_dir():
            for nested in sorted(artifact_path.rglob("*")):
                if nested.is_file():
                    _add_file(nested, str(Path(relative) / nested.relative_to(artifact_path)))

    assets_dir = plugin_dir / "assets"
    if assets_dir.is_dir():
        for nested in sorted(assets_dir.rglob("*")):
            if nested.is_file():
                _add_file(nested, str(Path("assets") / nested.relative_to(assets_dir)))

    if not asset_entries:
        return b""

    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, mode="w", compression=zipfile.ZIP_DEFLATED) as archive:
        for file_path, arc_name in asset_entries:
            archive.write(file_path, arc_name)
    return buffer.getvalue()


def main() -> None:
    parser = argparse.ArgumentParser(description="Compile all plugins to .atlas format")
    parser.add_argument("--plugins-dir", default=str(_backend_root / "plugins"))
    parser.add_argument("--output-dir", default=None, help="Output directory (default: plugins dir)")
    parser.add_argument("--encrypt", action="store_true")
    parser.add_argument("--key", default=None)
    args = parser.parse_args()

    plugins_dir = Path(args.plugins_dir)
    output_dir = Path(args.output_dir) if args.output_dir else plugins_dir
    output_dir.mkdir(parents=True, exist_ok=True)

    passphrase = None
    if args.encrypt:
        passphrase = args.key or os.environ.get("ATLAS_PLUGIN_KEY")
        if not passphrase:
            print("Error: --encrypt requires --key or ATLAS_PLUGIN_KEY", file=sys.stderr)
            sys.exit(1)

    compiled = 0
    for candidate in _iter_plugin_dirs(plugins_dir):
        manifest_path = candidate / "manifest.json"

        try:
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            PluginManifest.model_validate(manifest)
        except Exception as exc:
            print(f"  SKIP {candidate.name}: invalid manifest ({exc})")
            continue

        entry_point = manifest.get("entry_point", "wrapper.py")
        wrapper_path = candidate / entry_point
        if not wrapper_path.exists():
            print(f"  SKIP {candidate.name}: missing {entry_point}")
            continue

        source = wrapper_path.read_text(encoding="utf-8")
        assets_bytes = _build_assets_bundle(candidate, manifest)
        out_path = output_dir / f"{manifest['name']}.atlas"

        write_atlas(
            out_path,
            manifest,
            source,
            assets_bytes=assets_bytes,
            passphrase=passphrase,
        )
        size = out_path.stat().st_size
        enc = " (encrypted)" if passphrase else ""
        assets_note = f", assets={len(assets_bytes):,} bytes" if assets_bytes else ""
        print(f"  OK   {manifest['name']}.atlas ({size:,} bytes{assets_note}){enc}")
        compiled += 1

    print(f"\nCompiled {compiled} plugin(s) to {output_dir}")


if __name__ == "__main__":
    main()
