"""Decode SAM 3.1 segmentation output from Meta's Model API.

The API answers with one text line per frame: `<0f>` followed by comma-separated records, each an
object id, a box token and a mask token:

    <0f>0<|box;x1=..;y1=..;x2=..;y2=..;w=W;h=H;c=..|><|mask;x=0;y=0;c=..;data=ROWS,COLS,!payload|>

The mask is a raster of ROWS x COLS cells over the object's box (about one cell per pixel; for an
object that fills the frame, a scaled-down raster of the whole image). This module
decodes the `one_bit` encoding (requested with metadata.mask_encoding = "one_bit"): a context-modelled
binary range code, packed in a base85 variant.

The decoder is a Python port of `decodeRaster` and `unpack` in Meta's `@meta-sam/parser` 0.1.0
(dist/mask-codec.js), Copyright (c) Meta Platforms, Inc. and affiliates, distributed under the SAM
License (docs/licenses/SAM_LICENSE).
"""
from __future__ import annotations

import re
from dataclasses import dataclass

import numpy as np

_EXCLUDED = set('"\\,;<>|')
_ALPHABET = "".join(chr(c) for c in range(0x21, 0x7F) if chr(c) not in _EXCLUDED)
_VALUES = {ch: i for i, ch in enumerate(_ALPHABET)}
_RADIX, _PREFIX = 85, 5
_TOP, _BOTTOM, _MASK32 = 1 << 24, 1 << 16, 0xFFFFFFFF
_INCREMENT, _COUNT_LIMIT, _CONTEXTS, _PAD = 14, 4096, 1 << 12, 2


class SamMaskError(ValueError):
    pass


