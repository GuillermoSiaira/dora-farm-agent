"""WhatsApp Cloud API bridge for DORA.

Receives messages via webhook, routes to Agent with verifier, and sends formatted
answers back to the WhatsApp user.
"""
from __future__ import annotations

import hashlib
import hmac
import json
import os
import re
import ssl
import tempfile
import threading
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

from starlette.requests import Request
from starlette.responses import PlainTextResponse, Response

from dora.agent import Agent

_LOCK = threading.Lock()


@dataclass
class Session:
    agent: Agent
    last_active: float


_sessions: dict[str, Session] = {}
_daily_counts: dict[tuple[str, str], int] = {}


def reset_whatsapp_state() -> None:
    """Reset all in-memory sessions and daily counts. Useful for tests."""
    with _LOCK:
        _sessions.clear()
        _daily_counts.clear()


def _format_tables(text: str) -> str:
    lines = text.split("\n")
    out = []
    i = 0
    while i < len(lines):
        line = lines[i]
        if line.strip().startswith("|") and line.strip().endswith("|"):
            table_lines = []
            while i < len(lines) and lines[i].strip().startswith("|") and lines[i].strip().endswith("|"):
                table_lines.append(lines[i].strip())
                i += 1
            parsed = []
            for tl in table_lines:
                cells = [c.strip() for c in tl.strip("|").split("|")]
                if all(re.match(r"^:?-+:?$", c) for c in cells):
                    continue
                parsed.append(cells)
            if len(parsed) >= 2:
                headers = parsed[0]
                for row in parsed[1:]:
                    row_strs = []
                    for h, cell in zip(headers, row):
                        if h and cell:
                            row_strs.append(f"{h}: {cell}")
                        elif cell:
                            row_strs.append(cell)
                    if row_strs:
                        out.append(", ".join(row_strs))
            elif len(parsed) == 1:
                out.append(": ".join(parsed[0]))
            continue
        out.append(line)
        i += 1
    return "\n".join(out)


def markdown_to_whatsapp(text: str) -> str:
    """Convert Markdown to WhatsApp formatting: **bold** -> *bold*, headings -> *headings*, tables -> 'label: value'."""
    if not text:
        return ""
    text = _format_tables(text)
    # Headings to bold lines: # Heading -> *Heading*
    text = re.sub(r"^[ \t]*#{1,6}[ \t]*(.+?)[ \t]*$", r"*\1*", text, flags=re.MULTILINE)
    # **bold** or __bold__ to *bold*
    text = re.sub(r"\*\*(.+?)\*\*", r"*\1*", text)
    text = re.sub(r"__(.+?)__", r"*\1*", text)
    return text.strip()


def split_message(text: str, max_chars: int = 4000) -> list[str]:
    """Split answers longer than max_chars characters into several messages, at paragraph boundaries."""
    if not text or len(text) <= max_chars:
        return [text] if text else []

    paragraphs = text.split("\n\n")
    chunks: list[str] = []
    current_chunk: list[str] = []
    current_len = 0

    for p in paragraphs:
        p_len = len(p)
        if p_len > max_chars:
            if current_chunk:
                chunks.append("\n\n".join(current_chunk))
                current_chunk = []
                current_len = 0
            lines = p.split("\n")
            sub_chunk: list[str] = []
            sub_len = 0
            for l in lines:
                l_len = len(l)
                if l_len > max_chars:
                    if sub_chunk:
                        chunks.append("\n".join(sub_chunk))
                        sub_chunk = []
                        sub_len = 0
                    for start in range(0, l_len, max_chars):
                        chunks.append(l[start:start + max_chars])
                    continue

                sep = 1 if sub_chunk else 0
                if sub_len + l_len + sep > max_chars:
                    chunks.append("\n".join(sub_chunk))
                    sub_chunk = [l]
                    sub_len = l_len
                else:
                    sub_chunk.append(l)
                    sub_len += l_len + sep
            if sub_chunk:
                chunks.append("\n".join(sub_chunk))
            continue

        sep = 2 if current_chunk else 0
        if current_len + p_len + sep > max_chars:
            chunks.append("\n\n".join(current_chunk))
            current_chunk = [p]
            current_len = p_len
        else:
            current_chunk.append(p)
            current_len += p_len + sep

    if current_chunk:
        chunks.append("\n\n".join(current_chunk))

    return chunks


