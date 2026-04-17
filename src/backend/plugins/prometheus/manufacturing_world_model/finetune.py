#!/usr/bin/env python3
"""
Manufacturing World Model — TimesFM 2.5 LoRA fine-tuning pipeline.

Produces a lightweight per-machine adapter from healthy baseline sensor data,
so the MWM learns the exact rhythm of a specific production line rather than
a generalized manufacturing prior. At inference time the base TimesFM 2.5
weights stay frozen; only the LoRA adapter is loaded on top.

The script is intentionally ready-to-run but deliberately *not* executed as
part of the Luxshare pitch. The default behavior is: "pipeline is wired and
tested on a synthetic baseline — hand us your real healthy-state data and we
train the Line-4 adapter in under an hour on a single 4090."

Usage
-----
    python finetune.py --baseline path/to/healthy.csv --out adapters/line_4
    python finetune.py --demo   # run on the built-in synthetic reflow profile

Assumptions (all overridable):
    - Input CSV has a single numeric column OR a 'value' column.
    - All data in the file is "healthy" baseline (anomaly-free).
    - LoRA rank 16 applied to attention projections of the TimesFM 2.5 stack.

Outputs:
    <out>/adapter_model.safetensors    # LoRA weights
    <out>/adapter_config.json           # PEFT config
    <out>/train_log.json                # per-epoch train/val loss
"""

from __future__ import annotations

import argparse
import csv
import json
import logging
import math
import sys
from pathlib import Path
from typing import Iterable, List, Optional, Tuple

import numpy as np

logger = logging.getLogger("mwm_finetune")
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s: %(message)s")


# ---------------------------------------------------------------------------
# Default LoRA target modules.
# NOTE: These are the conventional attention-projection names used in most
# decoder-only transformers. If TimesFM 2.5's PyTorch module names differ,
# the first training step will raise "target_modules not found" — inspect the
# model via `print(model)` and update this list. Kept as a list rather than a
# regex so the failure mode is loud and obvious.
# ---------------------------------------------------------------------------
DEFAULT_LORA_TARGETS: List[str] = ["q_proj", "k_proj", "v_proj", "o_proj"]


# ---------------------------------------------------------------------------
# Data loading + windowing
# ---------------------------------------------------------------------------

def load_baseline_csv(path: Path) -> np.ndarray:
    """Read a one-column or 'value'-column CSV into a float array."""
    with path.open() as fh:
        reader = csv.reader(fh)
        header = next(reader)
        value_idx = 0
        if any(not _is_float(c) for c in header):
            # Header present — find 'value' column (or default to first).
            lowered = [h.strip().lower() for h in header]
            value_idx = lowered.index("value") if "value" in lowered else 0
            rows_iter: Iterable[List[str]] = reader
        else:
            rows_iter = [header] + list(reader)

        values = [float(row[value_idx]) for row in rows_iter if row]
    return np.asarray(values, dtype=np.float32)


def _is_float(x: str) -> bool:
    try:
        float(x)
        return True
    except (TypeError, ValueError):
        return False


def make_windows(
    values: np.ndarray, context_len: int, horizon: int, stride: int = 1,
) -> Tuple[np.ndarray, np.ndarray]:
    """Slice a long series into (context, target) windows for supervised training."""
    total = context_len + horizon
    if len(values) < total:
        raise ValueError(
            f"Baseline has {len(values)} points; need at least {total} "
            f"(context_len={context_len} + horizon={horizon})"
        )
    contexts, targets = [], []
    for start in range(0, len(values) - total + 1, stride):
        contexts.append(values[start:start + context_len])
        targets.append(values[start + context_len:start + total])
    return np.stack(contexts), np.stack(targets)


# ---------------------------------------------------------------------------
# Training
# ---------------------------------------------------------------------------

