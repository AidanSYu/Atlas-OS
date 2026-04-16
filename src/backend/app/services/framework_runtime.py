"""Generic runtime preflight and proof helpers for Atlas Framework plugins."""

from __future__ import annotations

import asyncio
import ctypes
import importlib.util
import os
import platform
import sys
import time
from typing import Any, Dict, List, Optional, Tuple

from app.atlas_plugin_system import get_tool_catalog

IMPORT_NAME_OVERRIDES = {
    "chronos-forecasting": "chronos",
    "neuraloperator": "neuralop",
    "qwen-vl-utils": "qwen_vl_utils",
}


def _resolve_import_name(package: str) -> str:
    return IMPORT_NAME_OVERRIDES.get(package, package.replace("-", "_"))


def _supports_self_test(plugin: Dict[str, Any]) -> bool:
    input_schema = plugin.get("input_schema") or {}
    if not isinstance(input_schema, dict):
        return bool(plugin.get("self_test"))
    properties = input_schema.get("properties") or {}
    if not isinstance(properties, dict):
        return bool(plugin.get("self_test"))
    mode_schema = properties.get("mode") or {}
    if not isinstance(mode_schema, dict):
        return bool(plugin.get("self_test"))
    mode_enum = mode_schema.get("enum") or []
    return "self_test" in mode_enum or bool(plugin.get("self_test"))


def _default_proof_arguments(plugin: Dict[str, Any]) -> Dict[str, Any]:
    return {"mode": "self_test"} if _supports_self_test(plugin) else {}


def _dependency_statuses(plugin: Dict[str, Any]) -> List[Dict[str, Any]]:
    statuses: List[Dict[str, Any]] = []
    for package in plugin.get("optional_dependencies", []):
        import_name = _resolve_import_name(package)
        statuses.append(
            {
                "package": package,
                "import_name": import_name,
                "available": importlib.util.find_spec(import_name) is not None,
            }
        )
    return statuses


def _memory_snapshot_mb() -> Tuple[int, int]:
    if sys.platform == "win32":
        class MEMORYSTATUSEX(ctypes.Structure):
            _fields_ = [
                ("dwLength", ctypes.c_ulong),
                ("dwMemoryLoad", ctypes.c_ulong),
                ("ullTotalPhys", ctypes.c_ulonglong),
                ("ullAvailPhys", ctypes.c_ulonglong),
                ("ullTotalPageFile", ctypes.c_ulonglong),
                ("ullAvailPageFile", ctypes.c_ulonglong),
                ("ullTotalVirtual", ctypes.c_ulonglong),
                ("ullAvailVirtual", ctypes.c_ulonglong),
                ("ullAvailExtendedVirtual", ctypes.c_ulonglong),
            ]

        status = MEMORYSTATUSEX()
        status.dwLength = ctypes.sizeof(MEMORYSTATUSEX)
        if ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(status)):
            total_mb = int(status.ullTotalPhys / (1024 * 1024))
            available_mb = int(status.ullAvailPhys / (1024 * 1024))
            return total_mb, available_mb
        return 0, 0

    if hasattr(os, "sysconf"):
        try:
            page_size = os.sysconf("SC_PAGE_SIZE")
            total_pages = os.sysconf("SC_PHYS_PAGES")
            available_pages = os.sysconf("SC_AVPHYS_PAGES")
        except (ValueError, OSError):
            return 0, 0
        total_mb = int((page_size * total_pages) / (1024 * 1024))
        available_mb = int((page_size * available_pages) / (1024 * 1024))
        return total_mb, available_mb

    return 0, 0


def _gpu_snapshot() -> Dict[str, Any]:
    if importlib.util.find_spec("torch") is None:
        return {
            "torch_available": False,
            "cuda_available": False,
            "gpu_devices": [],
        }

    try:
        import torch
    except Exception:
        return {
            "torch_available": True,
            "cuda_available": False,
            "gpu_devices": [],
        }

    if not torch.cuda.is_available():
        return {
            "torch_available": True,
            "cuda_available": False,
            "gpu_devices": [],
        }

    gpu_devices: List[Dict[str, Any]] = []
    for index in range(torch.cuda.device_count()):
        props = torch.cuda.get_device_properties(index)
        gpu_devices.append(
            {
                "index": index,
                "name": props.name,
                "total_vram_mb": int(props.total_memory / (1024 * 1024)),
            }
        )

    return {
        "torch_available": True,
        "cuda_available": True,
        "gpu_devices": gpu_devices,
    }


