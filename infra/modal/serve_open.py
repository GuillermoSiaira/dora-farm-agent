"""Any open model on Modal behind an OpenAI-compatible API (vLLM), for E9 (model size).

Same server as serve_llama.py, with the model, the GPU and the tool-call parser as parameters,
so each size of a family is its own app (dora-e9-<model>) and none touches the public app or MCP.

Deploy one size (from the repository root, with the Modal client installed):
    E9_MODEL=Qwen/Qwen2.5-7B-Instruct E9_GPU=L40S python -m modal deploy infra/modal/serve_open.py
Stop it when the run ends (it also scales to zero after SCALEDOWN_MINUTES idle):
    python -m modal app stop dora-e9-qwen2-5-7b-instruct

Variables read at deploy time (copied into the image, so the container sees the same values):
    E9_MODEL    Hugging Face id of the model
    E9_GPU      Modal GPU spec: L40S, A100-80GB, H100, H100:2 ...
    E9_PARSER   vLLM tool-call parser (default: hermes for Qwen, llama3_json for Llama)
    E9_MAXLEN   context length (default 32768)
    E9_QUANT    optional vLLM --quantization (e.g. fp8)

Secrets: huggingface-secret (HF_TOKEN) and dora-vllm (VLLM_API_KEY = MODAL_API_KEY in .env), as in serve_llama.py.
"""
import os
import re

import modal

MODEL = os.environ.get("E9_MODEL", "Qwen/Qwen2.5-7B-Instruct")
GPU = os.environ.get("E9_GPU", "L40S")
PARSER = os.environ.get("E9_PARSER") or ("llama3_json" if "llama" in MODEL.lower() else "hermes")
MAX_MODEL_LEN = int(os.environ.get("E9_MAXLEN", "32768"))
QUANT = os.environ.get("E9_QUANT", "")
STARTUP_MINUTES = int(os.environ.get("E9_STARTUP_MIN", "20"))   # a 72B downloads ~145 GB before it answers
SCALEDOWN_MINUTES = 5
PORT = 8000
TOOL_TEMPLATE_URL = "https://raw.githubusercontent.com/vllm-project/vllm/v0.9.2/examples/tool_chat_template_llama3.1_json.jinja"
TOOL_TEMPLATE = "/root/tool_chat_template_llama3.1_json.jinja"


def app_name(model: str) -> str:
    """dora-e9-<model name in lower case, only letters, digits and dashes>."""
    return "dora-e9-" + re.sub(r"[^a-z0-9]+", "-", model.split("/")[-1].lower()).strip("-")


image = (
    modal.Image.debian_slim(python_version="3.12")
    .pip_install("vllm==0.9.2", "transformers==4.53.2", "huggingface_hub[hf_transfer]")
    .env({"HF_HUB_ENABLE_HF_TRANSFER": "1", "E9_MODEL": MODEL, "E9_GPU": GPU, "E9_PARSER": PARSER,
          "E9_MAXLEN": str(MAX_MODEL_LEN), "E9_QUANT": QUANT,
          "E9_STARTUP_MIN": str(STARTUP_MINUTES)})
    .run_commands(f"python -c \"import urllib.request; urllib.request.urlretrieve('{TOOL_TEMPLATE_URL}', '{TOOL_TEMPLATE}')\"")
)

hf_cache = modal.Volume.from_name("huggingface-cache", create_if_missing=True)
vllm_cache = modal.Volume.from_name("vllm-cache", create_if_missing=True)

app = modal.App(app_name(MODEL))


@app.function(
    image=image,
    gpu=GPU,
    scaledown_window=SCALEDOWN_MINUTES * 60,
    timeout=60 * 60,
    volumes={"/root/.cache/huggingface": hf_cache, "/root/.cache/vllm": vllm_cache},
    secrets=[modal.Secret.from_name("huggingface-secret"), modal.Secret.from_name("dora-vllm")],
)
@modal.concurrent(max_inputs=16)
@modal.web_server(port=PORT, startup_timeout=STARTUP_MINUTES * 60)
def serve():
    import subprocess

    n_gpus = int(GPU.split(":")[1]) if ":" in GPU else 1
    cmd = [
        "vllm", "serve", MODEL,
        "--host", "0.0.0.0", "--port", str(PORT),
        "--api-key", os.environ["VLLM_API_KEY"],
        "--max-model-len", str(MAX_MODEL_LEN),
        "--enable-auto-tool-choice", "--tool-call-parser", PARSER,
        "--enable-prefix-caching",            # DORA's fixed prompt is the same in every request
        "--tensor-parallel-size", str(n_gpus),
        "--served-model-name", MODEL,
    ]
    if PARSER == "llama3_json":
        cmd += ["--chat-template", TOOL_TEMPLATE]
    if QUANT:
        cmd += ["--quantization", QUANT]
    subprocess.Popen(cmd)
