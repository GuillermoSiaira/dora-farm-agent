"""Aerial photos of the farm, read with SAM 3.1 (Meta's segmentation model).

The farmer sends a vertical photo of the field (drone straight down, or satellite). SAM marks the
damaged area (standing water after a flood, for example); the share of the photo it covers, times
the field's hectares, gives the hectares affected. That is a measurement, not the language model's
opinion, so the verifier can trace it. The engine then re-plans the season with the hectares already
sown and the yield lost on the affected part.
"""
from __future__ import annotations

import base64
import json
import os
import tempfile
import urllib.request
from io import BytesIO

from .sam_mask import parse_image_output, union_mask

# SAM takes a short noun phrase naming one concept. Several phrases per damage, because the same
# water reads as "flood water" in a flooded plain and as "puddle" in a field with ponding.
DAMAGE_CONCEPTS = {
    "flooding": ["flood water", "puddle"],
}


def segment(image_data_url: str, concept: str) -> str:
    """Raw SAM 3.1 output for one concept in one image (Meta Model API, Responses endpoint)."""
    base = os.environ.get("DORA_API_BASE", "https://api.meta.ai/v1").rstrip("/")
    body = {
        "model": os.environ.get("DORA_SAM_MODEL", "sam-3.1"),
        "input": [{"type": "message", "role": "user", "content": [
            {"type": "input_text", "text": concept},
            {"type": "input_image", "image_url": image_data_url}]}],
        "metadata": {"include_confidence": "true", "mask_encoding": "one_bit"},
    }
    req = urllib.request.Request(base + "/responses", data=json.dumps(body).encode(), headers={
        "Authorization": "Bearer " + os.environ["DORA_API_KEY"], "Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=180) as r:
        resp = json.load(r)
    texts = [part.get("text", "") for item in resp.get("output", []) for part in item.get("content", [])]
    return "".join(texts)


def measure_damage(image_data_url: str, damage: str = "flooding", segmenter=segment) -> dict:
    """Share of the photo covered by the damage, with the objects SAM found per concept."""
    if damage not in DAMAGE_CONCEPTS:
        raise ValueError(f"Unknown damage '{damage}'. Options: {', '.join(DAMAGE_CONCEPTS)}.")
    objects, per_concept = [], {}
    for concept in DAMAGE_CONCEPTS[damage]:
        found = parse_image_output(segmenter(image_data_url, concept))
        per_concept[concept] = len(found)
        objects += found
    if not objects:
        return {"damage": damage, "share": 0.0, "objects": 0, "objects_per_concept": per_concept, "mask": None}
    mask = union_mask(objects)
    return {"damage": damage, "share": float(mask.mean()), "objects": len(objects),
            "objects_per_concept": per_concept, "mask": mask}


def save_overlay(image_data_url: str, mask, path: str | None = None) -> str | None:
    """The photo with the damaged area in red, as a PNG next to the other temporary files."""
    if mask is None:
        return None
    try:
        from PIL import Image
    except ImportError:
        return None
    raw = base64.b64decode(image_data_url.split(",", 1)[1])
    img = Image.open(BytesIO(raw)).convert("RGB")
    if img.size != (mask.shape[1], mask.shape[0]):
        return None
    red = Image.blend(img, Image.new("RGB", img.size, (220, 30, 30)), 0.55)
    out = Image.composite(red, img, Image.fromarray((mask * 255).astype("uint8")))
    path = path or tempfile.NamedTemporaryFile(prefix="dora_damage_", suffix=".png", delete=False).name
    out.save(path)
    return path
