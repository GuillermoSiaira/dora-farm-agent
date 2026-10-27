# SPEC-16: DORA on WhatsApp (Meta WhatsApp Cloud API)

**Status:** to implement; optional for the hackathon (if Meta's account setup is not ready by Nov 2, it stays as "next step"). **Branch:** `spec-16-whatsapp`. Do not merge into `main`; it gets reviewed first.

## Why
Farmers in Argentina live on WhatsApp. "Send a voice note from the truck, get back when money is short and what it is worth" is the scene for the video, and WhatsApp is a Meta product (the hackathon weighs the use of Meta tools at 25%).

## Scope
A bridge, nothing more: WhatsApp message in → the existing `Agent` (with verifier) → answer out. No new economics.

## 1. Webhook (`dora/whatsapp.py`)
- Mounted on the Gradio app's FastAPI server (Gradio exposes `app` as a FastAPI instance; mount routes before `launch`), path `/whatsapp/webhook`.
- **GET** verification: if `hub.mode == "subscribe"` and `hub.verify_token == WHATSAPP_VERIFY_TOKEN`, return `hub.challenge` as plain text; else 403.
- **POST**: check the `X-Hub-Signature-256` header (HMAC-SHA256 of the raw body with `WHATSAPP_APP_SECRET`); reject with 403 if it does not match. Parse `entry[].changes[].value.messages[]`.
  - `type == "text"`: the text.
  - `type == "audio"`: download the media (GET `/{media_id}` for its URL, then GET the URL with the bearer token), transcribe with the existing `dora.media.transcribe` (which uses Meta's `muse-voice-transcribe-1.0` when configured).
  - `type == "image"`: download, pass as image to the agent (invoices, SPEC-08).
  - Other types: answer "Por ahora entiendo texto, audios y fotos de facturas."
- Answer **immediately** with HTTP 200 and do the work in a background thread (the agent takes 30–60 s; WhatsApp retries if the webhook is slow).
- First send a short text: "Recibido, estoy calculando… (tarda menos de un minuto)". Then the answer.

## 2. Sending (`send_text(to, body)`)
- POST `https://graph.facebook.com/{WHATSAPP_GRAPH_VERSION}/{WHATSAPP_PHONE_NUMBER_ID}/messages` with `Authorization: Bearer WHATSAPP_TOKEN`, JSON `{"messaging_product": "whatsapp", "to": <wa_id>, "type": "text", "text": {"body": ...}}`.
- WhatsApp text limit: split answers longer than 4,000 characters into several messages, at paragraph boundaries.
- Convert the agent's Markdown to WhatsApp formatting: `**bold**` → `*bold*`, headings → bold lines, tables → lines "label: value".

## 3. Conversation state
- One `Agent` per WhatsApp number (`wa_id`), in memory, expiring after 2 hours without messages. A message "nuevo" or "reset" starts over.
- Daily limit per number (default 20 questions) and global (default 200), from env, to protect the credits. When reached, say so politely.

## 4. Configuration (env only; never in code or git)
`WHATSAPP_TOKEN`, `WHATSAPP_PHONE_NUMBER_ID`, `WHATSAPP_VERIFY_TOKEN`, `WHATSAPP_APP_SECRET`, `WHATSAPP_GRAPH_VERSION` (default `v21.0`, check Meta's current version), `WHATSAPP_DAILY_LIMIT_PER_NUMBER`, `WHATSAPP_DAILY_LIMIT_TOTAL`. Add them to `.env.example` with placeholder values. If `WHATSAPP_TOKEN` is not set, the routes are not mounted and the app works as today.
- `docs/deploy.md`: a section "WhatsApp" with the steps the owner does in Meta's console (create the app, add WhatsApp, test number, add up to 5 recipient numbers, set the webhook URL `https://<space>/whatsapp/webhook` and the verify token, subscribe to `messages`).

## Acceptance tests (`tests/test_whatsapp.py`), no network (mock the HTTP calls and the agent)
1. GET with the right verify token returns the challenge; with a wrong one, 403.
2. POST with a bad signature returns 403; with a good one, 200, before the agent finishes.
3. A text message calls the agent once with that text and sends the "calculando" message and then the answer to the same `wa_id`.
4. An audio message downloads the media with the bearer token and passes the transcript to the agent.
5. A 9,000-character answer is sent as 3 messages, split at paragraph boundaries.
6. `**Plan**` becomes `*Plan*`.
7. The per-number daily limit stops the 21st question with the polite message.
8. Without `WHATSAPP_TOKEN`, the app builds and `/whatsapp/webhook` is not mounted.
9. All existing tests still pass.
