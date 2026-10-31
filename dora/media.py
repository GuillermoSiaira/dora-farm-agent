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


# Meta's speech-to-text takes only WAV, mono, 16-bit PCM at 16 or 24 kHz (dev.meta.ai/docs/speech-to-text).
_ASR_RATE = 24_000


def to_asr_wav(path: str | Path) -> bytes:
    """The audio as WAV bytes in the format Meta's speech-to-text accepts.

    WAV files are converted here (mixed to mono, resampled, 16-bit). Other formats (m4a, ogg, mp3 from a
    phone) need ffmpeg on the PATH; without it the error says so.
    """
    import io
    import shutil
    import subprocess
    import wave

    import numpy as np

    p = Path(path)
    if p.suffix.lower() != ".wav":
        ffmpeg = shutil.which("ffmpeg")
        if not ffmpeg:
            raise RuntimeError(f"'{p.suffix}' audio needs ffmpeg to be converted to WAV; send a WAV file or install ffmpeg.")
        out = subprocess.run([ffmpeg, "-v", "error", "-i", str(p), "-ac", "1", "-ar", str(_ASR_RATE),
                              "-c:a", "pcm_s16le", "-map_metadata", "-1", "-f", "wav", "-"],
                             capture_output=True, check=True)
        return out.stdout

    from scipy.io import wavfile
    from scipy.signal import resample_poly

    rate, data = wavfile.read(str(p))
    if data.dtype.kind == "f":
        x = data.astype(np.float64)
    elif data.dtype == np.uint8:
        x = (data.astype(np.float64) - 128) / 128
    else:
        x = data.astype(np.float64) / float(np.iinfo(data.dtype).max)
    if x.ndim > 1:
        x = x.mean(axis=1)
    if rate != _ASR_RATE:
        g = np.gcd(int(rate), _ASR_RATE)
        x = resample_poly(x, _ASR_RATE // g, int(rate) // g)
    pcm = (np.clip(x, -1.0, 1.0) * 32767).astype("<i2")
    buf = io.BytesIO()
    with wave.open(buf, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(_ASR_RATE)
        w.writeframes(pcm.tobytes())
    return buf.getvalue()


def transcribe(path: str | Path, model: str | None = None) -> str:
    """Transcribe an audio file with Meta's speech-to-text (POST /asr/transcribe, multipart).

    Uses DORA_TRANSCRIBE_MODEL from the environment by default (muse-voice-transcribe-1.0). If no
    backend is configured, returns 'voice notes need a transcription model'.
    """
    selected_model = model or os.environ.get("DORA_TRANSCRIBE_MODEL")
    if not selected_model:
        return "voice notes need a transcription model"

    audio_path = Path(path)
    if not audio_path.is_file():
        raise FileNotFoundError(f"Audio file not found: {audio_path}")

    base_url = os.environ.get("DORA_API_BASE", "https://api.meta.ai/v1").rstrip("/")
    url = f"{base_url}/asr/transcribe"
    api_key = os.environ.get("DORA_API_KEY", "")
    settings = {"model": selected_model, "audioEncoding": "WAV", "mode": "PUSH_TO_TALK"}
    audio = to_asr_wav(audio_path)

    boundary = f"----DORAFormBoundary{int(os.times().elapsed * 1000)}"
    crlf = b"\r\n"
    body = bytearray()
    body += f"--{boundary}".encode() + crlf
    body += b'Content-Disposition: form-data; name="request"' + crlf
    body += b"Content-Type: application/json" + crlf + crlf
    body += json.dumps(settings).encode() + crlf
    body += f"--{boundary}".encode() + crlf
    body += f'Content-Disposition: form-data; name="audio"; filename="{audio_path.stem}.wav"'.encode() + crlf
    body += b"Content-Type: audio/wav" + crlf + crlf
    body += audio + crlf
    body += f"--{boundary}--".encode() + crlf

    req = urllib.request.Request(
        url,
        data=bytes(body),
        headers={
            "Content-Type": f"multipart/form-data; boundary={boundary}",
            "Accept": "application/json",
            "Authorization": f"Bearer {api_key}",
            "User-Agent": "DORA-farm-agent/0.1",
        },
        method="POST",
    )

    ctx = ssl.create_default_context()
    try:
        with urllib.request.urlopen(req, timeout=120, context=ctx) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            return data.get("transcript", "")
    except urllib.error.HTTPError as e:
        err_msg = e.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"Transcription API error ({e.code}): {err_msg}")
    except Exception as e:
        raise RuntimeError(f"Transcription failed: {e}")
