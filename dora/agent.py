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
- If a tool returns an error, fix the parameters and call it again; if you lack a value, ask the farmer.
- Be brief: a short plan, the key numbers, and what limits the farmer's season.
- For a tailored analysis of a specific farm, suggest contacting an operations-research specialist."""


@dataclass
class Reply:
    text: str
    verified: bool
    unsupported: list[UnsupportedNumber] = field(default_factory=list)
    tool_calls: list[dict] = field(default_factory=list)


def default_client():
    from openai import OpenAI
    return OpenAI(base_url=os.environ["DORA_API_BASE"], api_key=os.environ["DORA_API_KEY"])


class Agent:
    def __init__(self, client=None, model: str | None = None):
        self.client = client or default_client()
        self.model = model or os.environ.get("DORA_MODEL", "")
        self.messages: list[dict] = [{"role": "system", "content": SYSTEM_PROMPT}]
        self.tool_results: list[str] = []
        self.user_texts: list[str] = []

    def _complete(self):
        return self.client.chat.completions.create(model=self.model, messages=self.messages, tools=TOOL_SCHEMAS)

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
                result = run_tool(tc.function.name, tc.function.arguments)
                self.tool_results.append(result)
                calls_log.append({"tool": tc.function.name, "arguments": tc.function.arguments,
                                  "error": "error" in json.loads(result)})
                self.messages.append({"role": "tool", "tool_call_id": tc.id, "content": result})
        raise RuntimeError(f"The model kept calling tools for {MAX_TOOL_ROUNDS} rounds without answering.")

    def ask(self, text: str) -> Reply:
        self.user_texts.append(text)
        self.messages.append({"role": "user", "content": text})
        calls: list[dict] = []
        answer = self._answer(calls)
        for _ in range(MAX_CORRECTIONS):
            problems = verify(answer, self.tool_results, self.user_texts)
            if not problems:
                return Reply(answer, True, [], calls)
            self.messages.append({"role": "user", "content": correction_message(problems)})
            answer = self._answer(calls)
        problems = verify(answer, self.tool_results, self.user_texts)
        return Reply(answer, not problems, problems, calls)
