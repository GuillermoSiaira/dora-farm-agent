"""Arm 3 of E9: a generic agent, not DORA's, connected to the engine through the public MCP server.

What a generic MCP client does: it reads the server's instructions and tool list, and gives them to a model
with a neutral system prompt. No DORA prompt, no modeling guide (unless guide=True: then it also reads the
server's dora://modeling-guide resource, as a client that loads resources would), no scenario checks.
Any model behind an OpenAI-compatible chat API works.

After the model answers, the harness (not the model) calls check_text with the answer and the signed results,
so "verified" means the same as in DORA: every number in the answer is backed by the engine or the question.

The MCP key, if any, comes from the environment (DORA_MCP_API_KEY); it is never logged or written."""
from __future__ import annotations

import json
import os
import time
import urllib.error
import urllib.request

DEFAULT_MCP_URL = "https://guillermosiaira--dora-mcp-mcp-app.us-east.modal.run/mcp"
# The engine's tools; the on-chain record and spreadsheet tools are not for answering a question.
ENGINE_TOOLS = ("build_scenario", "update_scenario", "solve_plan", "shadow_prices", "break_even_prices",
                "compare_rent_out", "evaluate_plan", "sensitivity", "check_text")
# Names of DORA's own tools for the same work, so the E1 scorer reads both arms alike.
AS_AGENT_TOOL = {"solve_plan": "evaluate_season"}
MAX_ROUNDS = 8
NEUTRAL_PROMPT = (
    "You are an assistant. Use the tools to answer the farmer's question. "
    "Quote only numbers that come from the tool results or from the question. "
    "If information is missing, ask for it instead of assuming. Answer in the farmer's language."
)


class MCPClient:
    """JSON-RPC over the stateless streamable HTTP transport: one POST per call."""

    def __init__(self, url: str | None = None, api_key: str | None = None, timeout: float = 120.0):
        self.url = url or os.environ.get("DORA_MCP_URL", DEFAULT_MCP_URL)
        self._key = api_key if api_key is not None else os.environ.get("DORA_MCP_API_KEY")
        self.timeout = timeout
        self.calls = 0
        self._id = 0

    def rpc(self, method: str, params: dict) -> dict:
        self._id += 1
        body = json.dumps({"jsonrpc": "2.0", "id": self._id, "method": method, "params": params}).encode()
        headers = {"Content-Type": "application/json", "Accept": "application/json, text/event-stream"}
        if self._key:
            headers["Authorization"] = "Bearer " + self._key
        for attempt in range(6):
            try:
                self.calls += 1
                with urllib.request.urlopen(urllib.request.Request(self.url, data=body, headers=headers),
                                            timeout=self.timeout) as r:
                    text = r.read().decode("utf-8")
                break
            except urllib.error.HTTPError as e:
                if e.code in (429, 502, 503, 504) and attempt < 5:
                    time.sleep(2 ** attempt * 2)
                    continue
                raise RuntimeError(f"MCP {method}: HTTP {e.code}") from None
        msg = parse_sse(text)
        if "error" in msg:
            raise RuntimeError(f"MCP {method}: {msg['error'].get('message')}")
        return msg["result"]

    def initialize(self) -> str:
        res = self.rpc("initialize", {"protocolVersion": "2025-06-18", "capabilities": {},
                                      "clientInfo": {"name": "dora-e9-generic-agent", "version": "1"}})
        return res.get("instructions") or ""

    def tools(self) -> list[dict]:
        return [t for t in self.rpc("tools/list", {})["tools"] if t["name"] in ENGINE_TOOLS]

    def resource(self, uri: str) -> str:
        return "\n".join(c.get("text", "") for c in self.rpc("resources/read", {"uri": uri}).get("contents", []))

    def call(self, name: str, arguments: dict) -> dict:
        return tool_payload(self.rpc("tools/call", {"name": name, "arguments": arguments}))


def parse_sse(text: str) -> dict:
    """The JSON-RPC message, whether the server answered with plain JSON or with server-sent events."""
    data = [line[5:].strip() for line in text.splitlines() if line.startswith("data:")]
    return json.loads(data[-1] if data else text)


