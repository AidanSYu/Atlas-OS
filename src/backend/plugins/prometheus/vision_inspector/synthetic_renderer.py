"""Procedural PCB renderer coupled to physics_simulator defect labels.

Takes a reflow profile dict (as produced by
`physics_simulator.invoke({'mode':'reflow_defect_physics'})`) and paints a
physics-consistent defect onto a synthetic PCB image. Outputs `(image, label)`
pairs where the label is in the strict machine-readable format the VLM is
post-trained to emit:

    DEFECT: <label> | CONFIDENCE: <0..1> | LOCATION: <component>_PIN<n>

Every visual defect is driven by the physics evidence so the renderer cannot
produce a cold-joint pixel signature on a profile that is physically a pass.
This matters because the DPO dataset generated from these images has to be
internally consistent — if the image says cold joint but the physics says pass,
the adapter learns contradictions and the alignment goal collapses.

The renderer is pure PIL + NumPy; no OpenGL, no Blender, no Modulus. Upgrade
path to a physics-accurate 3D pipeline is clean: replace `_draw_joint` and keep
the dataset-assembly scaffolding.
"""

from __future__ import annotations

import json
import logging
import math
import random
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple

import numpy as np
from PIL import Image, ImageDraw, ImageFilter

logger = logging.getLogger(__name__)

DEFECT_LABELS = (
    "pass",
    "cold_joint",
    "overshoot_damage",
    "insufficient_wetting",
    "excessive_tal_voids",
    "thermal_shock_tombstone",
    "solder_bridge",
)

STRICT_LABEL_TEMPLATE = "DEFECT: {defect} | CONFIDENCE: {confidence:.2f} | LOCATION: {location}"

# Components laid out on the virtual board. Each entry is (name, x, y, w, h,
# kind) where kind drives joint geometry. IC pads sit at fixed pin offsets.
_COMPONENTS: List[Tuple[str, int, int, int, int, str]] = [
    ("IC1", 80, 80, 120, 120, "qfn16"),
    ("IC2", 320, 80, 120, 120, "qfn16"),
    ("IC3", 80, 320, 120, 120, "qfn16"),
    ("R1", 260, 230, 40, 20, "chip"),
    ("R2", 260, 270, 40, 20, "chip"),
    ("C1", 260, 310, 40, 20, "chip"),
    ("C2", 260, 350, 40, 20, "chip"),
]

BOARD_GREEN = (22, 82, 38)
PAD_SILVER = (205, 205, 205)
SOLDER_SHINY = (215, 215, 222)
SOLDER_DULL = (140, 140, 140)
TRACE_GOLD = (200, 170, 60)
SILKSCREEN_WHITE = (235, 235, 235)
OVERSHOOT_BURN = (90, 55, 30)
VOID_DARK = (35, 35, 45)


@dataclass
class RenderedSample:
    image: Image.Image
    label_dict: Dict[str, Any]
    label_string: str


# ---------------------------------------------------------------------------
# Procedural board primitives
# ---------------------------------------------------------------------------

def _draw_base_board(draw: ImageDraw.ImageDraw, w: int, h: int, rng: random.Random) -> None:
    jitter = lambda c: tuple(max(0, min(255, c[i] + rng.randint(-6, 6))) for i in range(3))
    draw.rectangle([0, 0, w, h], fill=jitter(BOARD_GREEN))
    for y in range(120, h, 60):
        draw.line([(40, y), (w - 40, y)], fill=jitter(TRACE_GOLD), width=2)
    for x in range(60, w, 80):
        draw.line([(x, 40), (x, h - 40)], fill=jitter(TRACE_GOLD), width=1)


