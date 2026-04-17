"""Prometheus vision-alignment demo orchestration.

Wires the C3 -> renderer -> (optional) DPO finetune -> C5 inspection chain into
a single service call. The demo flow:

    1. physics_simulator generates `count` parametric reflow profiles, each
       tagged with a physics-derived defect label (cold_joint, overshoot,
       tombstone, ...).
    2. synthetic_renderer paints a physics-consistent PCB image for each
       profile plus `variants` augmentations, and writes a labels.jsonl +
       dpo_pairs.jsonl dataset on disk.
    3. A small evaluation loop invokes vision_inspector on a held-out subset
       of the rendered images, with the configured adapter (if any).
    4. The caller inspects the output: physics label vs. VLM label, format
       compliance rate, and token counts. These are the headline demo metrics.

Training itself (SFT + DPO) is NOT executed inline — it takes ~30 min on a
4090 and we do not want to block a web request on it. Instead, we return the
path to the rendered dataset and the exact CLI command the operator should run
to produce the adapter. The service is also safely callable with an existing
`adapter_path` to demonstrate a previously-trained alignment.
"""

from __future__ import annotations

import asyncio
import logging
import shutil
import tempfile
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

from app.atlas_plugin_system import get_tool_catalog

logger = logging.getLogger(__name__)


async def _invoke_plugin(name: str, args: Dict[str, Any]) -> Dict[str, Any]:
    catalog = get_tool_catalog()
    catalog.refresh()
    return await catalog.invoke(name, dict(args), context={"demo_mode": "vision_alignment"})


def _pick_evaluation_samples(
    dataset_dir: Path, per_label: int = 1,
) -> List[Dict[str, Any]]:
    """Return one sample per defect label (up to `per_label`) for held-out eval."""
    import json

    per_label_map: Dict[str, List[Dict[str, Any]]] = {}
    with (dataset_dir / "labels.jsonl").open() as fh:
        for line in fh:
            obj = json.loads(line)
            per_label_map.setdefault(obj["defect"], []).append(obj)
    selected: List[Dict[str, Any]] = []
    for label, items in per_label_map.items():
        selected.extend(items[:per_label])
    return selected


async def _run_held_out_eval(
    samples: List[Dict[str, Any]],
    dataset_dir: Path,
    reference_dir: Optional[Path],
    adapter_path: Optional[str],
    vlm_model: str,
) -> List[Dict[str, Any]]:
    results: List[Dict[str, Any]] = []
    for sample in samples:
        img_abs = dataset_dir / sample["image_path"]
        args: Dict[str, Any] = {
            "mode": "inspect",
            "image_path": str(img_abs),
            "anomaly_threshold": 0.3,
            "vlm_model": vlm_model,
        }
        if reference_dir is not None:
            args["reference_dir"] = str(reference_dir)
        if adapter_path:
            args["adapter_path"] = adapter_path
        started = time.perf_counter()
        result = await _invoke_plugin("vision_inspector", args)
        duration_ms = int((time.perf_counter() - started) * 1000)
        results.append({
            "profile_id": sample.get("profile_id"),
            "ground_truth_defect": sample["defect"],
            "ground_truth_location": sample["location"],
            "physics_peak_c": sample.get("physics_peak_c"),
            "physics_tal_s": sample.get("physics_tal_s"),
            "duration_ms": duration_ms,
            "verdict": result.get("verdict"),
            "vlm_defect": result.get("vlm_defect"),
            "vlm_location": result.get("vlm_location"),
            "vlm_format_ok": result.get("vlm_format_ok"),
            "vlm_token_count": result.get("vlm_token_count"),
            "anomaly_score": result.get("anomaly_score"),
            "summary": result.get("summary"),
            "error": result.get("error"),
        })
    return results


