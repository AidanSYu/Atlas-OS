"""Smoke tests for all Atlas Framework plugins.

Tests that every plugin:
1. Has a valid manifest.json
2. wrapper.py loads and exposes a PLUGIN object with invoke()
3. invoke() returns a dict with a 'summary' key (or at minimum doesn't crash)

Plugins with heavy dependencies (torch, tigramite, etc.) are tested for
load-ability only — their self_test modes require the deps to be installed.
"""
import asyncio
import json
import sys
import types
from pathlib import Path

import pytest

# Resolve paths
BACKEND_DIR = Path(__file__).resolve().parent.parent
PLUGINS_DIR = BACKEND_DIR / "plugins"
sys.path.insert(0, str(BACKEND_DIR))

# ---------------------------------------------------------------------------
# Discovery: find all plugin directories (supports grouped layout)
# ---------------------------------------------------------------------------

def _discover_plugins():
    """Yield (group, name, plugin_dir) for every plugin with manifest.json."""
    for item in sorted(PLUGINS_DIR.iterdir()):
        if not item.is_dir() or item.name.startswith("."):
            continue
        manifest = item / "manifest.json"
        if manifest.exists():
            yield ("", item.name, item)
        else:
            # Group folder
            for sub in sorted(item.iterdir()):
                if sub.is_dir() and (sub / "manifest.json").exists():
                    yield (item.name, sub.name, sub)


ALL_PLUGINS = list(_discover_plugins())
PLUGIN_IDS = [f"{g}/{n}" if g else n for g, n, _ in ALL_PLUGINS]


# ---------------------------------------------------------------------------
# Manifest validation
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("group,name,plugin_dir", ALL_PLUGINS, ids=PLUGIN_IDS)
def test_manifest_valid(group, name, plugin_dir):
    """Every plugin must have a parseable manifest with required fields."""
    manifest_path = plugin_dir / "manifest.json"
    assert manifest_path.exists(), f"Missing manifest.json in {plugin_dir}"

    data = json.loads(manifest_path.read_text(encoding="utf-8"))
    assert "name" in data, "Manifest missing 'name'"
    assert "description" in data, "Manifest missing 'description'"
    assert isinstance(data.get("priority", 50), int), "Priority must be int"
    assert data["name"] == name, f"Manifest name '{data['name']}' != directory name '{name}'"


# ---------------------------------------------------------------------------
# Wrapper loading
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("group,name,plugin_dir", ALL_PLUGINS, ids=PLUGIN_IDS)
def test_wrapper_loads(group, name, plugin_dir):
    """Every plugin's wrapper.py must be parseable Python with no app.* imports."""
    wrapper_path = plugin_dir / "wrapper.py"
    assert wrapper_path.exists(), f"Missing wrapper.py in {plugin_dir}"

    source = wrapper_path.read_text(encoding="utf-8")

    # Check for forbidden imports at source level
    import ast
    tree = ast.parse(source, filename=str(wrapper_path))
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module and node.module.startswith("app."):
            pytest.fail(f"Forbidden import from '{node.module}' at line {node.lineno}")
        if isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name.startswith("app."):
                    pytest.fail(f"Forbidden import '{alias.name}' at line {node.lineno}")


# ---------------------------------------------------------------------------
# Lightweight plugins: actually invoke them
# ---------------------------------------------------------------------------

LIGHTWEIGHT_PLUGINS = {
    "traceability_compliance",
    "evaluate_strategy",
    "enumerate_fragments",
    "standardize_smiles",
}


def _load_plugin_module(plugin_dir: Path):
    """Load a plugin wrapper into a module and return its PLUGIN object."""
    wrapper_path = plugin_dir / "wrapper.py"
    source = wrapper_path.read_text(encoding="utf-8")
    module = types.ModuleType(f"test_plugin_{plugin_dir.name}")
    module.__file__ = str(wrapper_path)
    try:
        exec(compile(source, str(wrapper_path), "exec"), module.__dict__)
    except ImportError as e:
        pytest.skip(f"Dependency not installed: {e}")
    plugin = module.__dict__.get("PLUGIN")
    if plugin is None:
        pytest.fail("wrapper.py does not expose PLUGIN")
    return plugin


