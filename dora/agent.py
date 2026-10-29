"""The agent loop: a Meta model that calls DORA's tools, checked by the verifier.

The model talks to the farmer, fills in scenarios and calls tools; it never
calculates. After each answer, the verifier checks every number. If a number
has no source, the model gets a correction message and rewrites the answer
(up to MAX_CORRECTIONS times). Answers that still fail are returned flagged.

Works with any OpenAI-compatible chat API (Meta's API, Baseten, Modal...),
configured with environment variables:
    DORA_API_BASE   base URL of the API
    DORA_API_KEY    API key (keep it in .env, never in the code)
    DORA_MODEL      model name
"""
from __future__ import annotations

import json
import os
from dataclasses import dataclass, field

from .schemas import TOOL_SCHEMAS
from .tools import run_tool
from .verifier import UnsupportedNumber, correction_message, verify

MAX_TOOL_ROUNDS = 8
MAX_CORRECTIONS = 2

_GUIDE_FILE = os.path.join(os.path.dirname(__file__), "modeling_guide.md")
MODELING_GUIDE = ""
if os.path.exists(_GUIDE_FILE):
    with open(_GUIDE_FILE, encoding="utf-8") as _f:
        MODELING_GUIDE = _f.read()

SYSTEM_PROMPT = """You are DORA, a crop-season planning assistant for grain farmers.
Answer in the farmer's language (Rioplatense Spanish if they write in Spanish).

How you work:
- You never calculate. Every number you give must come from a tool result or from what the farmer said.
  You may round numbers, but never add, subtract or derive new ones yourself.
- First call build_scenario with only the parameters the farmer gave, and show back what you understood,
  saying which values are the farmer's, which come from MAGyP and which are model assumptions.
- Then use evaluate_season, shadow_prices or sensitivity to answer.
- Explain shadow prices in plain words: "one more dollar of capital in September is worth X cents more
  than depositing it", "one more tonne of storage is worth nothing: storage is not your bottleneck".
- If the farmer asks about holding grain past the end of the season (e.g. soybean until the next harvest),
  say that the model ends in that month (fortnight 29; see storage.window_by_crop) and cannot evaluate it.
  Do not extrapolate.
- If a tool returns an error, fix the parameters and call it again; if you lack a value, ask the farmer.
- Be brief: a short plan, the key numbers, and what limits the farmer's season.
- When you quote a return on capital or on capital and land, always say whether it is for the 14.5-month season or for a year (*_annual_pct).
- For a tailored analysis of a specific farm, suggest contacting an operations-research specialist."""

FULL_SYSTEM_PROMPT = SYSTEM_PROMPT + ("\n\n" + MODELING_GUIDE if MODELING_GUIDE else "")


@dataclass
class Reply:
    text: str
    verified: bool
    unsupported: list[UnsupportedNumber] = field(default_factory=list)
    tool_calls: list[dict] = field(default_factory=list)
    initial_unsupported: list[UnsupportedNumber] = field(default_factory=list)
    usage: dict = field(default_factory=dict)


def default_client():
    from openai import OpenAI
    return OpenAI(base_url=os.environ["DORA_API_BASE"], api_key=os.environ["DORA_API_KEY"])


class Agent:
    def __init__(self, client=None, model: str | None = None, use_verifier: bool = True):
        self.client = client or default_client()
        self.model = model or os.environ.get("DORA_MODEL", "")
        self.use_verifier = use_verifier
        self.messages: list[dict] = [{"role": "system", "content": FULL_SYSTEM_PROMPT}]
        self.tool_results: list[str] = []
        self.user_texts: list[str] = []
        self.images: list[str] = []     # data URLs of the photos in the latest message that had any, for image tools
        self.usage = {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}

    def _complete(self):
        resp = self.client.chat.completions.create(model=self.model, messages=self.messages, tools=TOOL_SCHEMAS)
        if hasattr(resp, "usage") and resp.usage:
            self.usage["prompt_tokens"] += getattr(resp.usage, "prompt_tokens", 0) or 0
            self.usage["completion_tokens"] += getattr(resp.usage, "completion_tokens", 0) or 0
            self.usage["total_tokens"] += getattr(resp.usage, "total_tokens", 0) or 0
        return resp

    def _answer(self, calls_log: list[dict]) -> str:
        """Let the model call tools until it writes a text answer."""
        for _ in range(MAX_TOOL_ROUNDS):
            msg = self._complete().choices[0].message
            if not msg.tool_calls:
                self.messages.append({"role": "assistant", "content": msg.content or ""})
                return msg.content or ""
            self.messages.append({"role": "assistant", "content": msg.content or "", "tool_calls": [
                {"id": tc.id, "type": "function",
                 "function": {"name": tc.function.name, "arguments": tc.function.arguments}}
                for tc in msg.tool_calls]})
            for tc in msg.tool_calls:
                result = run_tool(tc.function.name, tc.function.arguments, images=self.images)
                self.tool_results.append(result)
                calls_log.append({"tool": tc.function.name, "arguments": tc.function.arguments,
                                  "error": "error" in json.loads(result)})
                self.messages.append({"role": "tool", "tool_call_id": tc.id, "content": result})
        raise RuntimeError(f"The model kept calling tools for {MAX_TOOL_ROUNDS} rounds without answering.")

    def ask(self, text: str, images: list | None = None, audio: str | None = None) -> Reply:
        from dora.media import build_user_content, transcribe

        actual_text = text or ""
        if audio:
            audio_transcript = transcribe(audio)
            if audio_transcript:
                actual_text = f"{actual_text}\n{audio_transcript}".strip() if actual_text else audio_transcript

        self.user_texts.append(actual_text)

        if images:
            from dora.media import encode_image
            self.images = [encode_image(p) for p in images]
            content = build_user_content(actual_text, images)
            self.messages.append({"role": "user", "content": content})
        else:
            self.messages.append({"role": "user", "content": actual_text})

        calls: list[dict] = []
        answer = self._answer(calls)
        initial_problems = verify(answer, self.tool_results, self.user_texts)

        if not self.use_verifier:
            return Reply(
                text=answer,
                verified=not initial_problems,
                unsupported=initial_problems,
                tool_calls=calls,
                initial_unsupported=initial_problems,
                usage=dict(self.usage),
            )

        for _ in range(MAX_CORRECTIONS):
            problems = verify(answer, self.tool_results, self.user_texts)
            if not problems:
                return Reply(
                    text=answer,
                    verified=True,
                    unsupported=[],
                    tool_calls=calls,
                    initial_unsupported=initial_problems,
                    usage=dict(self.usage),
                )
            self.messages.append({"role": "user", "content": correction_message(problems)})
            answer = self._answer(calls)
        problems = verify(answer, self.tool_results, self.user_texts)
        return Reply(
            text=answer,
            verified=not problems,
            unsupported=problems,
            tool_calls=calls,
            initial_unsupported=initial_problems,
            usage=dict(self.usage),
        )
