"""
NAVIGUIDE — OpenRouter LLM helper (2-key cascade)
==================================================
Shared by:
  - naviguide_orchestrator/nodes.py  (expedition briefing)
  - naviguide_agent3/nodes.py        (risk assessment briefing)
  - polar_api/main.py                (polar chat)

Sister implementation kept in sync in:
  - /app/naviguide-api/agents/deploy_ai.py  (SSE agents — same logic, standalone module)

Design
------
Two-level cascade — KEY-first, then models within a key:

    for key in [KEY_1, KEY_2]:
        for model in HARDCODED_MODELS[:3]:
            attempt (key, model, timeout=20s)
            on 200                       → return
            on 429 "free-models-per-day" → break inner loop (jump to next key)
            on other 429 / 404 / timeout → continue to next model
        # if inner loop wasn't broken globally, try dynamic /v1/models with THIS key
        for model in dynamic_free_models(key)[:3]:
            same rules

If no (key × model) combination succeeded → return None.
Callers convert None to their fallback (static briefing / "LLM unavailable").

Rationale
---------
OpenRouter's `:free` daily quota is GLOBAL per key. When we detect
"free-models-per-day", further attempts with the SAME key are guaranteed
to 429 — jumping to the next key immediately saves time and log noise.

Key masking
-----------
Full keys are NEVER logged. Only the first 4 + last 4 characters appear
in `_mask()` output (e.g. `sk-o...de97b`).
"""
from __future__ import annotations
import os
import json
import socket
import time
import urllib.request
import urllib.error
from pathlib import Path
from typing import Callable, List, Optional, Tuple

from dotenv import load_dotenv

# Load /app/naviguide-api/.env once at import time
_ENV_FILE = Path(__file__).resolve().parent.parent / "naviguide-api" / ".env"
load_dotenv(_ENV_FILE)

_OR_BASE_URL   = "https://openrouter.ai/api/v1/chat/completions"
_OR_MODELS_URL = "https://openrouter.ai/api/v1/models"

# Hardcoded free models — kept IN SYNC across the 4 LLM pipelines.
# Legacy slugs (llama-3.1-8b, gemma-2-9b, qwen-2.5-72b, mistral-7b :free)
# returned 404 in August 2026. Do not put them back.
HARDCODED_MODELS = [
    "nvidia/nemotron-nano-12b-v2-vl:free",
    "nvidia/nemotron-nano-9b-v2:free",
    "google/gemma-4-31b-it:free",
    "google/gemma-4-26b-a4b-it:free",
]

_TIMEOUT_S = 20  # per attempt


def _mask(key: str) -> str:
    """Redact API key: keep first 4 + last 4 characters."""
    if not key:
        return "(none)"
    if len(key) <= 8:
        return "***"
    return f"{key[:4]}...{key[-4:]}"


def get_keys() -> List[Tuple[str, str]]:
    """Return list of (key_string, label) tuples in cascade order.

    Priority:
      OPENROUTER_API_KEY_1  (fallback to legacy OPENROUTER_API_KEY)
      OPENROUTER_API_KEY_2

    Empty / missing keys are silently filtered out.
    """
    def _clean(v):
        return (v or "").replace('"', "").replace("'", "").strip()

    k1 = _clean(os.getenv("OPENROUTER_API_KEY_1")) or _clean(os.getenv("OPENROUTER_API_KEY"))
    k2 = _clean(os.getenv("OPENROUTER_API_KEY_2"))
    out = []
    if k1:
        out.append((k1, "key1"))
    if k2:
        out.append((k2, "key2"))
    return out


def log_startup_config(log_prefix: str) -> None:
    """Emit a single line summarising the effective cascade at module load."""
    keys = get_keys()
    if not keys:
        print(f"🔧 {log_prefix}: 0 keys configured — LLM cascade WILL fail", flush=True)
        return
    key_summary = ", ".join(_mask(k) for k, _ in keys)
    print(
        f"🔧 {log_prefix}: {len(keys)} key(s) configured ({key_summary}), "
        f"cascade = [{len(HARDCODED_MODELS[:3])} hardcoded × {len(keys)} keys, then dynamic wave per key]",
        flush=True,
    )


