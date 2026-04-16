#!/usr/bin/env python3
"""
atlas-sdk — Developer toolkit for building .atlas plugins.

Usage
-----
    atlas-sdk init <name>                 Scaffold a new plugin project
    atlas-sdk build [dir] [--encrypt]     Compile a plugin directory into .atlas
    atlas-sdk inspect <file.atlas>        Show manifest and metadata
    atlas-sdk verify <file.atlas>         Verify signature integrity

Environment variables
---------------------
    ATLAS_PLUGIN_KEY    Default encryption passphrase (overridden by --key)

Examples
--------
    # Scaffold a new plugin for a custom DEL-trained ML model
    atlas-sdk init score_del_hits

    # Build it (no encryption — open source)
    atlas-sdk build plugins/score_del_hits

    # Build with IP protection
    atlas-sdk build plugins/score_del_hits --encrypt --key "my-secret-key"

    # Inspect a compiled package
    atlas-sdk inspect score_del_hits.atlas

    # Verify it hasn't been tampered with
    atlas-sdk verify score_del_hits.atlas
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import textwrap
from pathlib import Path

# Ensure the backend package is importable when running from the repo root
_backend_root = Path(__file__).resolve().parent
if str(_backend_root) not in sys.path:
    sys.path.insert(0, str(_backend_root))

from app.atlas_plugin_system.atlas_format import (
    inspect_atlas,
    pack_atlas,
    read_atlas,
    write_atlas,
)
from app.atlas_plugin_system.registry import PluginManifest


# ---------------------------------------------------------------------------
# init — scaffold a new plugin project
# ---------------------------------------------------------------------------

_MANIFEST_TEMPLATE = """\
{{
  "schema_version": "1.0",
  "name": "{name}",
  "version": "0.1.0",
  "description": "TODO: describe what this plugin does.",
  "entry_point": "wrapper.py",
  "priority": 50,
  "tags": [],
  "input_schema": {{
    "type": "object",
    "properties": {{
      "smiles": {{
        "type": "string",
        "description": "SMILES string of the input molecule."
      }}
    }},
    "required": ["smiles"]
  }},
  "output_schema": {{
    "type": "object",
    "properties": {{
      "result": {{"type": "object"}},
      "summary": {{"type": "string"}}
    }}
  }}
}}
"""

_WRAPPER_TEMPLATE = '''\
"""Atlas plugin wrapper for {name}.

This module is compiled into .atlas bytecode by ``atlas-sdk build``.
It must expose one of:
    - PLUGIN   — object with async invoke(arguments, context) -> dict
    - create_plugin()  — factory returning such an object
    - invoke(arguments, context) — standalone async function