def send_text(to: str, body: str) -> list[dict]:
    """Send text message(s) to a WhatsApp recipient, splitting at 4,000 chars."""
    token = os.getenv("WHATSAPP_TOKEN", "")
    phone_id = os.getenv("WHATSAPP_PHONE_NUMBER_ID", "")
    version = os.getenv("WHATSAPP_GRAPH_VERSION", "v21.0")

    formatted = markdown_to_whatsapp(body)
    chunks = split_message(formatted, max_chars=4000)
    results = []

    url = f"https://graph.facebook.com/{version}/{phone_id}/messages"
    ctx = ssl.create_default_context()

    for chunk in chunks:
        payload = {
            "messaging_product": "whatsapp",
            "to": to,
            "type": "text",
            "text": {"body": chunk},
        }
        data = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(
            url,
            data=data,
            headers={
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/json",
                "User-Agent": "DORA-farm-agent/0.1",
            },
            method="POST",
        )
        try:
            with urllib.request.urlopen(req, context=ctx, timeout=30) as resp:
                resp_data = json.loads(resp.read().decode("utf-8"))
                results.append(resp_data)
        except urllib.error.HTTPError as e:
            err_body = e.read().decode("utf-8")
            results.append({"error": e.code, "message": err_body})
        except Exception as e:
            results.append({"error": str(e)})

    return results


def download_media(media_id: str) -> tuple[bytes, str]:
    """Retrieve media download URL and download media bytes using the bearer token."""
    token = os.getenv("WHATSAPP_TOKEN", "")
    version = os.getenv("WHATSAPP_GRAPH_VERSION", "v21.0")
    ctx = ssl.create_default_context()

    meta_url = f"https://graph.facebook.com/{version}/{media_id}"
    req1 = urllib.request.Request(
        meta_url,
        headers={"Authorization": f"Bearer {token}", "User-Agent": "DORA-farm-agent/0.1"},
    )
    with urllib.request.urlopen(req1, context=ctx, timeout=30) as resp:
        meta_data = json.loads(resp.read().decode("utf-8"))

    download_url = meta_data["url"]
    mime_type = meta_data.get("mime_type", "application/octet-stream")

    req2 = urllib.request.Request(
        download_url,
        headers={"Authorization": f"Bearer {token}", "User-Agent": "DORA-farm-agent/0.1"},
    )
    with urllib.request.urlopen(req2, context=ctx, timeout=60) as resp:
        content = resp.read()

    return content, mime_type


def get_or_create_session(wa_id: str) -> Agent:
    """Retrieve or create an in-memory Agent for wa_id, expiring after 2 hours."""
    now = time.time()
    with _LOCK:
        session = _sessions.get(wa_id)
        if session is None or (now - session.last_active > 7200):
            agent = Agent()
            session = Session(agent=agent, last_active=now)
            _sessions[wa_id] = session
        else:
            session.last_active = now
        return session.agent


def reset_session(wa_id: str) -> Agent:
    """Reset session for wa_id with a fresh Agent."""
    with _LOCK:
        agent = Agent()
        _sessions[wa_id] = Session(agent=agent, last_active=time.time())
        return agent


def check_and_increment_daily_limit(wa_id: str) -> tuple[bool, str]:
    """Check daily limits. Returns (allowed, error_message)."""
    limit_per_number = int(os.getenv("WHATSAPP_DAILY_LIMIT_PER_NUMBER", "20"))
    limit_total = int(os.getenv("WHATSAPP_DAILY_LIMIT_TOTAL", "200"))
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")

    with _LOCK:
        user_count = _daily_counts.get((today, wa_id), 0)
        total_count = _daily_counts.get((today, "TOTAL"), 0)

        if user_count >= limit_per_number:
            return False, f"Has alcanzado el límite diario de consultas ({limit_per_number} por día). Podés volver a consultar mañana."

        if total_count >= limit_total:
            return False, "El servicio ha alcanzado su límite diario de consultas. Por favor intentá mañana."

        _daily_counts[(today, wa_id)] = user_count + 1
        _daily_counts[(today, "TOTAL")] = total_count + 1
        return True, ""


