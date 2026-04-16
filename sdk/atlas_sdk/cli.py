#!/usr/bin/env python3
"""
atlas-sdk CLI — Developer toolkit for building .atlas plugins.

Usage:
    atlas-sdk init <name>                 Scaffold a new plugin project
    atlas-sdk build [dir] [--encrypt]     Compile a plugin directory into .atlas
    atlas-sdk inspect <file.atlas>        Show manifest and metadata
    atlas-sdk verify <file.atlas>         Verify signature integrity
"""

from __future__ import annotations

import argparse
import io
import json
import os
import sys
import textwrap
import zipfile
from pathlib import Path

from atlas_sdk.format import inspect_atlas, read_atlas, write_atlas
from atlas_sdk.manifest import PluginManifest
from atlas_sdk.templates import SUPPORTED_RUNTIMES, get_manifest, get_wrapper


# ---------------------------------------------------------------------------
# init
# ---------------------------------------------------------------------------

def cmd_init(args: argparse.Namespace) -> None:
    name = args.name
    runtime = args.runtime or "python"
    if runtime not in SUPPORTED_RUNTIMES:
        print(f"Error: unknown runtime '{runtime}'. Choose from: {', '.join(SUPPORTED_RUNTIMES)}", file=sys.stderr)
        sys.exit(1)

    out_dir = Path(args.output or ".") / name
    if out_dir.exists():
        print(f"Error: directory already exists: {out_dir}", file=sys.stderr)
        sys.exit(1)

    out_dir.mkdir(parents=True)

    (out_dir / "manifest.json").write_text(get_manifest(name, runtime), encoding="utf-8")
    (out_dir / "wrapper.py").write_text(get_wrapper(name, runtime), encoding="utf-8")

    class_name = "".join(word.capitalize() for word in name.split("_")) + "Plugin"
    print(f"Scaffolded new Atlas plugin at: {out_dir}/")
    print(f"  Runtime:       {runtime}")
    print(f"  manifest.json  — edit description, schemas, tags")
    print(f"  wrapper.py     — implement your logic in {class_name}.invoke()")

    if runtime == "gguf":
        print()
        print("  Next: place your .gguf model file in this directory.")
        print("  The wrapper will find it via __atlas_assets__ at runtime.")
    elif runtime == "onnx":
        print()
        print("  Next: place your .onnx model file in this directory.")
    elif runtime == "native":
        print()
        print("  Next: place your compiled .dll / .so / .dylib in this directory.")
        print("  Edit wrapper.py to configure ctypes function signatures.")

    print()
    print("When ready, compile with:")
    print(f"  atlas-sdk build {out_dir}")
    print()
    print("To protect proprietary IP:")
    print(f"  atlas-sdk build {out_dir} --encrypt --key YOUR_SECRET")


# ---------------------------------------------------------------------------
# build
# ---------------------------------------------------------------------------

def cmd_build(args: argparse.Namespace) -> None:
    plugin_dir = Path(args.directory or ".")
    manifest_path = plugin_dir / "manifest.json"

    if not manifest_path.exists():
        print(f"Error: no manifest.json found in {plugin_dir}", file=sys.stderr)
        sys.exit(1)

    try:
        manifest_data = json.loads(manifest_path.read_text(encoding="utf-8"))
        PluginManifest.model_validate(manifest_data)
    except Exception as exc:
        print(f"Error: invalid manifest.json: {exc}", file=sys.stderr)
        sys.exit(1)

    entry_point = manifest_data.get("entry_point", "wrapper.py")
    wrapper_path = plugin_dir / entry_point
    if not wrapper_path.exists():
        print(f"Error: entry point not found: {wrapper_path}", file=sys.stderr)
        sys.exit(1)

    source_code = wrapper_path.read_text(encoding="utf-8")
    assets_bytes = _collect_assets(plugin_dir, exclude={manifest_path.name, entry_point})

    passphrase = None
    if args.encrypt:
        passphrase = args.key or os.environ.get("ATLAS_PLUGIN_KEY")
        if not passphrase:
            print("Error: --encrypt requires --key or ATLAS_PLUGIN_KEY env var", file=sys.stderr)
            sys.exit(1)

    plugin_name = manifest_data["name"]
    output_path = Path(args.output or f"{plugin_name}.atlas")

    write_atlas(output_path, manifest_data, source_code,
                assets_bytes=assets_bytes, passphrase=passphrase)

    size = output_path.stat().st_size
    enc_label = " (encrypted)" if passphrase else ""
    print(f"Built: {output_path} ({size:,} bytes){enc_label}")
    print(f"  Plugin:  {plugin_name} v{manifest_data.get('version', '?')}")
    print(f"  Tags:    {', '.join(manifest_data.get('tags', []))}")

    if passphrase:
        print()
        print("  The orchestrator needs ATLAS_PLUGIN_KEY set to load this plugin.")


def _collect_assets(plugin_dir: Path, exclude: set) -> bytes:
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
            zf.write(asset, str(asset.relative_to(plugin_dir)))
    return buf.getvalue()


# ---------------------------------------------------------------------------
# inspect
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
    print(f"  Runtime:     {manifest.get('runtime', 'python')}")
    print(f"  Description: {manifest.get('description', '?')}")
    print(f"  Priority:    {manifest.get('priority', 50)}")
    print(f"  Tags:        {', '.join(manifest.get('tags', []))}")

    if args.json:
        print()
        print(json.dumps(info, indent=2, ensure_ascii=False))


# ---------------------------------------------------------------------------
# verify
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
# Entry point
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(
        prog="atlas-sdk",
        description="Developer toolkit for building .atlas plugin packages for the Atlas Framework.",
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

    p_init = subparsers.add_parser("init", help="Scaffold a new plugin project")
    p_init.add_argument("name", help="Plugin name (snake_case)")
    p_init.add_argument("-o", "--output", help="Parent directory (default: current dir)")
    p_init.add_argument(
        "-r", "--runtime",
        choices=SUPPORTED_RUNTIMES,
        default="python",
        help="Runtime type: python (default), gguf, onnx, native, generic",
    )
    p_init.set_defaults(func=cmd_init)

    p_build = subparsers.add_parser("build", help="Compile plugin directory to .atlas")
    p_build.add_argument("directory", nargs="?", default=".", help="Plugin directory")
    p_build.add_argument("-o", "--output", help="Output .atlas file path")
    p_build.add_argument("--encrypt", action="store_true", help="Encrypt code with AES-256-GCM")
    p_build.add_argument("--key", help="Encryption passphrase (or set ATLAS_PLUGIN_KEY)")
    p_build.set_defaults(func=cmd_build)

    p_inspect = subparsers.add_parser("inspect", help="Show .atlas manifest and metadata")
    p_inspect.add_argument("file", help="Path to .atlas file")
    p_inspect.add_argument("--json", action="store_true", help="Output raw JSON")
    p_inspect.set_defaults(func=cmd_inspect)

    p_verify = subparsers.add_parser("verify", help="Verify .atlas signature integrity")
    p_verify.add_argument("file", help="Path to .atlas file")
    p_verify.set_defaults(func=cmd_verify)

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
