#!/usr/bin/env python3
"""CI lint: reject any plugin wrapper.py that imports from app.*.

This enforces the air-gap rule: plugins must be fully self-contained
and import only from stdlib + their own pip dependencies.
"""
import ast
import sys
from pathlib import Path

PLUGINS_DIR = Path(__file__).resolve().parent.parent / "plugins"
FORBIDDEN_PREFIXES = ("app.", "app ")
# Support grouped layout: plugins/chemistry/my_plugin/, plugins/prometheus/my_plugin/
GROUP_DIRS = ["chemistry", "prometheus"]


def check_file(wrapper_path: Path) -> list[str]:
    """Return list of violations found in a wrapper.py."""
    violations = []
    try:
        tree = ast.parse(wrapper_path.read_text(encoding="utf-8"), filename=str(wrapper_path))
    except SyntaxError as e:
        return [f"{wrapper_path}: SyntaxError: {e}"]

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name.startswith(FORBIDDEN_PREFIXES):
                    violations.append(
                        f"{wrapper_path}:{node.lineno}: forbidden import '{alias.name}' "
                        f"— plugins must not import from app.*"
                    )
        elif isinstance(node, ast.ImportFrom):
            if node.module and node.module.startswith(FORBIDDEN_PREFIXES):
                violations.append(
                    f"{wrapper_path}:{node.lineno}: forbidden import from '{node.module}' "
                    f"— plugins must not import from app.*"
                )
    return violations


def main() -> int:
    if not PLUGINS_DIR.is_dir():
        print(f"Plugins directory not found: {PLUGINS_DIR}")
        return 1

    all_violations: list[str] = []
    scan_dirs = [PLUGINS_DIR]
    for group in GROUP_DIRS:
        group_path = PLUGINS_DIR / group
        if group_path.is_dir():
            scan_dirs.append(group_path)

    for scan_dir in scan_dirs:
        for plugin_dir in sorted(scan_dir.iterdir()):
            if not plugin_dir.is_dir():
                continue
            wrapper = plugin_dir / "wrapper.py"
            if wrapper.exists():
                all_violations.extend(check_file(wrapper))

    if all_violations:
        print("AIR-GAP VIOLATIONS FOUND:")
        for v in all_violations:
            print(f"  {v}")
        return 1

    print(f"All plugin wrappers pass air-gap check ({PLUGINS_DIR})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
