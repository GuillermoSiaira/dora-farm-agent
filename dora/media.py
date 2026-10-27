"""Multimodal media handling: image encoding for chat and pluggable audio transcription."""
from __future__ import annotations

import base64
import json
import mimetypes
import os
import ssl
import urllib.error
import urllib.request
from pathlib import Path


def encode_image(image_path: str | Path) -> str:
    """Read an image file and return its base64 data URL."""
    p = Path(image_path)
    if not p.is_file():
        raise FileNotFoundError(f"Image not found: {p}")

    mime, _ = mimetypes.guess_type(str(p))
    if not mime:
        suffix = p.suffix.lower()
        if suffix in (".jpg", ".jpeg"):
            mime = "image/jpeg"
        elif suffix == ".png":
            mime = "image/png"
        elif suffix == ".webp":
            mime = "image/webp"
        else:
            mime = "image/jpeg"

    with open(p, "rb") as f:
        data = f.read()

    b64 = base64.b64encode(data).decode("ascii")
    return f"data:{mime};base64,{b64}"


def build_user_content(text: str, image_paths: list[str | Path] | None = None) -> list[dict] | str:
    """Build OpenAI-compatible user message content with text and image_url parts."""
    if not image_paths:
        return text

    parts: list[dict] = [{"type": "text", "text": text}]
    for img in image_paths:
        data_url = encode_image(img)
        parts.append({
            "type": "image_url",
            "image_url": {"url": data_url},
        })
    return parts


def transcribe(path: str | Path, model: str | None = None) -> str:
    """Transcribe an audio file using an OpenAI-compatible /audio/transcriptions endpoint.

    Uses DORA_TRANSCRIBE_MODEL from the environment by default. If no backend is configured,
    returns 'voice notes need a transcription model'.
    """
    selected_model = model or os.environ.get("DORA_TRANSCRIBE_MODEL")
    if not selected_model:
        return "voice notes need a transcription model"

    audio_path = Path(path)
    if not audio_path.is_file():
        raise FileNotFoundError(f"Audio file not found: {audio_path}")

    base_url = os.environ.get("DORA_API_BASE", "https://api.openai.com/v1").rstrip("/")
    url = f"{base_url}/audio/transcriptions"
    api_key = os.environ.get("DORA_API_KEY", "")

    boundary = f"----WebKitFormBoundary{int(os.times().elapsed * 1000)}"
    body = bytearray()

    # Form field: model
    body.extend(f"--{boundary}\r\n".encode("utf-8"))
    body.extend(b'Content-Disposition: form-data; name="model"\r\n\r\n')
    body.extend(f"{selected_model}\r\n".encode("utf-8"))

    # Form field: file
    filename = audio_path.name
    mime, _ = mimetypes.guess_type(str(audio_path))
    mime = mime or "audio/mpeg"

    body.extend(f"--{boundary}\r\n".encode("utf-8"))
    body.extend(f'Content-Disposition: form-data; name="file"; filename="{filename}"\r\n'.encode("utf-8"))
    body.extend(f"Content-Type: {mime}\r\n\r\n".encode("utf-8"))
    with open(audio_path, "rb") as f:
        body.extend(f.read())
    body.extend(b"\r\n")

    body.extend(f"--{boundary}--\r\n".encode("utf-8"))

    req = urllib.request.Request(
        url,
        data=bytes(body),
        headers={
            "Content-Type": f"multipart/form-data; boundary={boundary}",
            "Authorization": f"Bearer {api_key}",
            "User-Agent": "DORA-farm-agent/0.1",
        },
        method="POST",
    )

    ctx = ssl.create_default_context()
    try:
        with urllib.request.urlopen(req, timeout=30, context=ctx) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            return data.get("text", "")
    except urllib.error.HTTPError as e:
        err_msg = e.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"Transcription API error ({e.code}): {err_msg}")
    except Exception as e:
        raise RuntimeError(f"Transcription failed: {e}")
