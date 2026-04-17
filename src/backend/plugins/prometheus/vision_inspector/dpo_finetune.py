#!/usr/bin/env python3
"""
Vision Inspector — Qwen2-VL 2B alignment pipeline (SFT + DPO).

Post-trains a LoRA adapter on top of the frozen Qwen2-VL-2B-Instruct base so
the model emits the strict Luxshare AOI format:

    DEFECT: <label> | CONFIDENCE: <0-1> | LOCATION: <comp>_PIN<n>

Two stages:
  1. Supervised Fine-Tuning (SFT) — teach the format using the rendered dataset
     produced by `synthetic_renderer.build_dataset`. Loss is masked to the
     target tokens only (prompt tokens contribute nothing).
  2. Direct Preference Optimization (DPO) — punish conversational filler. For
     each sample, `chosen` is the strict one-line label; `rejected` is a
     rendered paragraph. A frozen copy of the base model serves as the
     reference policy.

Usage
-----
    # Full demo: generate synthetic dataset via C3 + renderer, then train.
    python dpo_finetune.py --demo --out adapters/luxshare_demo

    # Train against a pre-rendered dataset.
    python dpo_finetune.py --dataset /path/to/rendered/dir --out adapters/xxx

Implementation notes
--------------------
Heavy deps (torch, transformers, peft) are imported at call time so --help
works on a bare interpreter. No dependency on TRL's VLM DPO trainer, which
churns across releases — we implement both objectives directly so shape
assumptions are visible.
"""

from __future__ import annotations

import argparse
import json
import logging
import math
import random
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger("vision_inspector_dpo")
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s: %(message)s")


DEFAULT_BASE_MODEL = "Qwen/Qwen2-VL-2B-Instruct"
DEFAULT_LORA_TARGETS: List[str] = ["q_proj", "k_proj", "v_proj", "o_proj"]
_USER_PROMPT = (
    "You are a factory AOI inspector. Report the defect for the highlighted "
    "component. Output exactly one line in this format and nothing else:\n"
    "DEFECT: <label> | CONFIDENCE: <0-1> | LOCATION: <component>_PIN<n>\n"
    "Valid labels: pass, cold_joint, overshoot_damage, insufficient_wetting, "
    "excessive_tal_voids, thermal_shock_tombstone, solder_bridge."
)


# ---------------------------------------------------------------------------
# Dataset
# ---------------------------------------------------------------------------

@dataclass
class SftRecord:
    image_path: Path
    target_text: str


@dataclass
class DpoRecord:
    image_path: Path
    chosen: str
    rejected: str


def load_sft_records(dataset_dir: Path) -> List[SftRecord]:
    labels_path = dataset_dir / "labels.jsonl"
    if not labels_path.exists():
        raise FileNotFoundError(f"Expected labels.jsonl in {dataset_dir}")
    records: List[SftRecord] = []
    with labels_path.open() as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            obj = json.loads(line)
            img = dataset_dir / obj["image_path"]
            records.append(SftRecord(image_path=img, target_text=obj["label_string"]))
    return records


def load_dpo_records(dataset_dir: Path) -> List[DpoRecord]:
    pairs_path = dataset_dir / "dpo_pairs.jsonl"
    if not pairs_path.exists():
        raise FileNotFoundError(f"Expected dpo_pairs.jsonl in {dataset_dir}")
    records: List[DpoRecord] = []
    with pairs_path.open() as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            obj = json.loads(line)
            img = dataset_dir / obj["image_path"]
            records.append(DpoRecord(
                image_path=img, chosen=obj["chosen"], rejected=obj["rejected"],
            ))
    return records


# ---------------------------------------------------------------------------
# Synthetic-data path (hooks C3 + renderer for --demo)
# ---------------------------------------------------------------------------

def generate_synthetic_dataset(out_dir: Path, count: int, variants: int, seed: int) -> Dict[str, Any]:
    """Run physics_simulator + synthetic_renderer to produce a fresh dataset."""
    import asyncio

    sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent.parent))
    from plugins.prometheus.physics_simulator.wrapper import PLUGIN as PHYSICS
    from plugins.prometheus.vision_inspector.synthetic_renderer import build_dataset

    profiles = asyncio.run(PHYSICS.invoke({
        "mode": "reflow_defect_physics", "count": count, "seed": seed,
    }))["profiles"]
    return build_dataset(profiles, out_dir, variants_per_profile=variants, seed=seed)


