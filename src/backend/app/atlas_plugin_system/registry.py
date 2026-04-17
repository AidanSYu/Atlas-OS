"""Filesystem-backed plugin registry for the Atlas Framework."""

from __future__ import annotations

import json
import logging
import os
import types
import zipfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field

from app.core.config import settings

logger = logging.getLogger(__name__)


class ResourceRequirements(BaseModel):
    """Hardware requirements for a plugin."""

    min_vram_mb: int = 0
    min_ram_mb: int = 0
    gpu_required: bool = False
    recommended_vram_mb: int = 0
    # When true, the orchestrator evicts itself from GPU before dispatching
    # this tool so the plugin has exclusive VRAM. Reserve for heavy workloads
    # (training, large VLM inference) — reloading Nemotron costs ~10-15s.
    exclusive_gpu: bool = False


class PluginManifest(BaseModel):
    """Validated plugin manifest loaded from manifest.json."""

    schema_version: str = "1.0"
    name: str
    version: str = "0.1.0"
    description: str
    entry_point: str = "wrapper.py"
    input_schema: Dict[str, Any] = Field(default_factory=dict)
    output_schema: Dict[str, Any] = Field(default_factory=dict)
    priority: int = 50
    tags: List[str] = Field(default_factory=list)
    runtime: str = "python"  # python | gguf | onnx | native | generic
    license: str = ""  # e.g. "Apache-2.0", "GPL-3.0"
    optional_dependencies: List[str] = Field(default_factory=list)
    artifacts: List[str] = Field(default_factory=list)  # embedded asset filenames
    resource_requirements: ResourceRequirements = Field(default_factory=ResourceRequirements)
    self_test: str = ""  # shell command to validate the plugin is working
    fallback_used: str = ""  # describes what capability is lost without optional deps


@dataclass
class RegisteredPlugin:
    """Runtime plugin record."""

    manifest: PluginManifest
    source_path: Path
    wrapper_reference: str
    wrapper_instance: Any = None
    load_error: Optional[str] = None
    source_type: str = "directory"