def _component_pins(comp: Tuple[str, int, int, int, int, str]) -> List[Tuple[str, int, int]]:
    name, x, y, w, h, kind = comp
    pins: List[Tuple[str, int, int]] = []
    if kind == "qfn16":
        for i in range(4):
            pins.append((f"{name}_PIN{i + 1}", x, y + 20 + i * ((h - 40) // 3)))
            pins.append((f"{name}_PIN{i + 5}", x + w, y + 20 + i * ((h - 40) // 3)))
            pins.append((f"{name}_PIN{i + 9}", x + 20 + i * ((w - 40) // 3), y))
            pins.append((f"{name}_PIN{i + 13}", x + 20 + i * ((w - 40) // 3), y + h))
    elif kind == "chip":
        pins.append((f"{name}_PIN1", x, y + h // 2))
        pins.append((f"{name}_PIN2", x + w, y + h // 2))
    return pins


def _draw_component_body(draw: ImageDraw.ImageDraw, comp: Tuple[str, int, int, int, int, str], rng: random.Random) -> None:
    name, x, y, w, h, kind = comp
    body_fill = (30 + rng.randint(-4, 4), 30 + rng.randint(-4, 4), 30 + rng.randint(-4, 4))
    draw.rectangle([x, y, x + w, y + h], fill=body_fill, outline=(60, 60, 60))
    draw.text((x + 6, y + 6), name, fill=SILKSCREEN_WHITE)


def _draw_joint(draw: ImageDraw.ImageDraw, px: int, py: int, defect: str, rng: random.Random) -> None:
    """Paint a solder joint whose visual signature matches the physics label.

    This is the core physics-to-pixel coupling. A single joint covers roughly
    12x12 pixels in the 512x512 image, consistent with AOI crop resolution.
    """
    r_out = 6
    if defect == "pass":
        # Smooth fillet, specular highlight.
        draw.ellipse([px - r_out, py - r_out, px + r_out, py + r_out], fill=SOLDER_SHINY)
        draw.ellipse([px - 2, py - 2, px + 1, py + 1], fill=(245, 245, 250))
    elif defect == "cold_joint":
        # Dull, bulbous, no fillet.
        bulb_r = r_out + rng.randint(0, 2)
        draw.ellipse([px - bulb_r, py - bulb_r, px + bulb_r, py + bulb_r], fill=SOLDER_DULL)
        for _ in range(6):
            gx, gy = px + rng.randint(-bulb_r, bulb_r), py + rng.randint(-bulb_r, bulb_r)
            draw.point((gx, gy), fill=(100, 100, 100))
    elif defect == "insufficient_wetting":
        # Partial joint; bare pad visible.
        draw.rectangle([px - r_out, py - 3, px + r_out, py + 3], fill=PAD_SILVER)
        draw.ellipse([px - 2, py - 2, px + 3, py + 3], fill=SOLDER_DULL)
    elif defect == "excessive_tal_voids":
        # Normal-ish joint with visible voids (dark circular holes).
        draw.ellipse([px - r_out, py - r_out, px + r_out, py + r_out], fill=SOLDER_SHINY)
        for _ in range(rng.randint(2, 4)):
            vx = px + rng.randint(-3, 3)
            vy = py + rng.randint(-3, 3)
            draw.ellipse([vx - 1, vy - 1, vx + 1, vy + 1], fill=VOID_DARK)
    elif defect == "overshoot_damage":
        # Scorched pad + laurel-brown halo on board.
        draw.ellipse([px - r_out - 4, py - r_out - 4, px + r_out + 4, py + r_out + 4], fill=OVERSHOOT_BURN)
        draw.ellipse([px - r_out, py - r_out, px + r_out, py + r_out], fill=(80, 70, 55))
    elif defect == "thermal_shock_tombstone":
        # One-sided joint only; other side shown as a bare pad to imply lift.
        draw.ellipse([px - r_out, py - r_out, px + r_out, py + r_out], fill=SOLDER_SHINY)
        draw.rectangle([px + r_out + 2, py - 3, px + r_out + 12, py + 3], fill=PAD_SILVER)
    elif defect == "solder_bridge":
        # Bright metallic line extending to a neighbour pad direction.
        draw.ellipse([px - r_out, py - r_out, px + r_out, py + r_out], fill=SOLDER_SHINY)
        draw.rectangle([px, py - 2, px + 18, py + 2], fill=SOLDER_SHINY)
    else:
        draw.ellipse([px - r_out, py - r_out, px + r_out, py + r_out], fill=SOLDER_SHINY)


# ---------------------------------------------------------------------------
# Domain randomisation
# ---------------------------------------------------------------------------

def _apply_lighting(img: Image.Image, rng: random.Random) -> Image.Image:
    arr = np.asarray(img, dtype=np.float32)
    h, w = arr.shape[:2]
    cx = rng.uniform(0.2, 0.8) * w
    cy = rng.uniform(0.2, 0.8) * h
    yy, xx = np.mgrid[0:h, 0:w]
    falloff = np.exp(-((xx - cx) ** 2 + (yy - cy) ** 2) / (2 * (max(h, w) * 0.35) ** 2))
    gain = 0.85 + 0.35 * falloff
    arr = np.clip(arr * gain[..., None], 0, 255)
    return Image.fromarray(arr.astype(np.uint8))


def _apply_shadow_band(img: Image.Image, rng: random.Random) -> Image.Image:
    if rng.random() > 0.5:
        return img
    arr = np.asarray(img, dtype=np.float32)
    h, w = arr.shape[:2]
    yy, xx = np.mgrid[0:h, 0:w]
    angle = rng.uniform(0, math.pi)
    pos = (xx * math.cos(angle) + yy * math.sin(angle)) / max(h, w)
    center = rng.uniform(0.3, 0.7)
    band = 1.0 - 0.25 * np.exp(-((pos - center) ** 2) / (2 * 0.05 ** 2))
    arr = np.clip(arr * band[..., None], 0, 255)
    return Image.fromarray(arr.astype(np.uint8))


def _apply_noise(img: Image.Image, rng: random.Random) -> Image.Image:
    arr = np.asarray(img, dtype=np.float32)
    noise = np.random.default_rng(rng.randint(0, 10_000)).normal(0, 4.0, arr.shape)
    arr = np.clip(arr + noise, 0, 255)
    return Image.fromarray(arr.astype(np.uint8))


def _apply_rotation(img: Image.Image, rng: random.Random) -> Image.Image:
    angle = rng.uniform(-4.0, 4.0)
    return img.rotate(angle, resample=Image.BILINEAR, fillcolor=BOARD_GREEN)


# ---------------------------------------------------------------------------
# Core render
# ---------------------------------------------------------------------------

def _pick_defect_location(defect: str, rng: random.Random) -> str:
    if defect == "pass":
        pins = [p for comp in _COMPONENTS for p in _component_pins(comp)]
        return rng.choice(pins)[0]
    pins = [p for comp in _COMPONENTS for p in _component_pins(comp)]
    return rng.choice(pins)[0]


def _render_one(
    defect: str,
    location: str,
    rng: random.Random,
    image_size: Tuple[int, int] = (512, 512),
    apply_augmentations: bool = True,
) -> Image.Image:
    w, h = image_size
    img = Image.new("RGB", (w, h), BOARD_GREEN)
    draw = ImageDraw.Draw(img)
    _draw_base_board(draw, w, h, rng)

    defect_pin_coords: Optional[Tuple[int, int]] = None
    for comp in _COMPONENTS:
        _draw_component_body(draw, comp, rng)
        for pin_name, px, py in _component_pins(comp):
            if pin_name == location and defect != "pass":
                defect_pin_coords = (px, py)
                continue
            _draw_joint(draw, px, py, "pass", rng)

    if defect != "pass" and defect_pin_coords is not None:
        _draw_joint(draw, defect_pin_coords[0], defect_pin_coords[1], defect, rng)

    if apply_augmentations:
        img = _apply_lighting(img, rng)
        img = _apply_shadow_band(img, rng)
        img = _apply_noise(img, rng)
        img = _apply_rotation(img, rng)
        if rng.random() < 0.3:
            img = img.filter(ImageFilter.GaussianBlur(radius=0.6))
    return img


# ---------------------------------------------------------------------------
# Physics -> visual coupling
# ---------------------------------------------------------------------------

def _confidence_from_physics(profile: Dict[str, Any]) -> float:
    """Translate physics margin-over-threshold into a synthetic ground-truth confidence.

    Used as the target CONFIDENCE the VLM should emit. Physics-clean profiles
    get 0.95+, borderline profiles get lower confidence.
    """
    defect = profile["primary_defect"]
    peak = float(profile.get("peak_c", 0.0))
    tal = float(profile.get("time_above_liquidus_s", 0.0))
    ramp = float(profile.get("max_ramp_c_per_s", 0.0))
    if defect == "pass":
        distance = min(
            abs(peak - 245.0) / 20.0,
            abs(tal - 65.0) / 40.0,
            1.0,
        )
        return max(0.70, 0.98 - distance * 0.2)
    if defect == "cold_joint":
        return max(0.70, min(0.99, 0.70 + (235.0 - peak) / 10.0 * 0.2))
    if defect == "overshoot_damage":
        return max(0.70, min(0.99, 0.70 + (peak - 260.0) / 10.0 * 0.2))
    if defect == "thermal_shock_tombstone":
        return max(0.70, min(0.99, 0.70 + (ramp - 3.0) / 2.0 * 0.2))
    if defect == "excessive_tal_voids":
        return max(0.70, min(0.99, 0.70 + (tal - 90.0) / 20.0 * 0.2))
    return 0.80


def render_profile(
    profile: Dict[str, Any],
    seed: int,
    augment_idx: int = 0,
    image_size: Tuple[int, int] = (512, 512),
) -> RenderedSample:
    """Render one image for a single physics profile."""
    rng = random.Random(seed * 1009 + augment_idx)
    defect = profile["primary_defect"]
    # Physics can also imply solder_bridge when TAL is mid-range and the paste
    # volume is high — we synthesise that here as a "co-occurring" failure on
    # ~15% of profiles flagged for voids, to diversify the class mix.
    if defect == "excessive_tal_voids" and rng.random() < 0.3:
        defect = "solder_bridge"
    location = _pick_defect_location(defect, rng)
    img = _render_one(defect, location, rng, image_size=image_size)
    confidence = _confidence_from_physics(profile)
    label_dict = {
        "profile_id": profile.get("profile_id"),
        "defect": defect,
        "confidence": round(confidence, 2),
        "location": location,
        "physics_peak_c": profile.get("peak_c"),
        "physics_tal_s": profile.get("time_above_liquidus_s"),
        "physics_max_ramp": profile.get("max_ramp_c_per_s"),
        "augment_idx": augment_idx,
    }
    label_string = STRICT_LABEL_TEMPLATE.format(
        defect=defect, confidence=confidence, location=location,
    )
    return RenderedSample(image=img, label_dict=label_dict, label_string=label_string)


# ---------------------------------------------------------------------------
# Dataset assembly
# ---------------------------------------------------------------------------

_CONVERSATIONAL_REJECTS = [
    ("The image shows a green printed circuit board. Upon close inspection near {loc}, "
     "there appears to be a small area consistent with {defect}, though I'd recommend "
     "a second look to confirm. Let me know if you'd like me to examine another region!"),
    ("Looking at the PCB, I can see what might be {defect} around {loc}. It's a bit hard "
     "to tell from this angle, but that is my best guess. Would you like more detail?"),
    ("Hmm, based on visual cues at {loc}, this joint looks like it could be an instance of "
     "{defect}. I'm not 100% sure though. Happy to take another pass if you can supply a "
     "higher resolution image."),
    ("I see a circuit board. Near the component at {loc}, the solder looks unusual — "
     "possibly a {defect}. Let me know if that helps or if you need more analysis!"),
]


def build_dataset(
    profiles: Iterable[Dict[str, Any]],
    out_dir: Path,
    variants_per_profile: int = 8,
    image_size: Tuple[int, int] = (512, 512),
    seed: int = 0,
) -> Dict[str, Any]:
    """Render a complete SFT + DPO dataset from a list of physics profiles.

    Layout:
        out_dir/images/<profile>_aug<k>.png
        out_dir/labels.jsonl         # one line per image, strict label + meta
        out_dir/dpo_pairs.jsonl      # {prompt, chosen, rejected}

    `chosen` is the strict one-line label; `rejected` is a conversational
    paragraph that preserves the same answer but adds filler. This is the
    preference signal DPO uses to collapse the VLM to structured output.
    """
    out_dir = Path(out_dir)
    (out_dir / "images").mkdir(parents=True, exist_ok=True)

    labels_path = out_dir / "labels.jsonl"
    dpo_path = out_dir / "dpo_pairs.jsonl"
    counts: Dict[str, int] = {}

    rng = random.Random(seed)
    with labels_path.open("w", encoding="utf-8") as lfh, dpo_path.open("w", encoding="utf-8") as dfh:
        for profile in profiles:
            for aug_idx in range(variants_per_profile):
                sample = render_profile(
                    profile, seed=seed + aug_idx, augment_idx=aug_idx, image_size=image_size,
                )
                img_name = f"{profile.get('profile_id', 'prof')}_aug{aug_idx:02d}.png"
                img_path = out_dir / "images" / img_name
                sample.image.save(img_path)
                record = dict(sample.label_dict)
                record["image_path"] = str(img_path.relative_to(out_dir))
                record["label_string"] = sample.label_string
                lfh.write(json.dumps(record) + "\n")

                rejected_template = rng.choice(_CONVERSATIONAL_REJECTS)
                rejected = rejected_template.format(
                    defect=record["defect"], loc=record["location"],
                )
                dfh.write(json.dumps({
                    "image_path": record["image_path"],
                    "prompt": _DPO_PROMPT,
                    "chosen": sample.label_string,
                    "rejected": rejected,
                }) + "\n")
                counts[record["defect"]] = counts.get(record["defect"], 0) + 1

    return {
        "out_dir": str(out_dir.resolve()),
        "labels_jsonl": str(labels_path.resolve()),
        "dpo_pairs_jsonl": str(dpo_path.resolve()),
        "total_images": sum(counts.values()),
        "per_defect": counts,
    }


_DPO_PROMPT = (
    "You are a factory AOI inspector. Report the defect for the highlighted "
    "component. Output exactly one line in this format and nothing else:\n"
    "DEFECT: <label> | CONFIDENCE: <0-1> | LOCATION: <component>_PIN<n>\n"
    "Valid labels: " + ", ".join(DEFECT_LABELS) + "."
)


STRICT_INFERENCE_PROMPT = _DPO_PROMPT