@pytest.mark.parametrize("group,name,plugin_dir", ALL_PLUGINS, ids=PLUGIN_IDS)
def test_lightweight_invoke(group, name, plugin_dir):
    """Lightweight plugins can be invoked without heavy deps."""
    if name not in LIGHTWEIGHT_PLUGINS:
        pytest.skip(f"{name} requires heavy dependencies")

    plugin = _load_plugin_module(plugin_dir)

    if name == "traceability_compliance":
        result = asyncio.run(plugin.invoke({"mode": "self_test"}))
        assert result.get("valid"), f"self_test failed: {result.get('error', result.get('summary'))}"
        assert "bundle_id" in result
        assert "content_hash" in result
        assert "narrative_report" in result

    elif name == "evaluate_strategy":
        result = asyncio.run(plugin.invoke({
            "routes": [
                {"route_index": 1, "score": 0.8, "number_of_steps": 3, "starting_materials": ["A", "B"]},
                {"route_index": 2, "score": 0.5, "number_of_steps": 6, "starting_materials": ["A", "B", "C"]},
            ]
        }))
        assert result.get("valid")
        assert len(result["scored_routes"]) == 2

    elif name == "enumerate_fragments":
        result = asyncio.run(plugin.invoke({"scaffold_name": "xyloside", "max_candidates": 5}))
        assert len(result.get("molecules", [])) > 0
        assert "summary" in result

    elif name == "standardize_smiles":
        result = asyncio.run(plugin.invoke({"smiles_list": ["c1ccccc1", "CC(=O)O"]}))
        assert "molecules" in result
        assert result.get("failed_count", -1) >= 0


# ---------------------------------------------------------------------------
# Heavy plugins: test only if deps are available
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("group,name,plugin_dir", ALL_PLUGINS, ids=PLUGIN_IDS)
def test_heavy_plugin_self_test(group, name, plugin_dir):
    """Heavy plugins with self_test mode — only runs if deps are installed."""
    if name in LIGHTWEIGHT_PLUGINS:
        pytest.skip("Already tested in lightweight suite")

    # These require specific dependencies
    dep_map = {
        "causal_discovery": ["tigramite", "pysr"],
        "manufacturing_world_model": ["numpy", "ruptures"],
        "physics_simulator": ["torch"],
        "sandbox_lab": ["botorch"],
        "vision_inspector": ["anomalib", "transformers", "torch"],
        "predict_properties": ["rdkit"],
        "check_toxicity": ["rdkit"],
        "predict_admet": [],  # has mock fallback
        "score_synthesizability": [],  # has heuristic
        "plan_synthesis": [],  # has skip sentinel
        "verify_spectrum": ["nmrglue", "scipy"],
    }

    required_deps = dep_map.get(name, [])
    for dep in required_deps:
        try:
            __import__(dep)
        except ImportError:
            pytest.skip(f"Dependency '{dep}' not installed for {name}")

    if name == "manufacturing_world_model":
        backend_candidates = [
            "chronos",
            "timesfm",
            "tsfm_public",
            "momentfm",
            "statsforecast",
        ]
        for dep in backend_candidates:
            try:
                __import__(dep)
                break
            except ImportError:
                continue
        else:
            pytest.skip("No supported forecasting backend installed for manufacturing_world_model")

    plugin = _load_plugin_module(plugin_dir)

    # Try self_test mode if supported — only prometheus plugins have it
    if name not in ("traceability_compliance", "causal_discovery",
                     "manufacturing_world_model", "physics_simulator",
                     "sandbox_lab", "vision_inspector"):
        pytest.skip(f"{name} is a chemistry plugin without self_test mode")
        return

    if hasattr(plugin, "invoke"):
        result = asyncio.run(plugin.invoke({"mode": "self_test"}))
        if isinstance(result, dict):
            assert "summary" in result or "error" in result, f"No summary or error in result: {result.keys()}"
