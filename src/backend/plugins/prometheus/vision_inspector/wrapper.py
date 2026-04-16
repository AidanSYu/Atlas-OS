"""Offline AOI triage with PatchCore and optional local VLM adjudication."""

from __future__ import annotations

import asyncio
import gc
import logging
import os
import tempfile
from pathlib import Path
from typing import Any, Dict, Optional

import numpy as np

logger = logging.getLogger(__name__)

_VLM_MODEL = None
_VLM_PROCESSOR = None


def _has_anomalib() -> bool:
    try:
        import anomalib  # noqa: F401
        return True
    except ImportError:
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
        task="classification",
        image_size=(256, 256),
        train_batch_size=8,
        eval_batch_size=8,
    )
    model = Patchcore(backbone="wide_resnet50_2", layers_to_extract=["layer2", "layer3"], coreset_sampling_ratio=0.1)
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


_DEFAULT_PROMPT = (
    "You are inspecting a cropped region from a PCB image flagged by anomaly detection. "
    "Respond with three lines only:\n"
    "CLASSIFICATION: one of [defect, false_positive, uncertain]\n"
    "CONFIDENCE: float between 0 and 1\n"
    "EXPLANATION: short rationale"
)


def _load_vlm(vlm_model: str) -> None:
    global _VLM_MODEL, _VLM_PROCESSOR
    if _VLM_MODEL is not None:
        return

    from transformers import AutoProcessor, Qwen2_5_VLForConditionalGeneration

    try:
        from transformers import BitsAndBytesConfig

        quant_config = BitsAndBytesConfig(load_in_4bit=True, bnb_4bit_compute_dtype="float16")
        _VLM_MODEL = Qwen2_5_VLForConditionalGeneration.from_pretrained(
            vlm_model,
            quantization_config=quant_config,
            device_map="auto",
            local_files_only=True,
        )
    except Exception:
        _VLM_MODEL = Qwen2_5_VLForConditionalGeneration.from_pretrained(
            vlm_model,
            device_map="auto",
            local_files_only=True,
        )
    _VLM_PROCESSOR = AutoProcessor.from_pretrained(vlm_model, local_files_only=True)


def _unload_vlm() -> None:
    global _VLM_MODEL, _VLM_PROCESSOR
    if _VLM_MODEL is not None:
        del _VLM_MODEL
        del _VLM_PROCESSOR
        _VLM_MODEL = None
        _VLM_PROCESSOR = None
        try:
            import torch

            if torch.cuda.is_available():
                torch.cuda.empty_cache()
        except Exception:
            pass
        gc.collect()


def _run_vlm_classification(crop_image, vlm_model: str, prompt: str) -> Dict[str, Any]:
    import torch

    _load_vlm(vlm_model)
    messages = [{"role": "user", "content": [{"type": "image", "image": crop_image}, {"type": "text", "text": prompt}]}]
    text = _VLM_PROCESSOR.apply_chat_template(messages, tokenize=False, add_generation_prompt=True)
    inputs = _VLM_PROCESSOR(text=[text], images=[crop_image], return_tensors="pt", padding=True)
    inputs = inputs.to(_VLM_MODEL.device)
    with torch.no_grad():
        generated = _VLM_MODEL.generate(**inputs, max_new_tokens=128)
    input_len = inputs["input_ids"].shape[1]
    output_text = _VLM_PROCESSOR.batch_decode(generated[:, input_len:], skip_special_tokens=True)[0].strip()

    classification = "uncertain"
    confidence = 0.5
    explanation = output_text
    for line in output_text.splitlines():
        line = line.strip()
        if line.upper().startswith("CLASSIFICATION:"):
            classification = line.split(":", 1)[1].strip().lower()
        elif line.upper().startswith("CONFIDENCE:"):
            try:
                confidence = float(line.split(":", 1)[1].strip())
            except ValueError:
                confidence = 0.5
        elif line.upper().startswith("EXPLANATION:"):
            explanation = line.split(":", 1)[1].strip()
    return {
        "vlm_classification": classification,
        "vlm_confidence": min(max(confidence, 0.0), 1.0),
        "vlm_explanation": explanation,
        "vlm_raw_output": output_text,
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
        vlm_model = args.get("vlm_model", "Qwen/Qwen2.5-VL-3B-Instruct")
        prompt = args.get("prompt", _DEFAULT_PROMPT)
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
            vlm_result = await loop.run_in_executor(None, _run_vlm_classification, crop_result["crop"], vlm_model, prompt)
            vlm_conf = float(vlm_result.get("vlm_confidence", 0.5))
            cascade_conf = 0.6 * anomaly_score + 0.4 * vlm_conf
            classification = vlm_result.get("vlm_classification", "uncertain")
            if classification == "false_positive":
                verdict = "PASS"
            elif cascade_conf > 0.7:
                verdict = "FAIL"
            else:
                verdict = "UNCERTAIN"
            return {
                "valid": True,
                "engine_used": result["engine_used"],
                "verdict": verdict,
                "anomaly_score": anomaly_score,
                "anomaly_heatmap_path": heatmap_path,
                "bbox": bbox,
                "vlm_explanation": vlm_result.get("vlm_explanation"),
                "vlm_classification": classification,
                "cascade_confidence": cascade_conf,
                "stage_reached": "detector+vlm",
                "summary": f"{verdict} — detector score {anomaly_score:.3f}, VLM classified '{classification}'.",
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
