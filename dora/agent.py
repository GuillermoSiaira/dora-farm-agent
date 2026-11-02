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

from .schemas import ALL_TOOL_SCHEMAS, TOOL_SCHEMAS
from .tools import run_tool
from .verifier import (
    SEASON_SOLVING_TOOLS, ScenarioProblem, UnsupportedNumber, check_scenario,
    correction_message, jargon, unnamed_series, verify, fix_label_language,
)

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
- Call build_scenario with only the parameters the farmer gave. Then answer in the format of the modeling guide, section 0.
- Then use evaluate_season, shadow_prices, sensitivity, climate_outlook or climate_scenarios to answer.
- Explain shadow prices in plain words: "one more dollar of capital in September is worth X cents more
  than depositing it", "one more tonne of storage is worth nothing: storage is not your bottleneck".
- If the farmer asks about holding grain past July, follow the modeling guide (carry-over needs a quote for that month; otherwise you cannot evaluate it).
- Never change a value the farmer gave, even an impossible one (a negative area): say why it cannot be used and ask. A yield or price for one crop is not a restriction to that crop.
- If a tool returns an error, fix the parameters and call it again; if you lack a value, ask the farmer.
- Be brief: a short plan, the key numbers, and what limits the farmer's season.
- When you quote a return on capital or on capital and land, always say whether it is for the 14.5-month season or for a year (*_annual_pct).
- If the farmer asks you to ask, or accepts your offer, interview with next_question (modeling guide, section 7): one question per reply."""

FULL_SYSTEM_PROMPT = SYSTEM_PROMPT + ("\n\n" + MODELING_GUIDE if MODELING_GUIDE else "")


@dataclass
class Reply:
    text: str
    verified: bool
    unsupported: list[UnsupportedNumber] = field(default_factory=list)
    tool_calls: list[dict] = field(default_factory=list)
    initial_unsupported: list[UnsupportedNumber] = field(default_factory=list)
    usage: dict = field(default_factory=dict)
    scenario_rejections: list[ScenarioProblem] = field(default_factory=list)
    style_problems: list[str] = field(default_factory=list)
    interview: dict | None = None


def default_client():
    from openai import OpenAI
    # max_retries: a 429 or 5xx in the middle of a long eval run is retried with backoff instead of ending it
    return OpenAI(base_url=os.environ["DORA_API_BASE"], api_key=os.environ["DORA_API_KEY"], max_retries=6)


class Agent:
    def __init__(self, client=None, model: str | None = None, use_verifier: bool = True):
        self.client = client or default_client()
        self.model = model or os.environ.get("DORA_MODEL", "")
        self.use_verifier = use_verifier
        self.messages: list[dict] = [{"role": "system", "content": FULL_SYSTEM_PROMPT}]
        self.tool_results: list[str] = []
        self.user_texts: list[str] = []
        self.images: list[str] = []     # data URLs of the photos in the latest message that had any, for image tools
        self.usage = {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0, "requests": 0}
        self.screen_scenario: dict | None = None   # last Scenario-tab parameters sent to the model (SPEC-23)
        self.scenario_rejections: list[ScenarioProblem] = []
        self.interview: dict = {"asked": [], "previous": None}
        self._turn_interview: dict | None = None

    def _complete(self):
        self.usage["requests"] += 1
        resp = self.client.chat.completions.create(model=self.model, messages=self.messages, tools=ALL_TOOL_SCHEMAS)
        if hasattr(resp, "usage") and resp.usage:
            u = resp.usage
            pt = u.get("prompt_tokens", 0) if isinstance(u, dict) else getattr(u, "prompt_tokens", 0)
            ct = u.get("completion_tokens", 0) if isinstance(u, dict) else getattr(u, "completion_tokens", 0)
            tt = u.get("total_tokens", 0) if isinstance(u, dict) else getattr(u, "total_tokens", 0)
            self.usage["prompt_tokens"] += pt or 0
            self.usage["completion_tokens"] += ct or 0
            self.usage["total_tokens"] += tt or 0
            details = u.get("prompt_tokens_details") if isinstance(u, dict) else getattr(u, "prompt_tokens_details", None)
            cached = 0
            if isinstance(details, dict):
                cached = details.get("cached_tokens", 0) or 0
            elif details is not None:
                cached = getattr(details, "cached_tokens", 0) or 0
            if cached:
                self.usage["cached_prompt_tokens"] = self.usage.get("cached_prompt_tokens", 0) + cached
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
                fn_name = tc.function.name
                fn_args_str = tc.function.arguments
                try:
                    args_dict = json.loads(fn_args_str) if isinstance(fn_args_str, str) else fn_args_str
                except json.JSONDecodeError:
                    args_dict = {}

                if fn_name == "next_question":
                    model_asked = args_dict.get("asked") or []
                    merged_asked = list(dict.fromkeys(self.interview["asked"] + model_asked))
                    args_dict["asked"] = merged_asked
                    if "previous" not in args_dict or args_dict["previous"] is None:
                        args_dict["previous"] = self.interview.get("previous")
                    fn_args_str = json.dumps(args_dict)

                if self.use_verifier and fn_name in SEASON_SOLVING_TOOLS:
                    problems = check_scenario(fn_name, args_dict, self.user_texts, self.tool_results)
                    if problems:
                        problems_payload = [
                            {"parameter": p.parameter, "value": p.value, "reason": p.reason}
                            for p in problems
                        ]
                        result = json.dumps({
                            "error": "scenario_mismatch",
                            "problems": problems_payload,
                            "hint": "Use only what the farmer said. Remove the parameter, or ask the farmer.",
                        })
                        calls_log.append({
                            "tool": fn_name,
                            "arguments": fn_args_str,
                            "error": True,
                            "rejected": True,
                        })
                        self.scenario_rejections.extend(problems)
                        self.messages.append({"role": "tool", "tool_call_id": tc.id, "content": result})
                        continue

                result = run_tool(fn_name, fn_args_str, images=self.images)
                self.tool_results.append(result)
                if fn_name == "next_question":
                    try:
                        res_obj = json.loads(result)
                        if isinstance(res_obj, dict):
                            next_item = res_obj.get("next")
                            if isinstance(next_item, dict) and next_item.get("id"):
                                nid = next_item["id"]
                                if nid not in self.interview["asked"]:
                                    self.interview["asked"].append(nid)
                            self.interview["previous"] = args_dict.get("scenario")
                            self._turn_interview = {
                                "asked": list(self.interview["asked"]),
                                "next_id": next_item.get("id") if isinstance(next_item, dict) else None,
                                "done": bool(res_obj.get("done", False)),
                            }
                    except Exception:
                        pass
                try:
                    is_err = "error" in json.loads(result)
                except Exception:
                    is_err = False
                calls_log.append({
                    "tool": fn_name,
                    "arguments": fn_args_str,
                    "error": is_err,
                    "rejected": False,
                })
                self.messages.append({"role": "tool", "tool_call_id": tc.id, "content": result})
        raise RuntimeError(f"The model kept calling tools for {MAX_TOOL_ROUNDS} rounds without answering.")

    def ask(self, text: str, images: list | None = None, audio: str | None = None,
            screen_scenario: dict | None = None) -> Reply:
        """Answer one farmer message.

        `screen_scenario` is the last scenario computed on the Scenario tab (its parameters, not its
        results), so questions like "what does this chart mean?" are answered about the farmer's own run.
        It is sent to the model only when it changed since the last message (SPEC-23)."""
        from dora.media import build_user_content, transcribe

        self.scenario_rejections = []
        actual_text = text or ""
        if audio:
            audio_transcript = transcribe(audio)
            if audio_transcript:
                actual_text = f"{actual_text}\n{audio_transcript}".strip() if actual_text else audio_transcript

        self.user_texts.append(actual_text)

        prompt_text = actual_text
        if screen_scenario and screen_scenario != self.screen_scenario:
            screen_json = json.dumps(screen_scenario, ensure_ascii=False, sort_keys=True)
            prompt_text = (
                "[Screen context, not typed by the farmer: the last scenario computed on the DORA Scenario tab "
                "(parameters only, no results). If you need a number, call the tools with this scenario.]\n"
                f"{screen_json}\n\n{actual_text}"
            )
            # These parameters are the farmer's own inputs on screen, so the verifier may accept them.
            self.user_texts.append(screen_json)
            self.screen_scenario = dict(screen_scenario)

        if images:
            from dora.media import encode_image
            self.images = [encode_image(p) for p in images]
            content = build_user_content(prompt_text, images)
            self.messages.append({"role": "user", "content": content})
        else:
            self.messages.append({"role": "user", "content": prompt_text})

        self._turn_interview = None

        def _get_styles(ans: str, calls_made: list[dict]) -> list[str]:
            st = list(jargon(ans))
            ser = unnamed_series(ans)
            if ser:
                st.extend(ser)
            if any(c.get("tool") == "next_question" for c in calls_made):
                if ans.count("?") > 1:
                    st.append("Ask only the question next_question returned; remove the others.")
            return st

        calls: list[dict] = []
        answer = fix_label_language(self._answer(calls), actual_text)
        initial_problems = verify(answer, self.tool_results, self.user_texts)

        if not self.use_verifier:
            return Reply(
                text=answer,
                verified=not initial_problems,
                unsupported=initial_problems,
                tool_calls=calls,
                initial_unsupported=initial_problems,
                usage=dict(self.usage),
                scenario_rejections=list(self.scenario_rejections),
                style_problems=_get_styles(answer, calls),
                interview=self._turn_interview,
            )

        for _ in range(MAX_CORRECTIONS):
            problems = verify(answer, self.tool_results, self.user_texts)
            styles = _get_styles(answer, calls)
            if not problems and not styles:
                return Reply(
                    text=answer,
                    verified=True,
                    unsupported=[],
                    tool_calls=calls,
                    initial_unsupported=initial_problems,
                    usage=dict(self.usage),
                    scenario_rejections=list(self.scenario_rejections),
                    style_problems=[],
                    interview=self._turn_interview,
                )
            self.messages.append({"role": "user", "content": correction_message(problems, styles)})
            answer = fix_label_language(self._answer(calls), actual_text)
        problems = verify(answer, self.tool_results, self.user_texts)
        styles = _get_styles(answer, calls)
        return Reply(
            text=answer,
            verified=not problems,
            unsupported=problems,
            tool_calls=calls,
            initial_unsupported=initial_problems,
            usage=dict(self.usage),
            scenario_rejections=list(self.scenario_rejections),
            style_problems=styles,
            interview=self._turn_interview,
        )
