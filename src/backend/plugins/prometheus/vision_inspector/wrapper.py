"""Offline AOI triage with PatchCore and optional local VLM adjudication.

The VLM stage is post-trained via `dpo_finetune.py` to emit a strict one-line
format (`DEFECT: <label> | CONFIDENCE: <0-1> | LOCATION: <comp>_PIN<n>`). Pass
`adapter_path` to this plugin to load a LoRA adapter on top of the frozen base
VLM; without it, the base model runs zero-shot and you get whatever verbose
output it was trained to emit."""

from __future__ import annotations

import asyncio
import gc
import logging
import os
import re
import tempfile
from pathlib import Path
from typing import Any, Dict, Optional, Tuple

import numpy as np

logger = logging.getLogger(__name__)

_VLM_MODEL = None
_VLM_PROCESSOR = None
_VLM_LOADED_KEY: Optional[Tuple[str, str]] = None
_DEFAULT_VLM_MODEL_ID = "Qwen/Qwen2-VL-2B-Instruct"

_STRICT_RE = re.compile(
    r"DEFECT:\s*(?P<defect>[A-Za-z_][A-Za-z0-9_]*)\s*\|\s*"
    r"CONFIDENCE:\s*(?P<confidence>[01]?\.\d+|1(?:\.0+)?|0)\s*\|\s*"
    r"LOCATION:\s*(?P<location>[A-Za-z0-9_]+)",
)


def _has_anomalib() -> bool:
    import sys
    try:
        import anomalib  # noqa: F401
        return True
    except ImportError as exc:
        logger.error(
            "[vision_inspector] anomalib import failed. python=%s, sys.path[0:3]=%s, error=%s",
            sys.executable, sys.path[:3], exc,
        )
        return False


def _has_transformers() -> bool:
    try:
        import torch  # noqa: F401
        import transformers  # noqa: F401
        return True
    except ImportError:
        return False


def _synthetic_pcb(w: int = 512, h: int = 512, defect: Optional[str] = None):
    from PIL import Image, ImageDraw

    img = Image.new("RGB", (w, h), (20, 80, 20))
    draw = ImageDraw.Draw(img)
    for x in range(64, w, 80):
        for y in range(64, h, 80):
            draw.rectangle([x - 12, y - 12, x + 12, y + 12], fill=(180, 180, 180))
    for y in range(100, h, 80):
        draw.line([(50, y), (w - 50, y)], fill=(200, 170, 50), width=2)
    if defect == "solder_bridge":
        draw.line([(64, 64), (144, 64)], fill=(180, 180, 180), width=6)
    elif defect == "missing_component":
        draw.rectangle([140, 140, 170, 170], fill=(20, 80, 20))
    elif defect == "shadow":
        shadow = Image.new("RGBA", (w, h), (0, 0, 0, 100))
        img = Image.alpha_composite(img.convert("RGBA"), shadow).convert("RGB")
    return img


def _generate_self_test_images(tmpdir: str) -> Dict[str, list]:
    ref_dir = os.path.join(tmpdir, "reference")
    defect_dir = os.path.join(tmpdir, "defects")
    os.makedirs(ref_dir, exist_ok=True)
    os.makedirs(defect_dir, exist_ok=True)

    reference_paths = []
    for idx in range(10):
        path = os.path.join(ref_dir, f"good_{idx:03d}.png")
        _synthetic_pcb().save(path)
        reference_paths.append(path)

    defective = []
    for defect_type in ["solder_bridge", "missing_component", "shadow"]:
        path = os.path.join(defect_dir, f"defect_{defect_type}.png")
        _synthetic_pcb(defect=defect_type).save(path)
        defective.append({"path": path, "defect_type": defect_type})

    return {"reference_dir": ref_dir, "reference_paths": reference_paths, "defective": defective}


def _train_patchcore(reference_dir: str, model_save_dir: str) -> str:
    from anomalib.data import Folder
    from anomalib.engine import Engine
    from anomalib.models import Patchcore

    datamodule = Folder(
        name="reference",
        root=reference_dir,
        normal_dir=reference_dir,
        train_batch_size=8,
        eval_batch_size=8,
    )
    model = Patchcore(backbone="wide_resnet50_2", layers=["layer2", "layer3"], coreset_sampling_ratio=0.1)
    engine = Engine(max_epochs=1, default_root_dir=model_save_dir)
    engine.fit(model=model, datamodule=datamodule)
    return model_save_dir