def _unpack(payload: str) -> bytes:
    if len(payload) < _PREFIX:
        raise SamMaskError("Mask payload is missing its length prefix.")
    try:
        digits = [_VALUES[ch] for ch in payload]
    except KeyError as e:
        raise SamMaskError("Mask payload contains an invalid character.") from e
    length = 0
    for d in digits[:_PREFIX]:
        length = length * _RADIX + d
    rem = length % 4
    if len(payload) != _PREFIX + (length // 4) * 5 + (rem + 1 if rem else 0):
        raise SamMaskError("Mask payload length does not match its prefix.")
    out = bytearray()
    src = _PREFIX
    for _ in range(length // 4):
        v = 0
        for d in digits[src:src + 5]:
            v = v * _RADIX + d
        if v > _MASK32:
            raise SamMaskError("Mask payload contains an out-of-range group.")
        out += v.to_bytes(4, "big")
        src += 5
    if rem:
        v = 0
        for i in range(5):
            v = v * _RADIX + (digits[src + i] if i < rem + 1 else _RADIX - 1)
        out += v.to_bytes(4, "big")[:rem]
    return bytes(out)


def decode_one_bit(payload: str, width: int, height: int) -> np.ndarray:
    """Raster (height x width) of 0/1 from a `!`-prefixed one_bit payload."""
    if not payload.startswith("!"):
        raise SamMaskError("one_bit mask payloads must start with !.")
    data = _unpack(payload[1:])
    if len(data) < 4:
        raise SamMaskError("Mask payload is missing its finalization.")
    pos = 4
    code = int.from_bytes(data[:4], "big")
    low, rng = 0, _MASK32
    counts = [1] * (_CONTEXTS * 2)
    pw = width + 2 * _PAD
    padded = bytearray(pw * (height + _PAD))
    out = np.zeros((height, width), dtype=np.uint8)
    for y in range(height):
        row = (y + _PAD) * pw + _PAD
        for x in range(width):
            p = row + x
            q = p - pw
            e = p - 2 * pw
            ctx = (padded[p - 1] | (padded[p - 2] << 1) | (padded[q - 2] << 2) | (padded[q - 1] << 3)
                   | (padded[q] << 4) | (padded[q + 1] << 5) | (padded[q + 2] << 6) | (padded[e - 2] << 7)
                   | (padded[e - 1] << 8) | (padded[e] << 9) | (padded[e + 1] << 10) | (padded[e + 2] << 11))
            off = ctx << 1
            zero, one = counts[off], counts[off + 1]
            scaled = rng // (zero + one)
            if scaled == 0:
                raise SamMaskError("Mask payload has invalid coding state.")
            value = ((code - low) & _MASK32) // scaled
            bit = 0 if value < zero else 1
            cum, freq = (0, zero) if bit == 0 else (zero, one)
            low = (low + scaled * cum) & _MASK32
            rng = scaled * freq
            while True:
                if ((low ^ (low + rng)) & _MASK32) >= _TOP:
                    if rng >= _BOTTOM:
                        break
                    rng = (-low & _MASK32) & (_BOTTOM - 1)
                if pos >= len(data):
                    raise SamMaskError("Mask payload ended before decoding completed.")
                code = ((code << 8) | data[pos]) & _MASK32
                pos += 1
                low = (low << 8) & _MASK32
                rng = (rng << 8) & _MASK32
            padded[p] = bit
            if bit:
                out[y, x] = 1
            counts[off + bit] += _INCREMENT
            if counts[off] + counts[off + 1] >= _COUNT_LIMIT:
                counts[off] = counts[off] >> 1 or 1
                counts[off + 1] = counts[off + 1] >> 1 or 1
    return out


@dataclass
class SamObject:
    object_id: int
    box: tuple[int, int, int, int]     # x1, y1, x2, y2 in image pixels
    image_size: tuple[int, int]        # width, height of the image
    confidence: float | None
    mask: np.ndarray                   # raster rows x cols, 0/1, covering the box

    def on_image(self) -> np.ndarray:
        """The mask on the image's pixel grid (height x width, bool), stretched over the box."""
        w, h = self.image_size
        x1, y1, x2, y2 = self.box
        bw, bh = x2 - x1 + 1, y2 - y1 + 1
        rows = (np.arange(bh) * self.mask.shape[0] // bh).clip(0, self.mask.shape[0] - 1)
        cols = (np.arange(bw) * self.mask.shape[1] // bw).clip(0, self.mask.shape[1] - 1)
        full = np.zeros((h, w), dtype=bool)
        full[y1:y1 + bh, x1:x1 + bw] = self.mask[np.ix_(rows, cols)].astype(bool)[: h - y1, : w - x1]
        return full

    @property
    def share_of_image(self) -> float:
        """Fraction of the image covered by the mask."""
        return float(self.on_image().mean())


_RECORD = re.compile(r"(\d+)<\|box;([^|]*)\|><\|mask;([^|]*)\|>")


def _fields(token: str) -> dict[str, str]:
    out = {}
    for part in token.split(";"):
        if "=" in part:
            k, v = part.split("=", 1)
            out[k] = v
    return out


def parse_image_output(text: str) -> list[SamObject]:
    """Every object SAM found in one image. An empty text means no matches."""
    objects = []
    for m in _RECORD.finditer(text or ""):
        box, mask = _fields(m.group(2)), _fields(m.group(3))
        rows, cols, payload = mask["data"].split(",", 2)
        if not payload.startswith("!"):
            raise SamMaskError("Request masks with metadata.mask_encoding = 'one_bit'.")
        objects.append(SamObject(
            object_id=int(m.group(1)),
            box=(int(box["x1"]), int(box["y1"]), int(box["x2"]), int(box["y2"])),
            image_size=(int(box["w"]), int(box["h"])),
            confidence=float(box["c"]) if "c" in box else None,
            mask=decode_one_bit(payload, int(cols), int(rows)),
        ))
    return objects


def union_share(objects: list[SamObject]) -> float:
    """Fraction of the image covered by any of the objects (overlaps counted once)."""
    if not objects:
        return 0.0
    return float(union_mask(objects).mean())


def union_mask(objects: list[SamObject]) -> np.ndarray:
    """Pixels of the image covered by any of the objects (bool, height x width)."""
    w, h = objects[0].image_size
    union = np.zeros((h, w), dtype=bool)
    for o in objects:
        if o.image_size != (w, h):
            raise SamMaskError("Objects of one image report different image sizes.")
        union |= o.on_image()
    return union
