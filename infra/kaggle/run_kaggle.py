"""E9/E10 on a free Kaggle notebook: an open model served with vLLM on the notebook's GPUs, and DORA's
evaluation running next to it, all inside the notebook. No API, no credit: Kaggle's weekly GPU quota.

The notebook needs: GPU T4 x2 (or P100), Internet on (to install vLLM and download the model), and the
private dataset "dora-code" (a zip of dora/ and eval/, made by infra/kaggle/package.py) attached.

Settings, as environment variables or the constants below:
    E9_MODEL   Hugging Face id (default Qwen/Qwen2.5-7B-Instruct)
    E9_IDS     comma-separated question ids, or "all"
    E9_ARMS    arms for eval/run_e9.py (default alone,dora)
Results go to /kaggle/working/results (the notebook's output, downloadable with `kaggle kernels output`).
"""
import glob
import os
import subprocess
import sys
import time
import urllib.request
import zipfile

MODEL = os.environ.get("E9_MODEL", "Qwen/Qwen2.5-7B-Instruct")
IDS = os.environ.get("E9_IDS", "q04,q08,q09,q18,q19")
ARMS = os.environ.get("E9_ARMS", "alone,dora")
MAX_LEN = os.environ.get("E9_MAXLEN", "32768")
WORK = "/kaggle/working"
CODE = f"{WORK}/dora-code"
PORT = 8000
KEY = "kaggle-local"          # the server only listens inside the notebook


def sh(cmd: str) -> None:
    print("+", cmd, flush=True)
    subprocess.run(cmd, shell=True, check=True)


def gpus() -> int:
    out = subprocess.run("nvidia-smi --query-gpu=name,memory.total --format=csv,noheader", shell=True,
                         capture_output=True, text=True).stdout.strip()
    print("GPUs:", out or "none", flush=True)
    return len([l for l in out.splitlines() if l.strip()])


def unpack_code() -> None:
    zips = glob.glob("/kaggle/input/**/dora-code.zip", recursive=True)
    if zips:
        with zipfile.ZipFile(zips[0]) as z:
            z.extractall(CODE)
    else:       # Kaggle extracts uploaded zips: the files are already there
        src = (glob.glob("/kaggle/input/**/dora/engine.py", recursive=True) or [None])[0]
        if not src:
            sys.exit("attach the dora-code dataset to the notebook")
        sh(f"cp -r {os.path.dirname(os.path.dirname(src))} {CODE}")
    print("code at", CODE, os.listdir(CODE), flush=True)


def serve(n_gpus: int) -> subprocess.Popen:
    # T4 and P100 have no bfloat16: half precision. Two T4s split the model (tensor parallel).
    cmd = ["python", "-m", "vllm.entrypoints.openai.api_server", "--model", MODEL, "--port", str(PORT),
           "--api-key", KEY, "--dtype", "half", "--max-model-len", MAX_LEN,
           "--tensor-parallel-size", str(max(1, n_gpus)), "--enable-auto-tool-choice",
           "--tool-call-parser", "hermes", "--enable-prefix-caching", "--served-model-name", MODEL]
    log = open(f"{WORK}/vllm.log", "w")
    proc = subprocess.Popen(cmd, stdout=log, stderr=subprocess.STDOUT)
    t0 = time.time()
    while time.time() - t0 < 30 * 60:
        if proc.poll() is not None:
            sys.exit(f"vLLM exited; see vllm.log:\n{open(f'{WORK}/vllm.log').read()[-3000:]}")
        try:
            urllib.request.urlopen(f"http://localhost:{PORT}/health", timeout=5)
            print(f"vLLM ready after {time.time() - t0:.0f} s", flush=True)
            return proc
        except Exception:
            time.sleep(10)
    sys.exit("vLLM did not start in 30 minutes")


def main() -> None:
    n = gpus()
    if n == 0:
        sys.exit("no GPU: turn on a GPU accelerator in the notebook settings")
    unpack_code()
    sh("pip install -q vllm==0.9.2")
    proc = serve(n)
    with open(f"{WORK}/kaggle.env", "w") as f:
        f.write(f"KAGGLE_VLLM_KEY={KEY}\n")
    env = dict(os.environ, DORA_OFFLINE="1", PYTHONUTF8="1")
    ids = "" if IDS == "all" else f"--ids {IDS}"
    t0 = time.time()
    subprocess.run(f"python eval/run_e9.py --model {MODEL} --base http://localhost:{PORT}/v1 "
                   f"--key-var KAGGLE_VLLM_KEY --env {WORK}/kaggle.env {ids} --arms {ARMS} --runs 1 "
                   f"--concurrency 4 --gpu-usd-per-s 0 --out {WORK}/results",
                   shell=True, check=False, cwd=CODE, env=env)
    print(f"evaluation took {time.time() - t0:.0f} s", flush=True)
    proc.terminate()


if __name__ == "__main__":
    main()
