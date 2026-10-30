"""An open Meta model on Modal, behind an OpenAI-compatible API (vLLM), for E6 and SPEC-24.

DORA's agent talks to any OpenAI-compatible chat API with tool calls, so pointing
DORA_API_BASE at this server is all it takes to run the evaluation on it.

Deploy (from the repository root, with the Modal client installed):
    python -m modal deploy infra/modal/serve_llama.py

Secrets it reads (created once, never written in the repository):
    huggingface-secret   HF_TOKEN=<read token of an account that accepted Meta's Llama license>
    dora-vllm            VLLM_API_KEY=<the key DORA sends; same value as MODAL_API_KEY in .env>

Billing: the GPU is billed per second while a container runs. It scales to zero after
SCALEDOWN_MINUTES without requests, so an idle server costs nothing, and the first request
after that pays a cold start (loading the weights), which SPEC-24 reports apart.
"""
import modal

MODEL = "meta-llama/Llama-3.1-8B-Instruct"
GPU = "L40S"                     # 48 GB: the 8B weights (16 GB) plus a 32k-token context (DORA sends ~28k)
MAX_MODEL_LEN = 32768
SCALEDOWN_MINUTES = 5
PORT = 8000
# vLLM's chat template for Llama 3.1 tool calls in JSON, from the same vLLM release (fetched when the image is built).
# Without it the 8B model wrote the call as plain text (docs/experimentos/2026-10-30-modal-llama-8b-q08.md).
TOOL_TEMPLATE_URL = "https://raw.githubusercontent.com/vllm-project/vllm/v0.9.2/examples/tool_chat_template_llama3.1_json.jinja"
TOOL_TEMPLATE = "/root/tool_chat_template_llama3.1_json.jinja"

image = (
    modal.Image.debian_slim(python_version="3.12")
    # transformers pinned: newer releases register "aimv2", which vLLM 0.9.2 also registers, and the server fails to start
    .pip_install("vllm==0.9.2", "transformers==4.53.2", "huggingface_hub[hf_transfer]")
    .env({"HF_HUB_ENABLE_HF_TRANSFER": "1"})
    .run_commands(f"python -c \"import urllib.request; urllib.request.urlretrieve('{TOOL_TEMPLATE_URL}', '{TOOL_TEMPLATE}')\"")
)

hf_cache = modal.Volume.from_name("huggingface-cache", create_if_missing=True)
vllm_cache = modal.Volume.from_name("vllm-cache", create_if_missing=True)

app = modal.App("dora-llama")


@app.function(
    image=image,
    gpu=GPU,
    scaledown_window=SCALEDOWN_MINUTES * 60,
    timeout=20 * 60,
    volumes={"/root/.cache/huggingface": hf_cache, "/root/.cache/vllm": vllm_cache},
    secrets=[modal.Secret.from_name("huggingface-secret"), modal.Secret.from_name("dora-vllm")],
)
@modal.concurrent(max_inputs=16)
@modal.web_server(port=PORT, startup_timeout=15 * 60)
def serve():
    import os
    import subprocess

    cmd = [
        "vllm", "serve", MODEL,
        "--host", "0.0.0.0", "--port", str(PORT),
        "--api-key", os.environ["VLLM_API_KEY"],
        "--max-model-len", str(MAX_MODEL_LEN),
        "--enable-auto-tool-choice", "--tool-call-parser", "llama3_json",   # DORA works through tool calls
        "--chat-template", TOOL_TEMPLATE,
        "--served-model-name", MODEL,
    ]
    subprocess.Popen(cmd)
