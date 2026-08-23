# NOTE: currently unused. Real streaming (httpx SSE) implementation kept
# for future migration. The 4 /agents/* endpoints in main.py currently import
# from `agents.deploy_ai` (urllib, non-streaming) instead. Do not delete
# without migrating the 4 agent endpoints first.
from __future__ import annotations
import asyncio
import json
import os
from pathlib import Path
from typing import AsyncIterator, List

import httpx
from dotenv import load_dotenv

# Load .env once at module import — avoids re-loading on every LLM call
env_file = Path(__file__).resolve().parents[1] / ".env"
load_dotenv(env_file)

_OR_BASE_URL = "https://openrouter.ai/api/v1/chat/completions"

# Stable free model cascade — ordered by quality / availability
_OR_MODELS = [
    "meta-llama/llama-3.1-8b-instruct:free",
    "google/gemma-2-9b-it:free",
    "qwen/qwen-2.5-72b-instruct:free",
    "mistralai/mistral-7b-instruct:free",
]

_OR_HEADERS_BASE = {
    "HTTP-Referer": "http://localhost:5173",
    "X-Title":      "NAVIGUIDE",
}


def _get_key() -> str:
    return os.getenv("OPENROUTER_API_KEY", "").replace('"', "").replace("'", "").strip()


def _build_messages(prompt: str, system_prompt: str = "") -> List[dict]:
    messages: List[dict] = []
    if system_prompt:
        messages.append({"role": "system", "content": system_prompt})
    messages.append({"role": "user", "content": prompt})
    return messages


# ── Sync call (used by non-async callers) ─────────────────────────────────────

def call_llm(prompt: str, system_prompt: str = "") -> str:
    """
    Synchronous OpenRouter call via httpx.
    Tries each model in _OR_MODELS in order; returns the first non-empty response.
    Safe to call from sync code (e.g. background threads).
    """
    key = _get_key()
    messages = _build_messages(prompt, system_prompt)

    for model in _OR_MODELS:
        try:
            with httpx.Client(timeout=45.0) as client:
                resp = client.post(
                    _OR_BASE_URL,
                    headers={
                        "Authorization": f"Bearer {key}",
                        "Content-Type":  "application/json",
                        **_OR_HEADERS_BASE,
                    },
                    json={
                        "model":    model,
                        "messages": messages,
                        "max_tokens": 1200,
                        "provider": {"data_collection": "allow"},
                    },
                )
                if resp.status_code == 200:
                    data = resp.json()
                    content = (
                        data.get("choices", [{}])[0]
                        .get("message", {})
                        .get("content", "")
                    )
                    if content:
                        return content
        except Exception:
            continue

    return "⚠️ LLM service temporarily unavailable."


# ── Async streaming call (FastAPI SSE endpoints) ──────────────────────────────

async def stream_llm(prompt: str, system_prompt: str = "") -> AsyncIterator[str]:
    """
    Real token-by-token SSE streaming via httpx.AsyncClient.
    Falls back to a single-chunk non-blocking call if streaming fails.
    Never blocks the FastAPI event loop.
    """
    key = _get_key()
    messages = _build_messages(prompt, system_prompt)

    for model in _OR_MODELS:
        try:
            async with httpx.AsyncClient(timeout=60.0) as client:
                async with client.stream(
                    "POST",
                    _OR_BASE_URL,
                    headers={
                        "Authorization": f"Bearer {key}",
                        "Content-Type":  "application/json",
                        **_OR_HEADERS_BASE,
                    },
                    json={
                        "model":    model,
                        "messages": messages,
                        "max_tokens": 1200,
                        "stream":   True,
                        "provider": {"data_collection": "allow"},
                    },
                ) as response:
                    if response.status_code != 200:
                        continue
                    got_content = False
                    async for line in response.aiter_lines():
                        if not line.startswith("data: "):
                            continue
                        data = line[6:].strip()
                        if data == "[DONE]":
                            break
                        try:
                            chunk = json.loads(data)
                            delta = (
                                chunk.get("choices", [{}])[0]
                                .get("delta", {})
                                .get("content", "")
                            )
                            if delta:
                                got_content = True
                                yield delta
                        except (json.JSONDecodeError, IndexError, KeyError):
                            continue
                    if got_content:
                        return   # streaming succeeded — done
        except Exception:
            continue

    # ── Fallback: non-streaming, run sync call in executor to avoid blocking ──
    loop = asyncio.get_event_loop()
    text = await loop.run_in_executor(None, call_llm, prompt, system_prompt)
    yield text