"""

from typing import Any, Dict, Optional


class {class_name}:
    """Replace this with your plugin implementation."""

    async def invoke(
        self,
        arguments: Optional[Dict[str, Any]] = None,
        context: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        args = arguments or {{}}
        smiles = args.get("smiles", "")

        # ----- YOUR LOGIC HERE -----
        result = {{"input": smiles, "status": "not_implemented"}}
        # ---------------------------

        return {{
            "result": result,
            "summary": f"{name} processed {{smiles}}",
        }}


# The orchestrator looks for this module-level object.
PLUGIN = {class_name}()
'''


def cmd_init(args: argparse.Namespace) -> None:
    name = args.name
    out_dir = Path(args.output or ".") / name
    if out_dir.exists():
        print(f"Error: directory already exists: {out_dir}", file=sys.stderr)
        sys.exit(1)

    out_dir.mkdir(parents=True)

    class_name = "".join(word.capitalize() for word in name.split("_")) + "Plugin"

    manifest_path = out_dir / "manifest.json"
    manifest_path.write_text(_MANIFEST_TEMPLATE.format(name=name), encoding="utf-8")

    wrapper_path = out_dir / "wrapper.py"
    wrapper_path.write_text(
        _WRAPPER_TEMPLATE.format(name=name, class_name=class_name),
        encoding="utf-8",
    )

    print(f"Scaffolded new Atlas plugin at: {out_dir}/")
    print(f"  manifest.json  — edit description, schemas, tags")
    print(f"  wrapper.py     — implement your logic in {class_name}.invoke()")
    print()
    print("When ready, compile with:")
    print(f"  atlas-sdk build {out_dir}")
    print()
    print("To protect proprietary IP:")
    print(f"  atlas-sdk build {out_dir} --encrypt --key YOUR_SECRET")


# ---------------------------------------------------------------------------
# build — compile to .atlas
# ---------------------------------------------------------------------------

def cmd_build(args: argparse.Namespace) -> None:
    plugin_dir = Path(args.directory or ".")
    manifest_path = plugin_dir / "manifest.json"

    if not manifest_path.exists():
        print(f"Error: no manifest.json found in {plugin_dir}", file=sys.stderr)
        sys.exit(1)

    # Validate manifest
    try:
        manifest_data = json.loads(manifest_path.read_text(encoding="utf-8"))
        PluginManifest.model_validate(manifest_data)
    except Exception as exc:
        print(f"Error: invalid manifest.json: {exc}", file=sys.stderr)
        sys.exit(1)

    # Read wrapper source
    entry_point = manifest_data.get("entry_point", "wrapper.py")
    wrapper_path = plugin_dir / entry_point
    if not wrapper_path.exists():
        print(f"Error: entry point not found: {wrapper_path}", file=sys.stderr)
        sys.exit(1)

    source_code = wrapper_path.read_text(encoding="utf-8")

    # Collect assets (any file that isn't manifest.json or the entry point)
    assets_bytes = _collect_assets(plugin_dir, exclude={manifest_path.name, entry_point})

    # Determine encryption
    passphrase = None
    if args.encrypt:
        passphrase = args.key or os.environ.get("ATLAS_PLUGIN_KEY")
        if not passphrase:
            print(
                "Error: --encrypt requires --key or ATLAS_PLUGIN_KEY env var",
                file=sys.stderr,
            )
            sys.exit(1)

    # Determine output path
    plugin_name = manifest_data["name"]
    output_path = Path(args.output or f"{plugin_name}.atlas")

    # Build
    write_atlas(
        output_path,
        manifest_data,
        source_code,
        assets_bytes=assets_bytes,
        passphrase=passphrase,
    )

    size = output_path.stat().st_size
    enc_label = " (encrypted)" if passphrase else ""
    print(f"Built: {output_path} ({size:,} bytes){enc_label}")
    print(f"  Plugin:  {plugin_name} v{manifest_data.get('version', '?')}")
    print(f"  Tags:    {', '.join(manifest_data.get('tags', []))}")

    if passphrase:
        print()
        print("  WARNING: Keep your encryption key safe.")
        print("  The orchestrator needs ATLAS_PLUGIN_KEY set to load this plugin.")


def _collect_assets(plugin_dir: Path, exclude: set) -> bytes:
    """Zip any extra files in the plugin directory into a bytes bundle."""
    import io
    import zipfile

    asset_files = [
        f for f in plugin_dir.rglob("*")
        if f.is_file()
        and f.name not in exclude
        and not f.name.startswith(".")
        and f.suffix not in {".pyc", ".pyo"}
    ]

    if not asset_files:
        return b""

    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        for asset in asset_files:
            arcname = str(asset.relative_to(plugin_dir))
            zf.write(asset, arcname)
    return buf.getvalue()


# ---------------------------------------------------------------------------
# inspect — show manifest
# ---------------------------------------------------------------------------

def cmd_inspect(args: argparse.Namespace) -> None:
    file_path = Path(args.file)
    if not file_path.exists():
        print(f"Error: file not found: {file_path}", file=sys.stderr)
        sys.exit(1)

    info = inspect_atlas(file_path)
    manifest = info["manifest"]

    print(f"Atlas Plugin Package: {file_path}")
    print(f"  File size:   {info['file_size']:,} bytes")
    print(f"  Encrypted:   {'yes' if info['encrypted'] else 'no'}")
    print(f"  Has assets:  {'yes' if info['has_assets'] else 'no'}")
    print()
    print(f"  Name:        {manifest.get('name', '?')}")
    print(f"  Version:     {manifest.get('version', '?')}")
    print(f"  Description: {manifest.get('description', '?')}")
    print(f"  Priority:    {manifest.get('priority', 50)}")
    print(f"  Tags:        {', '.join(manifest.get('tags', []))}")
    print()

    if args.json:
        print(json.dumps(info, indent=2, ensure_ascii=False))


# ---------------------------------------------------------------------------
# verify — check signature
# ---------------------------------------------------------------------------

def cmd_verify(args: argparse.Namespace) -> None:
    file_path = Path(args.file)
    if not file_path.exists():
        print(f"Error: file not found: {file_path}", file=sys.stderr)
        sys.exit(1)

    try:
        read_atlas(file_path, verify_signature=True, manifest_only=True)
        print(f"PASS: {file_path} — signature is valid")
    except ValueError as exc:
        print(f"FAIL: {file_path} — {exc}", file=sys.stderr)
        sys.exit(1)


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(
        prog="atlas-sdk",
        description="Developer toolkit for building and managing .atlas plugin packages.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=textwrap.dedent("""\
            Examples:
              atlas-sdk init my_plugin
              atlas-sdk build plugins/my_plugin --encrypt --key SECRET
              atlas-sdk inspect my_plugin.atlas
              atlas-sdk verify my_plugin.atlas
        """),
    )

    subparsers = parser.add_subparsers(dest="command", required=True)

    # init
    p_init = subparsers.add_parser("init", help="Scaffold a new plugin project")
    p_init.add_argument("name", help="Plugin name (snake_case)")
    p_init.add_argument("-o", "--output", help="Parent directory (default: current dir)")
    p_init.set_defaults(func=cmd_init)

    # build
    p_build = subparsers.add_parser("build", help="Compile plugin directory to .atlas")
    p_build.add_argument("directory", nargs="?", default=".", help="Plugin directory (default: .)")
    p_build.add_argument("-o", "--output", help="Output .atlas file path")
    p_build.add_argument("--encrypt", action="store_true", help="Encrypt code with AES-256-GCM")
    p_build.add_argument("--key", help="Encryption passphrase (or set ATLAS_PLUGIN_KEY)")
    p_build.set_defaults(func=cmd_build)

    # inspect
    p_inspect = subparsers.add_parser("inspect", help="Show .atlas manifest and metadata")
    p_inspect.add_argument("file", help="Path to .atlas file")
    p_inspect.add_argument("--json", action="store_true", help="Output raw JSON")
    p_inspect.set_defaults(func=cmd_inspect)

    # verify
    p_verify = subparsers.add_parser("verify", help="Verify .atlas signature integrity")
    p_verify.add_argument("file", help="Path to .atlas file")
    p_verify.set_defaults(func=cmd_verify)

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