async def run_vision_alignment_demo(
    count: int = 24,
    variants: int = 4,
    seed: int = 11,
    adapter_path: Optional[str] = None,
    vlm_model: str = "Qwen/Qwen2-VL-2B-Instruct",
    keep_dataset: bool = True,
    dataset_dir: Optional[str] = None,
) -> Dict[str, Any]:
    """Generate a synthetic dataset, (optionally) run inspection, report metrics.

    Arguments:
        count: number of reflow profiles C3 should synthesise.
        variants: augmentations per profile (image count = count * variants).
        adapter_path: if provided, pass to vision_inspector so the VLM loads it.
        dataset_dir: if provided, persist the rendered dataset there.
        keep_dataset: if False, delete the dataset after evaluation.
    """
    # 1. Physics from C3.
    physics = await _invoke_plugin(
        "physics_simulator",
        {"mode": "reflow_defect_physics", "count": count, "seed": seed},
    )
    if not physics.get("valid"):
        return {
            "status": "blocked",
            "stage": "physics",
            "error": physics.get("error") or "physics_simulator refused",
            "details": physics,
        }

    # 2. Render.
    if dataset_dir:
        out_dir = Path(dataset_dir)
        out_dir.mkdir(parents=True, exist_ok=True)
    else:
        out_dir = Path(tempfile.mkdtemp(prefix="prometheus_vision_"))

    # Deferred import to avoid loading PIL at service import time.
    from plugins.prometheus.vision_inspector.synthetic_renderer import build_dataset

    render_summary = await asyncio.get_running_loop().run_in_executor(
        None,
        lambda: build_dataset(
            physics["profiles"], out_dir, variants_per_profile=variants, seed=seed,
        ),
    )

    # 3. Held-out eval — one image per defect label.
    eval_samples = _pick_evaluation_samples(out_dir, per_label=1)

    eval_results: List[Dict[str, Any]] = []
    eval_error: Optional[str] = None
    try:
        eval_results = await _run_held_out_eval(
            eval_samples,
            dataset_dir=out_dir,
            reference_dir=None,
            adapter_path=adapter_path,
            vlm_model=vlm_model,
        )
    except Exception as exc:
        eval_error = f"{type(exc).__name__}: {exc}"
        logger.warning("Held-out eval failed: %s", eval_error)

    # 4. Summary metrics.
    strict_hits = sum(1 for r in eval_results if r.get("vlm_format_ok"))
    correct_defect = sum(
        1 for r in eval_results
        if r.get("vlm_format_ok") and r.get("vlm_defect") == r.get("ground_truth_defect")
    )
    mean_tokens = (
        sum(int(r.get("vlm_token_count") or 0) for r in eval_results) / max(1, len(eval_results))
    )
    mean_latency_ms = (
        sum(int(r.get("duration_ms") or 0) for r in eval_results) / max(1, len(eval_results))
    )

    finetune_cmd = (
        f"python plugins/prometheus/vision_inspector/dpo_finetune.py "
        f"--dataset {out_dir.resolve()} --out adapters/luxshare_aoi"
    )

    response = {
        "status": "success",
        "physics": {
            "label_counts": physics["label_counts"],
            "thresholds": physics["thresholds"],
        },
        "dataset": {
            "out_dir": render_summary["out_dir"],
            "total_images": render_summary["total_images"],
            "per_defect": render_summary["per_defect"],
            "labels_jsonl": render_summary["labels_jsonl"],
            "dpo_pairs_jsonl": render_summary["dpo_pairs_jsonl"],
        },
        "eval": {
            "adapter_path": adapter_path,
            "vlm_model": vlm_model,
            "samples_evaluated": len(eval_results),
            "strict_format_rate": strict_hits / max(1, len(eval_results)),
            "defect_match_rate": correct_defect / max(1, len(eval_results)),
            "mean_token_count": round(mean_tokens, 1),
            "mean_latency_ms": round(mean_latency_ms, 1),
            "per_sample": eval_results,
            "error": eval_error,
        },
        "next_step": {
            "action": "Run the alignment CLI to produce a LoRA adapter, then replay this demo with `adapter_path=<adapter>/dpo`.",
            "command": finetune_cmd,
        },
    }

    if not keep_dataset and dataset_dir is None:
        shutil.rmtree(out_dir, ignore_errors=True)
        response["dataset"]["out_dir"] = "(removed; pass keep_dataset=True to preserve)"

    return response
