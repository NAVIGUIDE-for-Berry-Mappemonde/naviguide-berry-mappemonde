"""
NAVIGUIDE — agents/deploy_ai.py
================================
LLM helper used by the 4 SSE agent endpoints (/api/agents/{meteo, pirate,
guard, custom}) in naviguide-api/main.py.

Delegates to the shared `_openrouter.py` helper in /app/naviguide_workspace/
so the 2-key × (hardcoded + dynamic) cascade stays IN SYNC across all 4
LLM pipelines (orchestrator briefing, agent3 briefing, polar chat, SSE agents).

Streaming: NOT touched. The `stream_llm()` coroutine still yields the entire
LLM response as a single SSE chunk. Real token-by-token streaming would
require migrating to /app/naviguide-api/deploy_ai.py (httpx SSE) — out of
scope.
"""
from __future__ import annotations
import sys
from pathlib import Path
from typing import AsyncIterator, List

# Path to the shared helper — one level up from /app/naviguide-api/, then
# into /app/naviguide_workspace/. Injected in sys.path once at module load.
_WORKSPACE = Path(__file__).resolve().parents[2] / "naviguide_workspace"
if str(_WORKSPACE) not in sys.path:
    sys.path.insert(0, str(_WORKSPACE))

from _openrouter import try_openrouter, log_startup_config  # noqa: E402

_ERROR_UNAVAILABLE = "⚠️ LLM service temporarily unavailable."

log_startup_config("AGENTS")


def _build_messages(prompt: str, system_prompt: str = "") -> List[dict]:
    messages = []
    if system_prompt:
        messages.append({"role": "system", "content": system_prompt})
    messages.append({"role": "user", "content": prompt})
    return messages


def call_llm(prompt: str, system_prompt: str = "") -> str:
    """2-key × (hardcoded + dynamic) cascade with UI-safe fallback message."""
    messages = _build_messages(prompt, system_prompt)
    content  = try_openrouter(messages, max_tokens=800, log_prefix="AGENTS")
    return content if content else _ERROR_UNAVAILABLE


async def stream_llm(prompt: str, system_prompt: str = "") -> AsyncIterator[str]:
    """SSE stream — 1 chunk (see module docstring)."""
    text = call_llm(prompt, system_prompt)
    yield text