def _try_one(key: str, key_label: str, model: str, messages: List[dict],
             max_tokens: int, wave: str, log_prefix: str) -> Tuple[Optional[str], str]:
    """Attempt one (key × model) call.

    Returns (content, category) where category is one of:
      'ok', '429-per-day', '429', '404', 'timeout', 'other'
    """
    url  = _OR_BASE_URL
    body = {
        "model":     model,
        "messages":  messages,
        "max_tokens": max_tokens,
        "provider":  {"data_collection": "allow"},
    }
    req = urllib.request.Request(
        url,
        data=json.dumps(body).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {key}",
            "Content-Type":  "application/json",
            "HTTP-Referer":  "http://localhost:5173",
            "X-Title":       "NAVIGUIDE",
        },
    )
    t0 = time.monotonic()
    try:
        with urllib.request.urlopen(req, timeout=_TIMEOUT_S) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            choices = data.get("choices") or []
            if choices:
                content = (choices[0].get("message") or {}).get("content") or ""
                # Strip common leakage lines from CoT-style models
                content = "\n".join(
                    ln for ln in content.splitlines()
                    if "thinking process" not in ln.lower()
                    and "<think>" not in ln.lower()
                ).strip()
                if content:
                    dt = time.monotonic() - t0
                    print(f"[llm] {key_label} × {model} → 200 ({len(content)} chars, {dt:.1f}s)", flush=True)
                    return content, "ok"
            return None, "other"

    except urllib.error.HTTPError as he:
        err_body = ""
        try:
            err_body = he.read().decode("utf-8", errors="ignore")[:300]
        except Exception:
            pass
        if he.code == 429:
            per_day = "free-models-per-day" in err_body
            cat = "429-per-day" if per_day else "429"
            reason = "free-models-per-day (key quota)" if per_day else "429 (model quota)"
            print(f"[llm] {key_label} × {model} → 429 {reason}", flush=True)
            return None, cat
        if he.code == 404:
            print(f"[llm] {key_label} × {model} → 404 model removed from free tier", flush=True)
            return None, "404"
        print(f"[llm] {key_label} × {model} → HTTP {he.code} — {err_body[:100]}", flush=True)
        return None, "other"

    except urllib.error.URLError as ue:
        if isinstance(ue.reason, socket.timeout):
            print(f"[llm] {key_label} × {model} → timeout (>{_TIMEOUT_S}s)", flush=True)
            return None, "timeout"
        print(f"[llm] {key_label} × {model} → URL error — {ue.reason}", flush=True)
        return None, "other"

    except socket.timeout:
        print(f"[llm] {key_label} × {model} → timeout (>{_TIMEOUT_S}s)", flush=True)
        return None, "timeout"

    except Exception as e:
        print(f"[llm] {key_label} × {model} → unexpected — {str(e)[:120]}", flush=True)
        return None, "other"


def _fetch_dynamic_models(key: str, exclude: List[str]) -> List[str]:
    """List free :free models from OpenRouter, excluding hardcoded ones."""
    try:
        req = urllib.request.Request(
            _OR_MODELS_URL,
            headers={"Authorization": f"Bearer {key}"},
        )
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            excl = set(exclude)
            return [
                m.get("id", "") for m in data.get("data", [])
                if m.get("id", "").endswith(":free") and m.get("id") not in excl
            ][:3]
    except Exception as e:
        print(f"[llm] dynamic /v1/models fetch failed: {e}", flush=True)
        return []


def try_openrouter(
    messages: List[dict],
    max_tokens: int = 800,
    log_prefix: str = "ORCH",
) -> Optional[str]:
    """Full 2-key × (hardcoded + dynamic) cascade.

    Args:
        messages    : OpenAI-format chat messages (system + user).
        max_tokens  : Max output tokens per attempt (defaults to 800).
        log_prefix  : Used only for the "all keys exhausted" line.

    Returns:
        LLM content string on first success, or None if every (key × model)
        combination failed. Caller is responsible for the fallback UX.
    """
    keys = get_keys()
    if not keys:
        print(f"[llm] {log_prefix}: ❌ no API keys configured", flush=True)
        return None

    for key, key_label in keys:
        exhausted = False  # True if this key hit free-models-per-day → skip to next

        # Wave 1 — hardcoded
        for model in HARDCODED_MODELS[:3]:
            content, cat = _try_one(key, key_label, model, messages, max_tokens, "hardcoded", log_prefix)
            if content:
                return content
            if cat == "429-per-day":
                exhausted = True
                break

        if exhausted:
            print(f"[llm] {key_label}: quota exhausted (free-models-per-day), switching key", flush=True)
            continue

        # Wave 2 — dynamic (only if key still has quota headroom)
        dyn = _fetch_dynamic_models(key, HARDCODED_MODELS)
        if dyn:
            print(f"[llm] {key_label}: hardcoded exhausted, trying dynamic {dyn}", flush=True)
        for model in dyn:
            content, cat = _try_one(key, key_label, model, messages, max_tokens, "dynamic", log_prefix)
            if content:
                return content
            if cat == "429-per-day":
                exhausted = True
                break

        if exhausted:
            print(f"[llm] {key_label}: quota exhausted mid-wave-2, switching key", flush=True)
            continue

    print(f"[llm] {log_prefix}: ❌ all keys × all models exhausted — caller should fallback", flush=True)
    return None
