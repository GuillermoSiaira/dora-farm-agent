# Deploying DORA to Hugging Face Spaces

This guide outlines the steps to publish the DORA demo application to a Hugging Face Space.

---

## 1. Create the Space on Hugging Face

1. Log into your account at [huggingface.co](https://huggingface.co).
2. Click **New Space** (or navigate to `https://huggingface.co/new-space`).
3. Set the parameters:
   - **Space name**: `dora-farm-agent` (or your preferred name).
   - **License**: Choose your preferred open source license (e.g., Apache 2.0 or MIT).
   - **SDK**: Select **Gradio**.
   - **Hardware**: Standard CPU (free tier is sufficient; the engine and UI run locally in Python without heavy local GPU requirements).
   - **Visibility**: Public (recommended for demo and hackathon evaluation).
4. Click **Create Space**.

---

## 2. Connect and Push Repository Code

The `README.md` at the root of this repository already contains the required Space front matter:
```yaml
---
title: DORA Farm Agent
sdk: gradio
app_file: app.py
pinned: false
---
```

You can sync your repository to Hugging Face via Git:

```bash
# Add Hugging Face Space as a remote
git remote add space https://huggingface.co/spaces/<your-username>/dora-farm-agent

# Push branch to Space main branch
git push space <your-branch>:main --force
```

Alternatively, you can set up a GitHub Action to automatically mirror pushes to the Space.

---

## 3. Configure Secrets

The core optimization engine and Scenario tab run entirely standalone without any external API keys. However, the **Chat with DORA** tab and model commentary require LLM credentials.

Configure secrets directly in the Hugging Face Space settings:
1. Navigate to your Space's **Settings** tab.
2. Under **Variables and secrets**, add the following **Secrets**:
   - `DORA_API_KEY`: Your API key for the Meta model provider (e.g., Together AI, Groq, Fireworks, or OpenRouter).
   - `DORA_API_BASE`: (Optional) Base URL if using a custom OpenAI-compatible endpoint (e.g., `https://api.together.xyz/v1`).
   - `DORA_MODEL`: (Optional) Model name to use (defaults to `meta-llama/Llama-3.3-70B-Instruct-Turbo` or provider equivalent).

> [!IMPORTANT]
> Never commit API keys or credentials to Git files. The application exclusively reads credentials from the environment (`DORA_API_KEY`, `DORA_API_BASE`, `DORA_MODEL`).

---

## 4. Verify Build and Runtime Logs

1. Go to the **App** and **Logs** tabs on your Space page.
2. Watch the container build: Hugging Face automatically installs dependencies from `requirements.txt`.
3. The server starts using `app.py`, listening on `0.0.0.0:7860`.
4. Verify the tabs:
   - **Escenario / Scenario**: Run an optimization to confirm HiGHS and Plotly work.
   - **Regiones / Regional Observatory**: Verify the interactive Leaflet map and regional metrics load.
   - **Chat con DORA**: If `DORA_API_KEY` was configured, verify the chatbot responds and verifies numbers.