def get_machine_profile() -> Dict[str, Any]:
    total_ram_mb, available_ram_mb = _memory_snapshot_mb()
    gpu_info = _gpu_snapshot()
    return {
        "platform": platform.platform(),
        "python_version": platform.python_version(),
        "cpu_count": os.cpu_count() or 0,
        "total_ram_mb": total_ram_mb,
        "available_ram_mb": available_ram_mb,
        **gpu_info,
    }


def _assess_resources(plugin: Dict[str, Any], machine: Dict[str, Any]) -> Dict[str, Any]:
    requirements = plugin.get("resource_requirements") or {}
    blockers: List[str] = []
    advisories: List[str] = []

    min_ram_mb = int(requirements.get("min_ram_mb") or 0)
    min_vram_mb = int(requirements.get("min_vram_mb") or 0)
    recommended_vram_mb = int(requirements.get("recommended_vram_mb") or 0)
    gpu_required = bool(requirements.get("gpu_required"))

    total_ram_mb = int(machine.get("total_ram_mb") or 0)
    available_ram_mb = int(machine.get("available_ram_mb") or 0)
    gpu_devices = machine.get("gpu_devices") or []
    max_vram_mb = max((int(device.get("total_vram_mb") or 0) for device in gpu_devices), default=0)
    cuda_available = bool(machine.get("cuda_available"))

    if min_ram_mb and total_ram_mb and total_ram_mb < min_ram_mb:
        blockers.append(
            f"Machine RAM is {total_ram_mb} MB, below the plugin minimum of {min_ram_mb} MB."
        )
    elif min_ram_mb and available_ram_mb and available_ram_mb < min_ram_mb:
        advisories.append(
            f"Available RAM is {available_ram_mb} MB, below the plugin minimum target of {min_ram_mb} MB."
        )

    if gpu_required and not cuda_available:
        blockers.append("This plugin requires CUDA-capable GPU support, but no CUDA device is available.")
    elif gpu_required and min_vram_mb and max_vram_mb and max_vram_mb < min_vram_mb:
        blockers.append(
            f"Detected GPU VRAM is {max_vram_mb} MB, below the plugin minimum of {min_vram_mb} MB."
        )
    elif min_vram_mb and cuda_available and max_vram_mb and max_vram_mb < min_vram_mb:
        advisories.append(
            f"Detected GPU VRAM is {max_vram_mb} MB, below the plugin minimum target of {min_vram_mb} MB."
        )

    if recommended_vram_mb and cuda_available and max_vram_mb and max_vram_mb < recommended_vram_mb:
        advisories.append(
            f"Detected GPU VRAM is {max_vram_mb} MB, below the recommended {recommended_vram_mb} MB."
        )

    if not blockers and not advisories:
        status = "ok"
    elif blockers:
        status = "blocked"
    else:
        status = "advisory"

    return {
        "status": status,
        "blockers": blockers,
        "advisories": advisories,
    }