def _run_patchcore_inference(image_path: str, model_dir: str) -> Dict[str, Any]:
    from PIL import Image
    from anomalib.models import Patchcore

    ckpt_candidates = list(Path(model_dir).rglob("*.ckpt"))
    if not ckpt_candidates:
        raise FileNotFoundError(f"No PatchCore checkpoint found in {model_dir}")
    model = Patchcore.load_from_checkpoint(str(ckpt_candidates[0]))
    model.eval()

    img = Image.open(image_path).convert("RGB").resize((256, 256))
    img_array = np.array(img, dtype=np.float32) / 255.0

    import torch

    img_tensor = torch.from_numpy(img_array).permute(2, 0, 1).unsqueeze(0)
    with torch.no_grad():
        predictions = model(img_tensor)
    anomaly_map = predictions.anomaly_map.cpu().squeeze().numpy() if predictions.anomaly_map is not None else None
    pred_mask = predictions.pred_mask.cpu().squeeze().numpy() if predictions.pred_mask is not None else None
    score = float(predictions.pred_score.cpu().item())
    return {
        "engine_used": "patchcore",
        "anomaly_score": min(max(score, 0.0), 1.0),
        "anomaly_heatmap": anomaly_map,
        "pred_mask": pred_mask,
    }


def _extract_anomaly_crop(image_path: str, heatmap, padding: int = 30) -> Dict[str, Any]:
    from PIL import Image

    img = Image.open(image_path).convert("RGB")
    width, height = img.size
    if heatmap is None:
        return {"crop": img, "bbox": [0, 0, width, height]}

    heatmap = np.asarray(heatmap, dtype=np.float32)
    ys, xs = np.where(heatmap > np.percentile(heatmap, 90))
    if len(xs) == 0 or len(ys) == 0:
        return {"crop": img, "bbox": [0, 0, width, height]}

    scale_x = width / heatmap.shape[1]
    scale_y = height / heatmap.shape[0]
    x_min = max(0, int(xs.min() * scale_x) - padding)
    y_min = max(0, int(ys.min() * scale_y) - padding)
    x_max = min(width, int(xs.max() * scale_x) + padding)
    y_max = min(height, int(ys.max() * scale_y) + padding)
    return {"crop": img.crop((x_min, y_min, x_max, y_max)), "bbox": [x_min, y_min, x_max, y_max]}


_STRICT_PROMPT = (
    "You are a factory AOI inspector. Report the defect for the highlighted "
    "component. Output exactly one line in this format and nothing else:\n"
    "DEFECT: <label> | CONFIDENCE: <0-1> | LOCATION: <component>_PIN<n>\n"
    "Valid labels: pass, cold_joint, overshoot_damage, insufficient_wetting, "
    "excessive_tal_voids, thermal_shock_tombstone, solder_bridge."
)


def _load_vlm(vlm_model: str, adapter_path: Optional[str] = None) -> None:
    """Load (or reuse) the VLM + optional PEFT adapter.

    Cached on (model_id, adapter_path) — swapping adapters forces a reload.
    """
    global _VLM_MODEL, _VLM_PROCESSOR, _VLM_LOADED_KEY

    cache_key = (vlm_model, adapter_path or "")
    if _VLM_MODEL is not None and _VLM_LOADED_KEY == cache_key:
        return
    if _VLM_MODEL is not None and _VLM_LOADED_KEY != cache_key:
        _unload_vlm()

    # Qwen2-VL-2B is our default (strict-format post-trained target). Qwen2.5-VL
    # works for backwards compatibility — choose the matching model class by
    # inspecting the repo id.
    if "Qwen2.5-VL" in vlm_model:
        from transformers import AutoProcessor, Qwen2_5_VLForConditionalGeneration as _Cls
    else:
        from transformers import AutoProcessor, Qwen2VLForConditionalGeneration as _Cls

    try:
        from transformers import BitsAndBytesConfig

        quant_config = BitsAndBytesConfig(load_in_4bit=True, bnb_4bit_compute_dtype="float16")
        model = _Cls.from_pretrained(
            vlm_model,
            quantization_config=quant_config,
            device_map="auto",
            local_files_only=True,
        )
    except Exception:
        model = _Cls.from_pretrained(
            vlm_model,
            device_map="auto",
            local_files_only=True,
        )

    if adapter_path:
        try:
            from peft import PeftModel  # type: ignore
        except ImportError as exc:
            raise RuntimeError(
                "adapter_path was supplied but 'peft' is not installed. "
                "Install it with: pip install peft."
            ) from exc
        model = PeftModel.from_pretrained(model, adapter_path)
        logger.info("Loaded VLM adapter from %s on top of %s", adapter_path, vlm_model)

    _VLM_MODEL = model
    _VLM_PROCESSOR = AutoProcessor.from_pretrained(vlm_model, local_files_only=True)
    _VLM_LOADED_KEY = cache_key


