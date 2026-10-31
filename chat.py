"""Chat with DORA in the terminal, showing each tool call and the verifier's verdict as they happen.

    python chat.py                                     # model from DORA_MODEL in .env
    python chat.py --model muse-spark-1.3-contributor
    python chat.py --no-verifier

In the chat, `audio nota.wav` sends a voice note (needs DORA_TRANSCRIBE_MODEL) and
`foto factura.png texto...` sends a photo with the text.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent


def _load_dotenv(path: Path) -> None:
    """KEY=value lines of .env into the environment, without overriding what is already set."""
    if not path.is_file():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            k, v = line.split("=", 1)
            os.environ.setdefault(k.strip(), v.strip().strip('"'))


def main() -> None:
    _load_dotenv(ROOT / ".env")
    parser = argparse.ArgumentParser(description="Chat with DORA in the terminal")
    parser.add_argument("--model", default=os.environ.get("DORA_MODEL", ""))
    parser.add_argument("--no-verifier", action="store_true")
    args = parser.parse_args()

    import dora.agent as agent_module

    original_run_tool = agent_module.run_tool

    def run_tool_shown(name, arguments, **kwargs):
        print(f"  -> {name}({arguments[:200]}{'...' if len(arguments) > 200 else ''})", flush=True)
        t = time.time()
        result = original_run_tool(name, arguments, **kwargs)
        status = "error" if "error" in json.loads(result) else "ok"
        print(f"     {status}, {time.time() - t:.1f} s", flush=True)
        return result

    agent_module.run_tool = run_tool_shown
    agent = agent_module.Agent(model=args.model, use_verifier=not args.no_verifier)
    print(f"DORA con {args.model}{' sin verificador' if args.no_verifier else ''}. Línea vacía para salir.")
    print("Voz: 'audio ARCHIVO.wav'. Foto: 'foto ARCHIVO.png texto'.\n")

    while True:
        try:
            text = input("vos> ").strip()
        except (EOFError, KeyboardInterrupt):
            break
        if not text:
            break
        t = time.time()
        audio, images = None, None
        cmd, _, rest = text.partition(" ")
        if cmd in ("audio", "foto") and rest:
            path, _, text = rest.strip().partition(" ")
            if not Path(path).is_file():
                print(f"  No encuentro {path}\n")
                continue
            audio, images = (path, None) if cmd == "audio" else (None, [path])
        reply = agent.ask(text, images=images, audio=audio)
        if audio:
            print(f"  [transcripción] {agent.user_texts[-1]}")
        print(f"\nDORA> {reply.text}\n")
        if reply.initial_unsupported:
            nums = ", ".join(str(u.text if hasattr(u, "text") else u) for u in reply.initial_unsupported)
            print(f"  [verificador] números sin respaldo en el primer borrador: {nums}")
        print(f"  [verificada: {'sí' if reply.verified else 'no'} | {time.time() - t:.0f} s | "
              f"{reply.usage.get('requests', 0)} llamadas al modelo, "
              f"{reply.usage.get('prompt_tokens', 0):,} tokens de entrada, "
              f"{reply.usage.get('completion_tokens', 0):,} de salida en la sesión]\n")


if __name__ == "__main__":
    sys.exit(main())