def build_plugin_runtime_snapshot(plugin: Dict[str, Any], machine: Dict[str, Any]) -> Dict[str, Any]:
    dependency_statuses = _dependency_statuses(plugin)
    missing_dependencies = [
        item["package"]
        for item in dependency_statuses
        if not item["available"]
    ]
    resource_assessment = _assess_resources(plugin, machine)

    blocking_issues: List[str] = []
    advisory_notes: List[str] = []
    if plugin.get("load_error"):
        blocking_issues.append(f"Plugin failed to load: {plugin['load_error']}")
    blocking_issues.extend(resource_assessment["blockers"])
    if missing_dependencies:
        advisory_notes.append(
            "Missing optional/runtime dependencies detected: " + ", ".join(missing_dependencies) + "."
        )
    advisory_notes.extend(resource_assessment["advisories"])

    if plugin.get("load_error") or resource_assessment["status"] == "blocked":
        preflight_status = "blocked"
    elif missing_dependencies:
        preflight_status = "attention"
    else:
        preflight_status = "unverified"

    return {
        "name": plugin["name"],
        "description": plugin["description"],
        "source": plugin["source"],
        "source_type": plugin["source_type"],
        "license": plugin.get("license") or "",
        "loaded": plugin.get("loaded", False),
        "load_error": plugin.get("load_error"),
        "preflight_status": preflight_status,
        "blocking_issues": blocking_issues,
        "advisory_notes": advisory_notes,
        "dependency_statuses": dependency_statuses,
        "missing_dependencies": missing_dependencies,
        "supports_self_test": _supports_self_test(plugin),
        "default_proof_arguments": _default_proof_arguments(plugin),
        "resource_assessment": resource_assessment,
    }


def build_framework_runtime_snapshot() -> Dict[str, Any]:
    catalog = get_tool_catalog()
    catalog.refresh()
    machine = get_machine_profile()
    plugins = [
        build_plugin_runtime_snapshot(plugin, machine)
        for plugin in catalog.list_plugins()
    ]
    return {
        "status": "ok",
        "machine": machine,
        "plugins": plugins,
    }


async def run_plugin_proof(
    plugin_name: str,
    arguments: Optional[Dict[str, Any]] = None,
    timeout_seconds: float = 120.0,
) -> Dict[str, Any]:
    runtime_snapshot = build_framework_runtime_snapshot()
    plugin_runtime = next(
        (item for item in runtime_snapshot["plugins"] if item["name"] == plugin_name),
        None,
    )
    if plugin_runtime is None:
        raise ValueError(f"Unknown Atlas Framework plugin: {plugin_name}")

    if plugin_runtime["load_error"]:
        return {
            "plugin_name": plugin_name,
            "proof_status": "blocked",
            "duration_ms": 0,
            "summary": plugin_runtime["blocking_issues"][0],
            "arguments": arguments or plugin_runtime["default_proof_arguments"],
            "runtime": plugin_runtime,
            "result": {"valid": False, "error": plugin_runtime["blocking_issues"][0]},
        }

    proof_arguments = dict(arguments or plugin_runtime["default_proof_arguments"])
    if not proof_arguments:
        return {
            "plugin_name": plugin_name,
            "proof_status": "unsupported",
            "duration_ms": 0,
            "summary": f"{plugin_name} does not expose a generic self-test invocation.",
            "arguments": {},
            "runtime": plugin_runtime,
            "result": {"valid": False, "error": "No generic self-test invocation is available for this plugin."},
        }

    catalog = get_tool_catalog()
    catalog.refresh()
    started = time.perf_counter()
    try:
        result = await asyncio.wait_for(
            catalog.invoke(
                plugin_name,
                proof_arguments,
                context={"proof_mode": True},
            ),
            timeout=timeout_seconds,
        )
    except asyncio.TimeoutError:
        duration_ms = int((time.perf_counter() - started) * 1000)
        return {
            "plugin_name": plugin_name,
            "proof_status": "failed",
            "duration_ms": duration_ms,
            "summary": f"{plugin_name} proof timed out after {timeout_seconds:.1f}s.",
            "arguments": proof_arguments,
            "runtime": plugin_runtime,
            "result": {"valid": False, "error": f"Timed out after {timeout_seconds:.1f}s."},
        }

    duration_ms = int((time.perf_counter() - started) * 1000)
    valid = result.get("valid", "error" not in result)
    proof_status = "passed" if valid and not result.get("error") else "failed"
    summary = result.get("summary") or result.get("error") or "Proof run completed."
    return {
        "plugin_name": plugin_name,
        "proof_status": proof_status,
        "duration_ms": duration_ms,
        "summary": summary,
        "arguments": proof_arguments,
        "runtime": plugin_runtime,
        "result": result,
    }