def handle_incoming_message(msg: dict) -> None:
    """Process an incoming WhatsApp message and dispatch the response."""
    wa_id = msg.get("from")
    if not wa_id:
        return

    msg_type = msg.get("type", "")

    if msg_type == "text":
        body = msg.get("text", {}).get("body", "").strip()
        if body.lower() in ("nuevo", "reset"):
            reset_session(wa_id)
            send_text(wa_id, "Comenzamos una nueva conversación. ¿En qué puedo ayudarte con tu campo?")
            return

        allowed, err_msg = check_and_increment_daily_limit(wa_id)
        if not allowed:
            send_text(wa_id, err_msg)
            return

        send_text(wa_id, "Recibido, estoy calculando… (tarda menos de un minuto)")
        agent = get_or_create_session(wa_id)
        reply = agent.ask(body)
        send_text(wa_id, reply.text)

    elif msg_type == "audio":
        allowed, err_msg = check_and_increment_daily_limit(wa_id)
        if not allowed:
            send_text(wa_id, err_msg)
            return

        send_text(wa_id, "Recibido, estoy calculando… (tarda menos de un minuto)")
        audio_info = msg.get("audio", {})
        media_id = audio_info.get("id")
        if not media_id:
            send_text(wa_id, "No se pudo descargar el audio.")
            return

        temp_path = None
        try:
            content, mime = download_media(media_id)
            suffix = ".ogg" if "ogg" in mime else ".mp3" if "mp3" in mime else ".m4a"
            with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as f:
                f.write(content)
                temp_path = f.name

            agent = get_or_create_session(wa_id)
            reply = agent.ask(text="", audio=temp_path)
            send_text(wa_id, reply.text)
        except Exception as e:
            send_text(wa_id, f"Hubo un error procesando el audio: {e}")
        finally:
            if temp_path and os.path.exists(temp_path):
                try:
                    os.remove(temp_path)
                except Exception:
                    pass

    elif msg_type == "image":
        allowed, err_msg = check_and_increment_daily_limit(wa_id)
        if not allowed:
            send_text(wa_id, err_msg)
            return

        send_text(wa_id, "Recibido, estoy calculando… (tarda menos de un minuto)")
        image_info = msg.get("image", {})
        media_id = image_info.get("id")
        caption = image_info.get("caption") or "Foto de factura recibida"
        if not media_id:
            send_text(wa_id, "No se pudo descargar la imagen.")
            return

        temp_path = None
        try:
            content, mime = download_media(media_id)
            suffix = ".png" if "png" in mime else ".webp" if "webp" in mime else ".jpg"
            with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as f:
                f.write(content)
                temp_path = f.name

            agent = get_or_create_session(wa_id)
            reply = agent.ask(text=caption, images=[temp_path])
            send_text(wa_id, reply.text)
        except Exception as e:
            send_text(wa_id, f"Hubo un error procesando la imagen: {e}")
        finally:
            if temp_path and os.path.exists(temp_path):
                try:
                    os.remove(temp_path)
                except Exception:
                    pass

    else:
        send_text(wa_id, "Por ahora entiendo texto, audios y fotos de facturas.")


def handle_webhook_payload(payload: dict, run_async: bool = True) -> None:
    """Parse WhatsApp Webhook payload and dispatch messages."""
    entries = payload.get("entry", [])
    for entry in entries:
        for change in entry.get("changes", []):
            val = change.get("value", {})
            for msg in val.get("messages", []):
                if run_async:
                    threading.Thread(target=handle_incoming_message, args=(msg,), daemon=True).start()
                else:
                    handle_incoming_message(msg)


def mount_whatsapp_webhook(app: Any) -> None:
    """Mount /whatsapp/webhook GET and POST endpoints on a FastAPI application."""

    @app.get("/whatsapp/webhook")
    async def verify_webhook(request: Request):
        mode = request.query_params.get("hub.mode")
        token = request.query_params.get("hub.verify_token")
        challenge = request.query_params.get("hub.challenge")
        expected_token = os.getenv("WHATSAPP_VERIFY_TOKEN", "")
        if mode == "subscribe" and token == expected_token and expected_token:
            return PlainTextResponse(content=challenge or "", status_code=200)
        return Response(content="Forbidden", status_code=403)

    @app.post("/whatsapp/webhook")
    async def receive_webhook(request: Request):
        raw_body = await request.body()
        secret = os.getenv("WHATSAPP_APP_SECRET", "")
        if secret:
            sig = request.headers.get("X-Hub-Signature-256", "")
            expected = "sha256=" + hmac.new(secret.encode("utf-8"), raw_body, hashlib.sha256).hexdigest()
            if not hmac.compare_digest(sig, expected):
                return Response(content="Forbidden", status_code=403)

        try:
            payload = json.loads(raw_body.decode("utf-8"))
        except Exception:
            return Response(content="Bad Request", status_code=400)

        handle_webhook_payload(payload, run_async=True)
        return Response(content="EVENT_RECEIVED", status_code=200)