def _unload_vlm() -> None:
    global _VLM_MODEL, _VLM_PROCESSOR, _VLM_LOADED_KEY
    if _VLM_MODEL is not None:
        del _VLM_MODEL
        del _VLM_PROCESSOR
        _VLM_MODEL = None
        _VLM_PROCESSOR = None
        _VLM_LOADED_KEY = None
        try:
            import torch

            if torch.cuda.is_available():
                torch.cuda.empty_cache()
        except Exception:
            pass
        gc.collect()


def _parse_strict_output(raw: str) -> Dict[str, Any]:
    """Extract the strict one-line schema from VLM output.

    If the model emits the structured line anywhere in its response we accept
    it; if not, we flag the response as `format_violation` and keep the raw
    text so the caller can see what went wrong.
    """
    match = _STRICT_RE.search(raw)
    if match is None:
        return {
            "defect": None,
            "confidence": None,
            "location": None,
            "format_ok": False,
            "raw": raw,
        }
    try:
        confidence = float(match.group("confidence"))
    except ValueError:
        confidence = None
    return {
        "defect": match.group("defect"),
        "confidence": min(max(confidence, 0.0), 1.0) if confidence is not None else None,
        "location": match.group("location"),
        "format_ok": True,
        "raw": raw,
    }


def _map_defect_to_verdict(defect: Optional[str]) -> str:
    if defect is None:
        return "UNCERTAIN"
    if defect == "pass":
        return "PASS"
    return "FAIL"


def _run_vlm_classification(
    crop_image,
    vlm_model: str,
    prompt: str,
    adapter_path: Optional[str] = None,
) -> Dict[str, Any]:
    import torch

    _load_vlm(vlm_model, adapter_path=adapter_path)
    messages = [{"role": "user", "content": [{"type": "image", "image": crop_image}, {"type": "text", "text": prompt}]}]
    text = _VLM_PROCESSOR.apply_chat_template(messages, tokenize=False, add_generation_prompt=True)
    inputs = _VLM_PROCESSOR(text=[text], images=[crop_image], return_tensors="pt", padding=True)
    inputs = inputs.to(_VLM_MODEL.device)
    with torch.no_grad():
        # Strict-format output should fit well under 64 tokens; the lower cap
        # is also part of the latency story — shorter decode = faster cycle.
        generated = _VLM_MODEL.generate(**inputs, max_new_tokens=64, do_sample=False)
    input_len = inputs["input_ids"].shape[1]
    output_text = _VLM_PROCESSOR.batch_decode(generated[:, input_len:], skip_special_tokens=True)[0].strip()

    parsed = _parse_strict_output(output_text)
    return {
        "vlm_defect": parsed["defect"],
        "vlm_classification": parsed["defect"] if parsed["format_ok"] else "uncertain",
        "vlm_location": parsed["location"],
        "vlm_confidence": parsed["confidence"] if parsed["confidence"] is not None else 0.5,
        "vlm_format_ok": parsed["format_ok"],
        "vlm_explanation": parsed["raw"],
        "vlm_raw_output": output_text,
        "vlm_token_count": int(generated.shape[1] - input_len),
    }


def _save_heatmap(heatmap, save_path: str) -> str:
    from PIL import Image

    heatmap = np.asarray(heatmap, dtype=np.float32)
    if heatmap.ndim != 2:
        raise ValueError("Heatmap must be a 2D array.")
    heatmap = (heatmap - heatmap.min()) / max(heatmap.max() - heatmap.min(), 1e-6)
    colored = np.zeros((heatmap.shape[0], heatmap.shape[1], 3), dtype=np.uint8)
    colored[:, :, 0] = (heatmap * 255).astype(np.uint8)
    colored[:, :, 1] = ((1.0 - heatmap) * 64).astype(np.uint8)
    colored[:, :, 2] = ((1.0 - heatmap) * 64).astype(np.uint8)
    Image.fromarray(colored).save(save_path)
    return save_path