# ---------------------------------------------------------------------------
# Input construction
# ---------------------------------------------------------------------------

def _messages_for(user_prompt: str, assistant_text: str) -> List[Dict[str, Any]]:
    return [
        {"role": "user", "content": [
            {"type": "image"},
            {"type": "text", "text": user_prompt},
        ]},
        {"role": "assistant", "content": [{"type": "text", "text": assistant_text}]},
    ]


def _build_batch(processor, images: List[Any], assistant_texts: List[str], device: str):
    """Return (inputs, labels) where labels mask everything except the target.

    Qwen2-VL's chat template stitches image placeholders into the text; we
    template each message pair, tokenize the full sequence, then build labels
    that keep only the assistant-text span (the target) active for loss.
    """
    import torch

    input_texts: List[str] = []
    target_texts: List[str] = []
    for text in assistant_texts:
        full = processor.apply_chat_template(
            _messages_for(_USER_PROMPT, text),
            tokenize=False, add_generation_prompt=False,
        )
        # Templated without the assistant turn gives us the prefix length.
        prefix = processor.apply_chat_template(
            _messages_for(_USER_PROMPT, ""),
            tokenize=False, add_generation_prompt=True,
        )
        input_texts.append(full)
        target_texts.append(full[len(prefix):] if full.startswith(prefix) else text)

    batch = processor(text=input_texts, images=images, return_tensors="pt", padding=True)
    input_ids = batch["input_ids"].to(device)
    attention_mask = batch["attention_mask"].to(device)
    labels = input_ids.clone()
    # Mask everything before each sample's target span.
    for i, tgt in enumerate(target_texts):
        # Tokenise target alone to get its length (approximate — we're tolerant
        # to off-by-one because ignored tokens are just skipped).
        tgt_tokens = processor.tokenizer(tgt, add_special_tokens=False)["input_ids"]
        tgt_len = min(len(tgt_tokens), input_ids.shape[1])
        if tgt_len <= 0:
            labels[i, :] = -100
            continue
        labels[i, :-tgt_len] = -100
    batch_on_device = {k: (v.to(device) if hasattr(v, "to") else v) for k, v in batch.items()}
    batch_on_device["labels"] = labels
    batch_on_device["input_ids"] = input_ids
    batch_on_device["attention_mask"] = attention_mask
    return batch_on_device


def _logprob_of_target(model, processor, images: List[Any], assistant_texts: List[str], device: str):
    """Sum log-prob of each target span under `model`. Shape: (batch,)."""
    import torch
    import torch.nn.functional as F

    batch = _build_batch(processor, images, assistant_texts, device)
    input_ids = batch["input_ids"]
    labels = batch["labels"]
    outputs = model(
        input_ids=input_ids,
        attention_mask=batch["attention_mask"],
        pixel_values=batch.get("pixel_values"),
        image_grid_thw=batch.get("image_grid_thw"),
    )
    logits = outputs.logits[:, :-1, :]
    targets = labels[:, 1:]
    logp = F.log_softmax(logits, dim=-1)
    # Gather only non-masked positions.
    mask = (targets != -100)
    safe_targets = targets.clamp(min=0)
    gathered = logp.gather(-1, safe_targets.unsqueeze(-1)).squeeze(-1)
    gathered = gathered * mask.float()
    return gathered.sum(dim=1)


# ---------------------------------------------------------------------------
# SFT
# ---------------------------------------------------------------------------

