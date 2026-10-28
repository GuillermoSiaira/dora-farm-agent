"""SPEC-18: aerial photo of the field -> SAM 3.1 -> hectares affected -> re-planned season. No network:
the SAM answers are recorded outputs of the real API (tests/fixtures/sam), for two public-domain FEMA
aerial photos (Canton, Missouri, 2008 flood; wet farmland in Wisconsin), both 1280 px wide."""
import base64
import json
from io import BytesIO
from pathlib import Path

import numpy as np
import pytest
from PIL import Image

from dora.agent import Agent
from dora.field_image import measure_damage
from dora.sam_mask import SamMaskError, decode_one_bit, parse_image_output, union_share
from dora.tools import assess_field_image, run_tool

FIX = Path(__file__).parent / "fixtures" / "sam"
MISSOURI = (FIX / "missouri_flood_water.txt").read_text()
WISCONSIN = (FIX / "wisconsin_puddle.txt").read_text()


def _blank_photo(w=1280, h=852) -> str:
    buf = BytesIO()
    Image.new("RGB", (w, h), (90, 120, 70)).save(buf, "PNG")
    return "data:image/png;base64," + base64.b64encode(buf.getvalue()).decode()


def _segmenter(answers: dict):
    calls = []

    def seg(image_data_url, concept):
        calls.append(concept)
        return answers.get(concept, "")
    seg.calls = calls
    return seg


# 1. The one_bit decoder reproduces what the API drew (shares checked against the overlays by eye).
def test_decoder_on_recorded_outputs():
    flood = parse_image_output(MISSOURI)
    assert len(flood) == 1 and flood[0].mask.shape == (678, 1024)
    assert union_share(flood) == pytest.approx(0.7518, abs=0.001)
    ponds = parse_image_output(WISCONSIN)
    assert len(ponds) == 16
    assert all(o.image_size == (1280, 850) for o in ponds)
    assert union_share(ponds) == pytest.approx(0.0296, abs=0.0005)


def test_mask_sits_on_its_box():
    ponds = parse_image_output(WISCONSIN)
    big = max(ponds, key=lambda o: (o.box[2] - o.box[0]) * (o.box[3] - o.box[1]))
    full = big.on_image()
    ys, xs = np.nonzero(full)
    x1, y1, x2, y2 = big.box
    assert xs.min() >= x1 and xs.max() <= x2 and ys.min() >= y1 and ys.max() <= y2


def test_empty_output_and_bad_payload():
    assert parse_image_output("") == []
    with pytest.raises(SamMaskError):
        decode_one_bit("~abc", 2, 2)
    with pytest.raises(SamMaskError):
        decode_one_bit("!!!!!$", 4, 4)   # length prefix 0... then a stray character


# 2. Damage measurement unions the concepts and counts overlaps once.
def test_measure_damage_unions_concepts():
    seg = _segmenter({"flood water": MISSOURI, "puddle": MISSOURI})
    m = measure_damage(_blank_photo(), "flooding", segmenter=seg)
    assert seg.calls == ["flood water", "puddle"]
    assert m["share"] == pytest.approx(0.7518, abs=0.001)
    assert m["objects"] == 2


# 3. The tool: hectares affected, same hectares sown, lower value, and a red overlay of the right size.
def test_assess_field_image_replans_with_sown_hectares():
    photo = _blank_photo(1280, 850)
    out = assess_field_image({"area_ha": 500}, _images=[photo], _segmenter=_segmenter({"puddle": WISCONSIN}))
    assert out["affected_share"] == pytest.approx(0.0296, abs=0.0005)
    assert out["affected_ha"] == pytest.approx(500 * out["affected_share"], abs=0.1)
    for c, h in out["before"]["hectares"].items():
        assert out["after"]["hectares"][c] == pytest.approx(h, abs=0.1)
        assert out["yield_t_ha_after"][c] == pytest.approx(out["yield_t_ha_before"][c] * (1 - out["affected_share"]), abs=0.01)
    assert out["npv_change_usd"] < 0
    overlay = Image.open(out["overlay_path"])
    assert overlay.size == (1280, 850)


def test_no_damage_found_changes_nothing():
    out = assess_field_image({"area_ha": 500}, _images=[_blank_photo()], _segmenter=_segmenter({}))
    assert out["affected_ha"] == 0.0
    assert out["npv_change_usd"] == pytest.approx(0.0, abs=1.0)
    assert "overlay_path" not in out


def test_partial_loss_share():
    seg = _segmenter({"flood water": MISSOURI})
    full = assess_field_image({"area_ha": 500}, _images=[_blank_photo()], _segmenter=seg)
    half = assess_field_image({"area_ha": 500}, loss_share=0.5, _images=[_blank_photo()], _segmenter=seg)
    assert full["npv_change_usd"] < half["npv_change_usd"] < 0
    # Three quarters of the field lost: the season needs credit beyond the farmer's 100,000 line.
    assert full["extra_credit_needed_usd"] > 0
    assert full["after"]["max_credit_usd"] == pytest.approx(100_000 + full["extra_credit_needed_usd"], abs=100)


# 4. Errors the agent can act on.
def test_errors():
    out = json.loads(run_tool("assess_field_image", {"scenario": {}}, images=[]))
    assert "photo" in out["error"]
    out = json.loads(run_tool("assess_field_image", {"scenario": {}, "image": 3}, images=[_blank_photo()]))
    assert "position" in out["error"]
    out = json.loads(run_tool("assess_field_image", {"scenario": {}, "_images": ["x"]}, images=[]))
    assert "_" in out["error"]


# 5. The agent hands the farmer's photos to the tool; the model only names which one.
def test_agent_passes_photos_to_the_tool(tmp_path, monkeypatch):
    from types import SimpleNamespace as NS
    import dora.field_image as fi
    monkeypatch.setattr(fi, "segment", _segmenter({"puddle": WISCONSIN}))
    photo_path = tmp_path / "lote.png"
    Image.new("RGB", (1280, 850), (90, 120, 70)).save(photo_path)
    call = NS(id="c1", function=NS(name="assess_field_image", arguments=json.dumps({"scenario": {"area_ha": 500}})))
    steps = [[call], "Se inundó el 3,0 % del lote."]

    class Client:
        def __init__(self):
            self.chat = NS(completions=NS(create=self.create))

        def create(self, **kw):
            step = steps.pop(0)
            msg = NS(content=None, tool_calls=step) if isinstance(step, list) else NS(content=step, tool_calls=None)
            return NS(choices=[NS(message=msg)], usage=None)

    agent = Agent(client=Client(), model="test", use_verifier=False)
    agent.ask("Mirá cómo quedó el lote", images=[str(photo_path)])
    result = json.loads(agent.tool_results[0])
    assert result["affected_share_pct"] == pytest.approx(3.0, abs=0.1)