def tool_payload(res: dict) -> dict:
    """The tool's own dict ({result, provenance} or {error, ...}) from a tools/call result."""
    if isinstance(res.get("structuredContent"), dict):
        sc = res["structuredContent"]
        return sc["result"] if set(sc) == {"result"} and isinstance(sc["result"], dict) else sc
    texts = [c.get("text", "") for c in res.get("content", []) if c.get("type") == "text"]
    try:
        out = json.loads("".join(texts))
        return out if isinstance(out, dict) else {"result": out}
    except json.JSONDecodeError:
        return {"error": "".join(texts) or "empty tool result"}


def openai_tools(mcp_tools: list[dict]) -> list[dict]:
    return [{"type": "function", "function": {"name": t["name"], "description": t.get("description", ""),
                                              "parameters": t.get("inputSchema") or {"type": "object"}}}
            for t in mcp_tools]


class MCPAgent:
    """One question, one generic agent. ask() returns a dict the E1 scorer understands."""

    def __init__(self, client, model: str, mcp: MCPClient, setup: dict):
        self.client, self.model, self.mcp = client, model, mcp
        self.tools = setup["tools"]
        self.system = setup["system"]
        self.usage = {"prompt_tokens": 0, "completion_tokens": 0, "requests": 0}

    def _complete(self, messages):
        resp = self.client.chat.completions.create(model=self.model, messages=messages, tools=self.tools)
        u = getattr(resp, "usage", None)
        if u is not None:
            self.usage["prompt_tokens"] += getattr(u, "prompt_tokens", 0) or 0
            self.usage["completion_tokens"] += getattr(u, "completion_tokens", 0) or 0
        self.usage["requests"] += 1
        return resp.choices[0].message

    def ask(self, question: str) -> dict:
        messages = [{"role": "system", "content": self.system}, {"role": "user", "content": question}]
        calls, results, signed = [], [], []
        text, stopped = "", None
        for _ in range(MAX_ROUNDS):
            msg = self._complete(messages)
            if not msg.tool_calls:
                text = msg.content or ""
                break
            messages.append({"role": "assistant", "content": msg.content or "", "tool_calls": [
                {"id": tc.id, "type": "function", "function": {"name": tc.function.name,
                                                                "arguments": tc.function.arguments}}
                for tc in msg.tool_calls]})
            for tc in msg.tool_calls:
                name, raw_args = tc.function.name, tc.function.arguments
                try:
                    args = json.loads(raw_args) if isinstance(raw_args, str) else (raw_args or {})
                    bad_json = not isinstance(args, dict)
                except json.JSONDecodeError:
                    args, bad_json = {}, True
                if bad_json or name not in ENGINE_TOOLS:
                    out = {"error": "invalid JSON arguments" if bad_json else f"unknown tool {name}"}
                else:
                    try:
                        out = self.mcp.call(name, args)
                    except RuntimeError as e:
                        out = {"error": str(e)}
                is_err = "error" in out
                calls.append({"tool": AS_AGENT_TOOL.get(name, name), "mcp_tool": name,
                              "arguments": raw_args if isinstance(raw_args, str) else json.dumps(raw_args),
                              "error": is_err, "rejected": False, "bad_json": bad_json})
                result = out.get("result", out)
                results.append(json.dumps(result, ensure_ascii=False))
                if not is_err and isinstance(out.get("provenance"), dict):
                    signed.append({"result": out["result"], "provenance": out["provenance"]})
                messages.append({"role": "tool", "tool_call_id": tc.id,
                                 "content": json.dumps(out, ensure_ascii=False)})
        else:
            stopped = "max_rounds"
        check = self.mcp.call("check_text", {"text": text, "results": signed, "farmer_said": [question]})
        return {"text": text, "tool_calls": calls, "tool_results": results, "usage": dict(self.usage),
                "verified": bool(check.get("result", check).get("supported")) if text else False,
                "unsupported": [u.get("text") for u in check.get("result", check).get("unsupported", [])],
                "stopped": stopped}


def setup(mcp: MCPClient, guide: bool = False) -> dict:
    """What a generic client gives the model: the server's instructions and tools (and the guide, if asked)."""
    system = NEUTRAL_PROMPT
    instructions = mcp.initialize()
    if instructions:
        system += "\n\nServer instructions: " + instructions
    if guide:
        system += "\n\n" + mcp.resource("dora://modeling-guide")
    return {"system": system, "tools": openai_tools(mcp.tools())}