def train_sft(
    base_model: str,
    records: List[SftRecord],
    out_dir: Path,
    epochs: int,
    batch_size: int,
    lr: float,
    lora_rank: int,
    lora_alpha: int,
    lora_targets: List[str],
    device: str,
) -> Dict[str, Any]:
    import torch
    from PIL import Image
    from peft import LoraConfig, get_peft_model
    from transformers import AutoProcessor, Qwen2VLForConditionalGeneration

    out_dir.mkdir(parents=True, exist_ok=True)
    logger.info("SFT: loading base VLM %s on %s", base_model, device)
    model = Qwen2VLForConditionalGeneration.from_pretrained(
        base_model, torch_dtype=torch.bfloat16 if device == "cuda" else torch.float32,
    ).to(device)
    processor = AutoProcessor.from_pretrained(base_model)

    lora_cfg = LoraConfig(
        r=lora_rank,
        lora_alpha=lora_alpha,
        target_modules=lora_targets,
        lora_dropout=0.05,
        bias="none",
        task_type="CAUSAL_LM",
    )
    model = get_peft_model(model, lora_cfg)
    model.print_trainable_parameters()

    optim = torch.optim.AdamW(
        [p for p in model.parameters() if p.requires_grad], lr=lr,
    )
    history: List[Dict[str, float]] = []
    rng = random.Random(0)

    for epoch in range(1, epochs + 1):
        rng.shuffle(records)
        model.train()
        epoch_loss = 0.0
        n_batches = 0
        for i in range(0, len(records), batch_size):
            batch_records = records[i:i + batch_size]
            images = [Image.open(r.image_path).convert("RGB") for r in batch_records]
            texts = [r.target_text for r in batch_records]

            batch = _build_batch(processor, images, texts, device)
            optim.zero_grad()
            outputs = model(
                input_ids=batch["input_ids"],
                attention_mask=batch["attention_mask"],
                pixel_values=batch.get("pixel_values"),
                image_grid_thw=batch.get("image_grid_thw"),
                labels=batch["labels"],
            )
            outputs.loss.backward()
            optim.step()
            epoch_loss += float(outputs.loss.item())
            n_batches += 1
        avg_loss = epoch_loss / max(1, n_batches)
        logger.info("SFT epoch %d/%d  loss=%.4f", epoch, epochs, avg_loss)
        history.append({"epoch": epoch, "loss": avg_loss})

    model.save_pretrained(str(out_dir))
    processor.save_pretrained(str(out_dir))
    return {"stage": "sft", "history": history, "out_dir": str(out_dir.resolve())}


# ---------------------------------------------------------------------------
# DPO
# ---------------------------------------------------------------------------