class _FunctionWrapper:
    """Normalize module-level invoke() functions into the wrapper protocol."""

    def __init__(self, fn: Any):
        self._fn = fn

    async def invoke(
        self,
        arguments: Optional[Dict[str, Any]] = None,
        context: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        result = self._fn(arguments or {}, context or {})
        if hasattr(result, "__await__"):
            result = await result
        if isinstance(result, dict):
            return result
        return {"summary": str(result), "raw_result": result}


class PluginRegistry:
    """Scan the plugins directory and lazily load wrapper runtimes."""

    def __init__(self, plugin_dir: Optional[Path] = None):
        self.plugin_dir = Path(plugin_dir or settings.ATLAS_PLUGIN_DIR)
        self._plugins: Dict[str, RegisteredPlugin] = {}
        self.refresh()

    def _iter_candidates(self, root: Path) -> List[Path]:
        """Yield plugin candidates from root, supporting one level of grouping.

        Supports both flat layout (plugins/my_plugin/) and grouped layout
        (plugins/chemistry/my_plugin/, plugins/prometheus/my_plugin/).
        A directory is a group folder if it contains no manifest.json but
        contains subdirectories that do.
        """
        candidates: List[Path] = []
        root_dir_names = {
            item.name
            for item in root.iterdir()
            if item.is_dir() and not item.name.startswith(".")
        }
        for item in sorted(root.iterdir(), key=lambda p: p.name.lower()):
            if item.name.startswith("."):
                continue
            if item.is_dir():
                manifest_path = item / "manifest.json"
                if manifest_path.exists():
                    # Direct plugin directory
                    candidates.append(item)
                else:
                    # Potential group folder — recurse one level
                    child_dir_names = {
                        sub.name
                        for sub in item.iterdir()
                        if sub.is_dir() and not sub.name.startswith(".")
                    }
                    for sub in sorted(item.iterdir(), key=lambda p: p.name.lower()):
                        if sub.name.startswith("."):
                            continue
                        if (
                            sub.is_file()
                            and sub.suffix.lower() in {".atlas", ".zip"}
                            and sub.stem in child_dir_names
                        ):
                            continue
                        candidates.append(sub)
            else:
                # .atlas or .zip file at root level
                if item.suffix.lower() in {".atlas", ".zip"} and item.stem in root_dir_names:
                    continue
                candidates.append(item)
        return candidates

    def refresh(self) -> None:
        """Rescan the plugins directory for folders and zip archives."""
        self.plugin_dir.mkdir(parents=True, exist_ok=True)
        previous = self._plugins
        discovered: Dict[str, RegisteredPlugin] = {}

        for candidate in self._iter_candidates(self.plugin_dir):
            if candidate.name.startswith("."):
                continue
            record = self._build_record(candidate)
            if record is None:
                continue
            existing = previous.get(record.manifest.name)
            if (
                existing is not None
                and existing.source_path == record.source_path
                and existing.wrapper_reference == record.wrapper_reference
            ):
                record.wrapper_instance = existing.wrapper_instance
                record.load_error = existing.load_error
            if record.manifest.name in discovered:
                previous_record = discovered[record.manifest.name]
                if self._source_priority(previous_record.source_type) > self._source_priority(record.source_type):
                    logger.warning(
                        "Duplicate Atlas plugin name '%s' from %s; keeping %s over lower-priority %s source",
                        record.manifest.name,
                        candidate,
                        previous_record.source_path,
                        record.source_type,
                    )
                    continue
                logger.warning(
                    "Duplicate Atlas plugin name '%s' from %s; overriding previous entry",
                    record.manifest.name,
                    candidate,
                )
            discovered[record.manifest.name] = record

        self._plugins = discovered
        logger.info("Atlas PluginRegistry loaded %d plugin(s)", len(self._plugins))

    def _build_record(self, candidate: Path) -> Optional[RegisteredPlugin]:
        if candidate.is_dir():
            manifest_path = candidate / "manifest.json"
            if not manifest_path.exists():
                return None
            try:
                manifest = PluginManifest.model_validate_json(
                    manifest_path.read_text(encoding="utf-8")
                )
            except Exception as exc:
                logger.warning("Skipping invalid plugin manifest at %s: %s", manifest_path, exc)
                return None
            return RegisteredPlugin(
                manifest=manifest,
                source_path=candidate,
                wrapper_reference=manifest.entry_point,
                source_type="directory",
            )

        if candidate.is_file() and candidate.suffix.lower() == ".atlas":
            return self._build_atlas_record(candidate)

        if candidate.is_file() and candidate.suffix.lower() == ".zip":
            try:
                with zipfile.ZipFile(candidate) as archive:
                    manifest_member = self._resolve_archive_member(
                        archive.namelist(),
                        "manifest.json",
                    )
                    if manifest_member is None:
                        return None
                    manifest = PluginManifest.model_validate_json(
                        archive.read(manifest_member).decode("utf-8")
                    )
                    wrapper_member = self._resolve_archive_member(
                        archive.namelist(),
                        manifest.entry_point,
                    )
                    if wrapper_member is None:
                        logger.warning(
                            "Skipping zip plugin %s because %s was not found",
                            candidate,
                            manifest.entry_point,
                        )
                        return None
            except Exception as exc:
                logger.warning("Skipping unreadable zip plugin %s: %s", candidate, exc)
                return None

            return RegisteredPlugin(
                manifest=manifest,
                source_path=candidate,
                wrapper_reference=wrapper_member,
                source_type="zip",
            )

        return None

    def _build_atlas_record(self, candidate: Path) -> Optional[RegisteredPlugin]:
        """Build a RegisteredPlugin from a .atlas binary package."""
        from app.atlas_plugin_system.atlas_format import inspect_atlas

        try:
            info = inspect_atlas(candidate)
            manifest = PluginManifest.model_validate(info["manifest"])
        except Exception as exc:
            logger.warning("Skipping invalid .atlas package %s: %s", candidate, exc)
            return None

        return RegisteredPlugin(
            manifest=manifest,
            source_path=candidate,
            wrapper_reference="<atlas>",
            source_type="atlas",
        )

    @staticmethod
    def _source_priority(source_type: str) -> int:
        return {
            "directory": 3,
            "atlas": 2,
            "zip": 1,
        }.get(source_type, 0)

    @staticmethod
    def _resolve_archive_member(names: List[str], target_name: str) -> Optional[str]:
        direct_matches = [name for name in names if name.rstrip("/") == target_name]
        if direct_matches:
            return direct_matches[0]

        suffix = "/" + target_name
        nested_matches = [name for name in names if name.endswith(suffix)]
        if nested_matches:
            nested_matches.sort(key=len)
            return nested_matches[0]

        return None

    def list_plugins(self) -> List[Dict[str, Any]]:
        """Return plugin metadata for API responses and prompt construction."""
        return [
            {
                "name": record.manifest.name,
                "description": record.manifest.description,
                "priority": record.manifest.priority,
                "input_schema": record.manifest.input_schema,
                "output_schema": record.manifest.output_schema,
                "tags": record.manifest.tags,
                "license": record.manifest.license,
                "optional_dependencies": record.manifest.optional_dependencies,
                "artifacts": record.manifest.artifacts,
                "resource_requirements": record.manifest.resource_requirements.model_dump(),
                "self_test": record.manifest.self_test,
                "fallback_used": record.manifest.fallback_used,
                "source": str(record.source_path),
                "source_type": record.source_type,
                "loaded": record.wrapper_instance is not None,
                "load_error": record.load_error,
            }
            for record in self._ordered_plugins()
        ]

    def tool_names(self) -> List[str]:
        """Return tool names ordered by prompt priority."""
        return [record.manifest.name for record in self._ordered_plugins()]

    def is_exclusive_gpu(self, plugin_name: str) -> bool:
        """Return True if the plugin's manifest requests exclusive GPU access."""
        record = self._plugins.get(plugin_name)
        if record is None:
            return False
        return bool(record.manifest.resource_requirements.exclusive_gpu)

    def build_toolkit_prompt(self) -> str:
        """Compile manifest schemas into an orchestrator-facing toolkit block."""
        tool_blocks: List[str] = []
        for record in self._ordered_plugins():
            manifest = record.manifest
            required = manifest.input_schema.get("required", []) if manifest.input_schema else []
            tool_blocks.append(
                "\n".join(
                    [
                        f"TOOL: {manifest.name}",
                        "KIND: plugin",
                        f"DESCRIPTION: {manifest.description}",
                        f"REQUIRED PARAMETERS: {json.dumps(required, ensure_ascii=True)}",
                        f"INPUT SCHEMA: {json.dumps(manifest.input_schema, ensure_ascii=True)}",
                    ]
                )
            )
        return "\n\n".join(tool_blocks)

    async def invoke(
        self,
        plugin_name: str,
        arguments: Optional[Dict[str, Any]] = None,
        context: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Invoke a plugin wrapper by name."""
        record = self._plugins.get(plugin_name)
        if record is None:
            raise ValueError(f"Unknown Atlas Framework plugin: {plugin_name}")

        wrapper = self._load_wrapper(record)
        try:
            result = await wrapper.invoke(arguments or {}, context or {})
        except Exception as exc:
            logger.error("Atlas plugin '%s' failed: %s", plugin_name, exc, exc_info=True)
            return {
                "summary": f"{plugin_name} failed: {exc}",
                "error": str(exc),
                "plugin": plugin_name,
            }

        if isinstance(result, dict):
            if "summary" not in result:
                result["summary"] = self._summarize_result(plugin_name, result)
            return result

        return {
            "summary": f"{plugin_name} returned a non-dict result",
            "raw_result": result,
        }

    def _load_wrapper(self, record: RegisteredPlugin) -> Any:
        if record.wrapper_instance is not None:
            return record.wrapper_instance

        try:
            if record.source_type == "atlas":
                module = self._load_atlas_module(record)
            else:
                module_name = f"atlas_framework_plugin_{record.manifest.name}"
                module = types.ModuleType(module_name)
                module.__file__ = f"{record.source_path}:{record.wrapper_reference}"

                if record.source_type == "directory":
                    wrapper_path = record.source_path / record.wrapper_reference
                    source = wrapper_path.read_text(encoding="utf-8")
                    origin = str(wrapper_path)
                else:
                    with zipfile.ZipFile(record.source_path) as archive:
                        source = archive.read(record.wrapper_reference).decode("utf-8")
                    origin = f"{record.source_path}!{record.wrapper_reference}"

                exec(compile(source, origin, "exec"), module.__dict__)

            wrapper = module.__dict__.get("PLUGIN")
            if wrapper is None and "create_plugin" in module.__dict__:
                wrapper = module.__dict__["create_plugin"]()
            if wrapper is None and "invoke" in module.__dict__:
                wrapper = _FunctionWrapper(module.__dict__["invoke"])

            if wrapper is None or not hasattr(wrapper, "invoke"):
                raise RuntimeError(
                    f"Wrapper {record.wrapper_reference} did not expose PLUGIN, create_plugin(), or invoke()."
                )

            record.wrapper_instance = wrapper
            record.load_error = None
            return wrapper
        except Exception as exc:
            record.load_error = str(exc)
            raise

    @staticmethod
    def _load_atlas_module(record: RegisteredPlugin) -> types.ModuleType:
        """Load a .atlas binary package into a module via bytecode unmarshalling."""
        from app.atlas_plugin_system.atlas_format import load_atlas_module, read_atlas

        passphrase = os.environ.get("ATLAS_PLUGIN_KEY")
        package = read_atlas(record.source_path, passphrase=passphrase)
        return load_atlas_module(package)

    @staticmethod
    def _summarize_result(plugin_name: str, payload: Dict[str, Any]) -> str:
        keys = ", ".join(sorted(payload.keys())[:6])
        return f"{plugin_name} completed. Keys: {keys or 'none'}."

    def _ordered_plugins(self) -> List[RegisteredPlugin]:
        return sorted(
            self._plugins.values(),
            key=lambda record: (-record.manifest.priority, record.manifest.name),
        )


_plugin_registry: Optional[PluginRegistry] = None


def get_plugin_registry() -> PluginRegistry:
    """Return the Atlas Framework plugin registry singleton."""
    global _plugin_registry
    if _plugin_registry is None:
        _plugin_registry = PluginRegistry()
    return _plugin_registry