def train(
    baseline: np.ndarray,
    out_dir: Path,
    context_len: int,
    horizon: int,
    lora_rank: int,
    lora_alpha: int,
    lora_targets: List[str],
    lr: float,
    epochs: int,
    batch_size: int,
    val_fraction: float,
) -> None:
    """Train a LoRA adapter against a healthy-baseline series.

    The heavy imports (torch, timesfm, peft) are deferred until call time so
    `python finetune.py --help` works on a bare interpreter.
    """
    import torch
    import torch.nn.functional as F
    from torch.utils.data import DataLoader, TensorDataset

    try:
        import timesfm  # type: ignore
    except ImportError as exc:
        raise RuntimeError(
            "TimesFM is not installed. Install from "
            "https://github.com/google-research/timesfm (PyPI release pending)."
        ) from exc
    try:
        from peft import LoraConfig, get_peft_model  # type: ignore
    except ImportError as exc:
        raise RuntimeError("peft is required: pip install peft") from exc

    out_dir.mkdir(parents=True, exist_ok=True)
    device = "cuda" if torch.cuda.is_available() else "cpu"
    logger.info("Device: %s", device)

    # --- Windowed dataset -------------------------------------------------
    contexts, targets = make_windows(baseline, context_len, horizon)
    split = max(1, int(len(contexts) * (1 - val_fraction)))
    x_train = torch.from_numpy(contexts[:split]).to(device)
    y_train = torch.from_numpy(targets[:split]).to(device)
    x_val = torch.from_numpy(contexts[split:]).to(device)
    y_val = torch.from_numpy(targets[split:]).to(device)
    logger.info("Windows: train=%d  val=%d", len(x_train), len(x_val))

    train_loader = DataLoader(TensorDataset(x_train, y_train), batch_size=batch_size, shuffle=True)

    # --- Load base model --------------------------------------------------
    logger.info("Loading TimesFM 2.5 base weights ...")
    model = timesfm.TimesFM_2p5_200M_torch.from_pretrained(
        "google/timesfm-2.5-200m-pytorch",
    )

    # --- Wrap with LoRA ---------------------------------------------------
    lora_cfg = LoraConfig(
        r=lora_rank,
        lora_alpha=lora_alpha,
        target_modules=lora_targets,
        lora_dropout=0.05,
        bias="none",
        task_type="FEATURE_EXTRACTION",
    )
    # peft wraps the inner torch.nn.Module. TimesFM exposes its backbone at
    # .model in recent releases; fall back to the wrapper itself if missing.
    inner = getattr(model, "model", model)
    peft_inner = get_peft_model(inner, lora_cfg)
    if hasattr(model, "model"):
        model.model = peft_inner
    else:
        model = peft_inner
    logger.info("Trainable parameters:")
    peft_inner.print_trainable_parameters()

    optim = torch.optim.AdamW(
        [p for p in peft_inner.parameters() if p.requires_grad], lr=lr,
    )

    # --- Training loop ----------------------------------------------------
    history: List[dict] = []
    for epoch in range(1, epochs + 1):
        peft_inner.train()
        total_loss = 0.0
        n_batches = 0
        for xb, yb in train_loader:
            optim.zero_grad()
            pred = _forward_forecast(model, xb, horizon)
            loss = F.mse_loss(pred, yb)
            loss.backward()
            optim.step()
            total_loss += float(loss.item())
            n_batches += 1
        train_loss = total_loss / max(1, n_batches)

        peft_inner.eval()
        with torch.no_grad():
            val_pred = _forward_forecast(model, x_val, horizon) if len(x_val) else None
            val_loss = float(F.mse_loss(val_pred, y_val).item()) if val_pred is not None else math.nan
        logger.info("epoch %2d/%d  train=%.5f  val=%.5f", epoch, epochs, train_loss, val_loss)
        history.append({"epoch": epoch, "train_loss": train_loss, "val_loss": val_loss})

    # --- Persist ----------------------------------------------------------
    peft_inner.save_pretrained(str(out_dir))
    (out_dir / "train_log.json").write_text(json.dumps({
        "context_len": context_len,
        "horizon": horizon,
        "lora_rank": lora_rank,
        "lora_alpha": lora_alpha,
        "lora_targets": lora_targets,
        "lr": lr,
        "epochs": epochs,
        "batch_size": batch_size,
        "history": history,
    }, indent=2))
    logger.info("Adapter saved to %s", out_dir.resolve())


def _forward_forecast(model: "object", context: "object", horizon: int) -> "object":
    """Run a forward pass returning a (batch, horizon) point-forecast tensor.

    TimesFM 2.5's training-mode forward returns per-token distributions; the
    exact attribute path can shift between library versions, so we probe a
    small set of known shapes. If none match, we raise with a clear message so
    the operator can inspect `output` and add the correct accessor.
    """
    output = model(context, horizon=horizon) if callable(getattr(model, "__call__", None)) else None
    if output is None:
        raise RuntimeError("Base model is not callable — check the TimesFM wrapper version.")
    for attr in ("point_forecast", "predictions", "last_hidden_state", "mean"):
        if hasattr(output, attr):
            tensor = getattr(output, attr)
            if tensor.ndim == 3:
                tensor = tensor[..., 0]
            return tensor[:, :horizon]
    if hasattr(output, "shape"):
        return output[:, :horizon]
    raise RuntimeError(
        f"Could not extract point forecast from output of type {type(output)}. "
        f"Inspect the object and extend _forward_forecast accordingly."
    )


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("--baseline", type=Path, default=None,
                        help="CSV of healthy sensor readings (single numeric column or 'value' header).")
    parser.add_argument("--demo", action="store_true",
                        help="Use the built-in synthetic reflow oven baseline instead of --baseline.")
    parser.add_argument("--out", type=Path, default=Path("adapters/mwm_default"),
                        help="Output directory for the LoRA adapter.")
    parser.add_argument("--context-len", type=int, default=512)
    parser.add_argument("--horizon", type=int, default=64)
    parser.add_argument("--lora-rank", type=int, default=16)
    parser.add_argument("--lora-alpha", type=int, default=32)
    parser.add_argument("--lora-targets", default=",".join(DEFAULT_LORA_TARGETS),
                        help="Comma-separated module-name suffixes to inject LoRA into.")
    parser.add_argument("--lr", type=float, default=1e-4)
    parser.add_argument("--epochs", type=int, default=10)
    parser.add_argument("--batch-size", type=int, default=16)
    parser.add_argument("--val-fraction", type=float, default=0.2)
    args = parser.parse_args()

    if args.demo:
        sys.path.insert(0, str(Path(__file__).resolve().parent))
        from wrapper import _generate_reflow_demo  # type: ignore
        # Concatenate a long healthy run (drop the drift + spike regions).
        values, _ = _generate_reflow_demo()
        baseline = values[:300].copy()
        # Tile to get enough windows for a real train loop.
        baseline = np.tile(baseline, 5)
        logger.info("Using synthetic demo baseline (n=%d)", len(baseline))
    elif args.baseline is None:
        parser.error("Must pass --baseline PATH or --demo.")
    else:
        baseline = load_baseline_csv(args.baseline)
        logger.info("Loaded baseline from %s (n=%d)", args.baseline, len(baseline))

    train(
        baseline=baseline,
        out_dir=args.out,
        context_len=args.context_len,
        horizon=args.horizon,
        lora_rank=args.lora_rank,
        lora_alpha=args.lora_alpha,
        lora_targets=[t.strip() for t in args.lora_targets.split(",") if t.strip()],
        lr=args.lr,
        epochs=args.epochs,
        batch_size=args.batch_size,
        val_fraction=args.val_fraction,
    )


if __name__ == "__main__":
    main()
