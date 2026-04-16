"""Retrosynthesis planning plugin — fully self-contained, no app imports.

Wraps AiZynthFinder ONNX model for retrosynthesis routes. Runs on CPU.
"""
import asyncio
import logging
import os
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)


class PlanSynthesisWrapper:

    def __init__(self):
        self._finder: Any = None
        self._attempted_load = False

    def _ensure_finder(self) -> Any:
        if self._attempted_load:
            return self._finder
        self._attempted_load = True
        try:
            import importlib.util
            if importlib.util.find_spec("aizynthfinder") is None:
                raise ImportError("aizynthfinder not installed")
            from aizynthfinder.aizynthfinder import AiZynthFinder
            config_path = os.path.join(os.getcwd(), "data", "config.yml")
            if not os.path.exists(config_path):
                config_path = os.path.join(os.getcwd(), "config.yml")
            if not os.path.exists(config_path):
                logger.warning("AiZynthFinder config not found. plan_synthesis will be skipped.")
                return None
            self._finder = AiZynthFinder(configfile=config_path)
            logger.info("AiZynthFinder model loaded.")
        except ImportError:
            logger.warning("aizynthfinder not installed — plan_synthesis will be skipped.")
        except Exception as e:
            logger.warning("Failed to load AiZynthFinder: %s", e)
        return self._finder

    async def invoke(
        self,
        arguments: Optional[Dict[str, Any]] = None,
        context: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        args = arguments or {}
        smiles = args.get("smiles", "")
        if not smiles:
            return {"valid": False, "error": "Missing 'smiles' argument."}
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(None, self._compute, smiles)

    def _compute(self, smiles: str) -> dict:
        finder = self._ensure_finder()
        if finder is None:
            return {
                "skipped": True, "reason": "aizynthfinder is not installed",
                "summary": "Retrosynthesis skipped — aizynthfinder not installed.",
            }
        try:
            finder.target_smiles = smiles
            try:
                finder.stock.select("zinc")
                finder.expansion_policy.select("uspto")
                finder.filter_policy.select("uspto")
            except Exception as e:
                logger.warning("Failed to select policies, using defaults: %s", e)

            finder.tree_search()
            finder.build_routes()

            if not finder.routes:
                return {"smiles": smiles, "valid": True, "routes_found": 0,
                        "message": "No synthesis routes found.", "routes": []}

            routes_data = []
            stats = finder.extract_statistics()
            for i, route in enumerate(finder.routes.dicts[:3]):
                nodes = getattr(finder.routes[i], "nodes", [])
                if not nodes and "nodes" in route:
                    nodes = route["nodes"]
                routes_data.append({
                    "route_index": i + 1, "score": route.get("score", 0),
                    "is_solved": route.get("is_solved", False),
                    "starting_materials": list(route.get("starting_materials", [])),
                    "number_of_steps": route.get("length", 0) if "length" in route else len(nodes) // 2 if isinstance(nodes, list) else "Unknown",
                    "reaction_summary": route.get("reaction_summary", "Detailed reactions omitted for brevity"),
                })

            return {
                "smiles": smiles, "valid": True,
                "routes_found": len(finder.routes), "routes": routes_data,
                "search_stats": {
                    "iterations": stats.get("number_of_iterations", 0),
                    "time_s": round(stats.get("time", 0), 2),
                },
            }
        except Exception as e:
            return {"smiles": smiles, "valid": False, "error": str(e)}


PLUGIN = PlanSynthesisWrapper()
