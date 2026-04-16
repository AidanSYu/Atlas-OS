"""Emit a machine-aware Atlas Framework runtime audit report."""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from pathlib import Path
from typing import Any, Dict, List

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.services.framework_runtime import build_framework_runtime_snapshot, run_plugin_proof


async def _collect_report(
    plugin_names: List[str],
    run_proofs: bool,
    timeout_seconds: float,
) -> Dict[str, Any]:
    snapshot = build_framework_runtime_snapshot()
    report: Dict[str, Any] = {
        "runtime": snapshot,
        "proofs": [],
    }
    if not run_proofs:
        return report

    available_names = {plugin["name"] for plugin in snapshot["plugins"]}
    targets = plugin_names or sorted(available_names)
    proofs: List[Dict[str, Any]] = []
    for plugin_name in targets:
        if plugin_name not in available_names:
            proofs.append(
                {
                    "plugin_name": plugin_name,
                    "proof_status": "unknown",
                    "summary": f"Plugin '{plugin_name}' was not found in the current catalog.",
                }
            )
            continue
        proofs.append(
            await run_plugin_proof(
                plugin_name,
                timeout_seconds=timeout_seconds,
            )
        )
    report["proofs"] = proofs
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description="Atlas Framework runtime audit")
    parser.add_argument(
        "--run-proofs",
        action="store_true",
        help="Run each plugin's generic self-test/proof path when available.",
    )
    parser.add_argument(
        "--plugin",
        action="append",
        default=[],
        help="Restrict proof runs to one or more plugin names.",
    )
    parser.add_argument(
        "--timeout-seconds",
        type=float,
        default=120.0,
        help="Per-plugin timeout for proof runs.",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=None,
        help="Optional path to write the JSON audit report.",
    )
    args = parser.parse_args()

    report = asyncio.run(
        _collect_report(
            plugin_names=list(args.plugin),
            run_proofs=bool(args.run_proofs),
            timeout_seconds=float(args.timeout_seconds),
        )
    )
    rendered = json.dumps(report, indent=2)
    if args.output is not None:
        args.output.write_text(rendered, encoding="utf-8")
    else:
        print(rendered)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
