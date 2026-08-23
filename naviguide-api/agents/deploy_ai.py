from __future__ import annotations
import os, json, urllib.request
from typing import AsyncIterator, List
from pathlib import Path
from dotenv import load_dotenv

env_file = Path(__file__).resolve().parents[1] / ".env"
load_dotenv(env_file)

_OR_BASE_URL = "https://openrouter.ai/api/v1/chat/completions"

def _build_messages(prompt: str, system_prompt: str = "") -> List[dict]:
    messages = []
    if system_prompt:
        messages.append({"role": "system", "content": system_prompt})
    messages.append({"role": "user", "content": prompt})
    return messages

def call_llm(prompt: str, system_prompt: str = "") -> str:
    key = os.getenv("OPENROUTER_API_KEY", "").replace('"', '').replace("'", "").strip()
    messages = _build_messages(prompt, system_prompt)
    models = [
        os.getenv("OPENROUTER_MODEL_1", "openrouter/free"),
        os.getenv("OPENROUTER_MODEL_2", "openrouter/auto")
    ]

    for model in models:
        try:
            req = urllib.request.Request(
                _OR_BASE_URL,
                data=json.dumps({
                    "model": model,
                    "messages": messages,
                    "provider": {"data_collection": "allow"}
                }).encode("utf-8"),
                headers={
                    "Authorization": f"Bearer {key}",
                    "Content-Type": "application/json",
                    "HTTP-Referer": "http://localhost:5173"
                }
            )
            with urllib.request.urlopen(req, timeout=20) as resp:
                res = json.loads(resp.read().decode("utf-8"))
                if "choices" in res and len(res["choices"]) > 0:
                    return res["choices"][0]["message"]["content"]
        except Exception:
            continue

    return "⚠️ LLM service temporarily unavailable."

async def stream_llm(prompt: str, system_prompt: str = "") -> AsyncIterator[str]:
    text = call_llm(prompt, system_prompt)
    yield text