def train_dpo(
    base_model: str,
    sft_adapter: Path,
    records: List[DpoRecord],
    out_dir: Path,
    epochs: int,
    batch_size: int,
    lr: float,
    beta: float,
    device: str,
) -> Dict[str, Any]:
    import torch
    import torch.nn.functional as F
    from PIL import Image
    from peft import PeftModel
    from transformers import AutoProcessor, Qwen2VLForConditionalGeneration

    out_dir.mkdir(parents=True, exist_ok=True)
    logger.info("DPO: loading base VLM %s + SFT adapter from %s", base_model, sft_adapter)

    dtype = torch.bfloat16 if device == "cuda" else torch.float32
    processor = AutoProcessor.from_pretrained(base_model)

    # Policy = base + SFT adapter (trainable). Reference = base (frozen, no adapter).
    base_for_policy = Qwen2VLForConditionalGeneration.from_pretrained(base_model, torch_dtype=dtype).to(device)
    policy = PeftModel.from_pretrained(base_for_policy, sft_adapter, is_trainable=True)

    reference = Qwen2VLForConditionalGeneration.from_pretrained(base_model, torch_dtype=dtype).to(device)
    for p in reference.parameters():
        p.requires_grad_(False)
    reference.eval()

    optim = torch.optim.AdamW(
        [p for p in policy.parameters() if p.requires_grad], lr=lr,
    )
    history: List[Dict[str, float]] = []
    rng = random.Random(0)

    for epoch in range(1, epochs + 1):
        rng.shuffle(records)
        policy.train()
        epoch_loss = 0.0
        epoch_margin = 0.0
        n_batches = 0
        for i in range(0, len(records), batch_size):
            batch_records = records[i:i + batch_size]
            images = [Image.open(r.image_path).convert("RGB") for r in batch_records]
            chosen_texts = [r.chosen for r in batch_records]
            rejected_texts = [r.rejected for r in batch_records]

            # Compute log-probs for chosen and rejected under both models.
            lp_policy_chosen = _logprob_of_target(policy, processor, images, chosen_texts, device)
            lp_policy_rejected = _logprob_of_target(policy, processor, images, rejected_texts, device)
            with torch.no_grad():
                lp_ref_chosen = _logprob_of_target(reference, processor, images, chosen_texts, device)
                lp_ref_rejected = _logprob_of_target(reference, processor, images, rejected_texts, device)

            chosen_ratio = lp_policy_chosen - lp_ref_chosen
            rejected_ratio = lp_policy_rejected - lp_ref_rejected
            margin = chosen_ratio - rejected_ratio
            loss = -F.logsigmoid(beta * margin).mean()

            optim.zero_grad()
            loss.backward()
            optim.step()
            epoch_loss += float(loss.item())
            epoch_margin += float(margin.mean().item())
            n_batches += 1
        avg_loss = epoch_loss / max(1, n_batches)
        avg_margin = epoch_margin / max(1, n_batches)
        logger.info("DPO epoch %d/%d  loss=%.4f margin=%.4f", epoch, epochs, avg_loss, avg_margin)
        history.append({"epoch": epoch, "loss": avg_loss, "margin": avg_margin})

    policy.save_pretrained(str(out_dir))
    processor.save_pretrained(str(out_dir))
    return {"stage": "dpo", "history": history, "out_dir": str(out_dir.resolve())}


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("--base-model", default=DEFAULT_BASE_MODEL)
    parser.add_argument("--dataset", type=Path, default=None,
                        help="Path to a rendered dataset dir (labels.jsonl + dpo_pairs.jsonl).")
    parser.add_argument("--demo", action="store_true",
                        help="Generate a fresh synthetic dataset via C3+renderer, then train.")
    parser.add_argument("--demo-count", type=int, default=60,
                        help="Number of physics profiles to synthesise when --demo.")
    parser.add_argument("--demo-variants", type=int, default=8,
                        help="Rendered variants per physics profile when --demo.")
    parser.add_argument("--out", type=Path, default=Path("adapters/luxshare_aoi"))
    parser.add_argument("--sft-epochs", type=int, default=3)
    parser.add_argument("--dpo-epochs", type=int, default=2)
    parser.add_argument("--batch-size", type=int, default=2)
    parser.add_argument("--lr", type=float, default=1e-4)
    parser.add_argument("--dpo-beta", type=float, default=0.1)
    parser.add_argument("--lora-rank", type=int, default=16)
    parser.add_argument("--lora-alpha", type=int, default=32)
    parser.add_argument("--lora-targets", default=",".join(DEFAULT_LORA_TARGETS))
    parser.add_argument("--device", default=None, help="cuda / cpu (default: auto).")
    parser.add_argument("--skip-sft", action="store_true")
    parser.add_argument("--skip-dpo", action="store_true")
    args = parser.parse_args()

    if args.demo and args.dataset is None:
        dataset_dir = args.out / "dataset"
        logger.info("Generating synthetic dataset at %s", dataset_dir)
        summary = generate_synthetic_dataset(
            dataset_dir, count=args.demo_count, variants=args.demo_variants, seed=11,
        )
        logger.info("Rendered %d images: %s", summary["total_images"], summary["per_defect"])
        args.dataset = dataset_dir
    if args.dataset is None:
        parser.error("Must supply --dataset PATH or --demo.")

    # Defer torch import to here so --help works on bare interpreter.
    import torch
    device = args.device or ("cuda" if torch.cuda.is_available() else "cpu")
    logger.info("Device: %s", device)

    lora_targets = [t.strip() for t in args.lora_targets.split(",") if t.strip()]
    overall_log: Dict[str, Any] = {
        "base_model": args.base_model,
        "dataset": str(args.dataset.resolve()),
        "stages": [],
    }

    sft_out = args.out / "sft"
    if not args.skip_sft:
        sft_records = load_sft_records(args.dataset)
        logger.info("SFT: %d records", len(sft_records))
        result = train_sft(
            base_model=args.base_model, records=sft_records, out_dir=sft_out,
            epochs=args.sft_epochs, batch_size=args.batch_size, lr=args.lr,
            lora_rank=args.lora_rank, lora_alpha=args.lora_alpha,
            lora_targets=lora_targets, device=device,
        )
        overall_log["stages"].append(result)

    if not args.skip_dpo:
        if not sft_out.exists():
            parser.error("DPO requires an SFT adapter. Run --skip-dpo false with SFT first, or supply one.")
        dpo_records = load_dpo_records(args.dataset)
        logger.info("DPO: %d records", len(dpo_records))
        result = train_dpo(
            base_model=args.base_model, sft_adapter=sft_out, records=dpo_records,
            out_dir=args.out / "dpo", epochs=args.dpo_epochs, batch_size=args.batch_size,
            lr=args.lr, beta=args.dpo_beta, device=device,
        )
        overall_log["stages"].append(result)

    (args.out / "train_log.json").write_text(json.dumps(overall_log, indent=2))
    logger.info("All done. Final adapter: %s", (args.out / "dpo").resolve())


if __name__ == "__main__":
    main()