class VisionInspectorWrapper:
    async def invoke(
        self,
        arguments: Optional[Dict[str, Any]] = None,
        _context: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        args = arguments or {}
        mode = args.get("mode", "inspect")
        if mode == "self_test":
            return await self._run_self_test(args)
        if mode == "train_reference":
            return await self._train_reference(args)
        if mode == "inspect":
            return await self._inspect(args)
        return {"valid": False, "error": f"Unknown mode '{mode}'."}

    async def _train_reference(self, args: dict) -> Dict[str, Any]:
        reference_dir = args.get("reference_dir")
        if not reference_dir:
            return {"valid": False, "error": "'reference_dir' is required."}
        if not os.path.isdir(reference_dir):
            return {"valid": False, "error": f"Reference directory not found: {reference_dir}"}
        if not _has_anomalib():
            return {
                "valid": False,
                "error": (
                    "vision_inspector is unavailable because 'anomalib' is not installed. "
                    "Install it with: pip install anomalib"
                ),
                "summary": "Vision Inspector is not ready on this machine. Missing dependency: anomalib.",
            }

        model_dir = os.path.join(reference_dir, ".vision_model")
        os.makedirs(model_dir, exist_ok=True)
        loop = asyncio.get_running_loop()
        await loop.run_in_executor(None, _train_patchcore, reference_dir, model_dir)
        engine_used = "patchcore"
        return {
            "valid": True,
            "engine_used": engine_used,
            "model_dir": model_dir,
            "summary": f"Reference model trained using {engine_used}.",
        }

    async def _inspect(self, args: dict) -> Dict[str, Any]:
        if not _has_anomalib():
            return {
                "valid": False,
                "error": (
                    "vision_inspector is unavailable because 'anomalib' is not installed. "
                    "Install it with: pip install anomalib"
                ),
                "summary": "Vision Inspector is not ready on this machine. Missing dependency: anomalib.",
            }
        image_path = args.get("image_path")
        if not image_path:
            return {"valid": False, "error": "'image_path' is required."}
        if not os.path.isfile(image_path):
            return {"valid": False, "error": f"Image not found: {image_path}"}

        reference_dir = args.get("reference_dir", "")
        model_dir = os.path.join(reference_dir, ".vision_model") if reference_dir else ""
        if not model_dir or not os.path.isdir(model_dir):
            return {"valid": False, "error": "No trained vision model found. Run 'train_reference' first."}

        loop = asyncio.get_running_loop()
        result = await loop.run_in_executor(None, _run_patchcore_inference, image_path, model_dir)

        anomaly_score = float(result["anomaly_score"])
        heatmap = result.get("anomaly_heatmap")
        heatmap_path = ""
        if heatmap is not None:
            heatmap_path = _save_heatmap(heatmap, image_path.rsplit(".", 1)[0] + "_heatmap.png")

        threshold = float(args.get("anomaly_threshold", 0.5))
        crop_result = await loop.run_in_executor(None, _extract_anomaly_crop, image_path, heatmap)
        bbox = crop_result["bbox"]

        if anomaly_score < threshold:
            return {
                "valid": True,
                "engine_used": result["engine_used"],
                "verdict": "PASS",
                "anomaly_score": anomaly_score,
                "anomaly_heatmap_path": heatmap_path,
                "bbox": bbox,
                "vlm_explanation": None,
                "vlm_classification": None,
                "cascade_confidence": anomaly_score,
                "stage_reached": "detector_only",
                "summary": f"PASS — anomaly score {anomaly_score:.3f} is below threshold {threshold:.2f}.",
            }

        skip_vlm = bool(args.get("skip_vlm", False))
        vlm_model = args.get("vlm_model", _DEFAULT_VLM_MODEL_ID)
        prompt = args.get("prompt", _STRICT_PROMPT)
        adapter_path = args.get("adapter_path") or None
        if skip_vlm:
            verdict = "FAIL" if anomaly_score > 0.7 else "UNCERTAIN"
            return {
                "valid": True,
                "engine_used": result["engine_used"],
                "verdict": verdict,
                "anomaly_score": anomaly_score,
                "anomaly_heatmap_path": heatmap_path,
                "bbox": bbox,
                "vlm_explanation": "VLM stage skipped or unavailable.",
                "vlm_classification": None,
                "cascade_confidence": anomaly_score,
                "stage_reached": "detector_only",
                "summary": f"{verdict} - detector score {anomaly_score:.3f}; VLM stage intentionally skipped.",
            }

        if not _has_transformers():
            return {
                "valid": False,
                "error": (
                    "VLM adjudication was requested, but the local VLM stack is missing. "
                    "Install torch and transformers, then ensure the model weights are cached locally."
                ),
                "engine_used": result["engine_used"],
                "verdict": "UNCERTAIN",
                "anomaly_score": anomaly_score,
                "anomaly_heatmap_path": heatmap_path,
                "bbox": bbox,
                "vlm_explanation": None,
                "vlm_classification": None,
                "cascade_confidence": anomaly_score,
                "stage_reached": "detector_only",
                "summary": "Detector flagged the image, but the requested VLM adjudication stage is not available on this machine.",
            }

        try:
            vlm_result = await loop.run_in_executor(
                None, _run_vlm_classification, crop_result["crop"], vlm_model, prompt, adapter_path,
            )
            vlm_conf = float(vlm_result.get("vlm_confidence", 0.5))
            cascade_conf = 0.6 * anomaly_score + 0.4 * vlm_conf
            defect_label = vlm_result.get("vlm_defect")
            format_ok = bool(vlm_result.get("vlm_format_ok", False))
            if not format_ok:
                verdict = "FAIL" if cascade_conf > 0.7 else "UNCERTAIN"
            else:
                verdict = _map_defect_to_verdict(defect_label)
            return {
                "valid": True,
                "engine_used": result["engine_used"],
                "verdict": verdict,
                "anomaly_score": anomaly_score,
                "anomaly_heatmap_path": heatmap_path,
                "bbox": bbox,
                "vlm_defect": defect_label,
                "vlm_location": vlm_result.get("vlm_location"),
                "vlm_format_ok": format_ok,
                "vlm_token_count": vlm_result.get("vlm_token_count"),
                "vlm_explanation": vlm_result.get("vlm_explanation"),
                "vlm_classification": vlm_result.get("vlm_classification"),
                "cascade_confidence": cascade_conf,
                "adapter_path": adapter_path,
                "stage_reached": "detector+vlm",
                "summary": (
                    f"{verdict} — detector {anomaly_score:.3f}, "
                    f"VLM {'strict' if format_ok else 'unstructured'} output: "
                    f"{defect_label or 'n/a'} @ {vlm_result.get('vlm_location') or 'n/a'}"
                ),
            }
        except Exception as exc:
            return {
                "valid": False,
                "error": f"VLM adjudication failed: {exc}",
                "engine_used": result["engine_used"],
                "verdict": "UNCERTAIN" if anomaly_score <= 0.7 else "FAIL",
                "anomaly_score": anomaly_score,
                "anomaly_heatmap_path": heatmap_path,
                "bbox": bbox,
                "vlm_explanation": f"VLM unavailable: {exc}",
                "vlm_classification": None,
                "cascade_confidence": anomaly_score,
                "stage_reached": "detector_only",
                "summary": f"Detector score {anomaly_score:.3f}; VLM adjudication failed and was not silently substituted.",
            }
        finally:
            _unload_vlm()

    async def _run_self_test(self, args: dict) -> Dict[str, Any]:
        enable_vlm = bool(args.get("enable_vlm", True))
        loop = asyncio.get_running_loop()
        with tempfile.TemporaryDirectory(prefix="vision_inspector_selftest_") as tmpdir:
            test_data = await loop.run_in_executor(None, _generate_self_test_images, tmpdir)
            train_result = await self._train_reference({"reference_dir": test_data["reference_dir"]})
            if not train_result.get("valid"):
                return train_result

            engine_used = train_result["engine_used"]
            results = []
            detected_defects = 0
            all_valid = True
            for defect in test_data["defective"]:
                inspect_result = await self._inspect(
                    {
                        "image_path": defect["path"],
                        "reference_dir": test_data["reference_dir"],
                        "skip_vlm": not enable_vlm,
                    }
                )
                inspect_result["defect_type"] = defect["defect_type"]
                results.append(inspect_result)
                all_valid = all_valid and bool(inspect_result.get("valid"))
                if inspect_result.get("anomaly_score", 0.0) >= 0.5:
                    detected_defects += 1

        passed = all_valid and detected_defects == len(results)
        return {
            "valid": passed,
            "self_test": True,
            "engine_used": engine_used,
            "processed_images": len(results),
            "detected_defects": detected_defects,
            "vlm_stage": "enabled" if enable_vlm else "skipped",
            "results": results,
            "summary": (
                f"Self-test complete using {engine_used}: processed {len(results)} defective image(s), "
                f"flagged {detected_defects} above threshold. "
                f"Synthetic benchmark {'PASS' if passed else 'FAIL'}."
            ),
        }


PLUGIN = VisionInspectorWrapper()
