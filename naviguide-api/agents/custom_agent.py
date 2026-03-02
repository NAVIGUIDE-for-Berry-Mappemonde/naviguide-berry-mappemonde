"""
NAVIGUIDE Simulation Agent — Custom (Port & Customs Intelligence)

LangGraph StateGraph — Pipeline:
  prepare_context → llm_generate → format_response → END

Domain: Port entry requirements, customs/immigration, marina fees,
        provisioning, anchorage options, VHF/authority contacts.
Sources: Deploy AI LLM (trained on WPI data, cruising guides).
"""

from __future__ import annotations

import math
from datetime import datetime, timezone
from typing import List, Optional

from langgraph.graph import StateGraph, END
from langchain_core.messages import HumanMessage, AIMessage
from typing_extensions import TypedDict

from .deploy_ai import call_llm
from .context_block import build_extra_context_block


# ── State ──────────────────────────────────────────────────────────────────────

class CustomAgentState(TypedDict):
    # Inputs
    from_stop:    str
    to_stop:      str
    lat:          float
    lon:          float
    nm_remaining: float
    language:     str
    # Internal
    prompt:       str
    messages:     List
    # Outputs
    content:      str
    data_sources: List[str]
    data_freshness: str
    error:        Optional[str]


# ── Node 1: prepare_context ────────────────────────────────────────────────────

def prepare_context_node(state: CustomAgentState) -> CustomAgentState:
    """Build the structured prompt for the Port Intelligence LLM."""
    lang_full = "French" if state["language"] == "fr" else "English"
    nm        = state["nm_remaining"]
    to_stop   = state["to_stop"]
    from_stop = state["from_stop"]

    prompt = (
        f"You are NAVIGUIDE's port intelligence advisor for the Berry-Mappemonde "
        f"circumnavigation expedition (French catamaran, 13.5 m, LOA, draft 1.8 m).\n\n"
        f"NAVIGATION CONTEXT:\n"
        f"• Current leg      : {from_stop} → {to_stop}\n"
        f"• Position         : {state['lat']:.4f}° lat / {state['lon']:.4f}° lon\n"
        f"• Distance to port : {nm:.0f} nautical miles\n"
        f"• Response language: {lang_full}\n\n"
        f"Provide a port briefing for **{to_stop}** covering:\n"
        f"1. **Entry formalities** — required documents, clearance procedures, "
        f"customs & immigration contacts (phone / VHF)\n"
        f"2. **Marina & anchorage** — recommended marinas, anchorage areas, "
        f"approximate overnight fees (local currency & USD)\n"
        f"3. **Provisioning** — nearest supermarket, fuel dock, fresh water\n"
        f"4. **Port authority** — VHF working channel, harbour master contact\n"
        f"5. **One critical tip** — the single most important thing to know "
        f"before arriving at this port\n\n"
        f"Format in **Markdown**, concise and actionable for an offshore crew. "
        f"Max 350 words. Start directly with the port name as heading."
    )

    msg = HumanMessage(content=f"[custom_agent] Preparing port brief for {to_stop}")
    return {
        **state,
        "prompt":   prompt,
        "messages": [msg],
        "error":    None,
    }


# ── Node 2: llm_generate ──────────────────────────────────────────────────

def llm_generate_node(state: CustomAgentState) -> CustomAgentState:
    """Call Deploy AI to generate the port intelligence brief."""
    content, freshness = call_llm(state["prompt"])

    if not content:
        to_stop = state["to_stop"]
        content = (
            f"## {to_stop} — Port Intelligence\n\n"
            f"⚠️ **LLM service temporarily unavailable.**\n\n"
            f"**Recommended resources:**\n"
            f"- 🌐 [Noonsite](https://www.noonsite.com) — "
            f"search for {to_stop} port entry requirements\n"
            f"- 📖 Local pilot charts & sailing almanac\n"
            f"- 📡 VHF Ch 16 → harbour authority on arrival\n\n"
            f"Distance remaining: **{state['nm_remaining']:.0f} nm**."
        )
        freshness = "training_only"

    msg = AIMessage(content=f"[custom_agent] ✅ Port brief generated for {state['to_stop']}")
    return {
        **state,
        "content":        content,
        "data_sources":   ["deploy_ai_llm", "wpi_training_data", "cruising_guides"],
        "data_freshness": freshness,
        "messages":       [msg],
    }


# ── Graph factory ──────────────────────────────────────────────────────────

def build_custom_agent():
    """Compile and return the Custom (Port Intelligence) LangGraph."""
    graph = StateGraph(CustomAgentState)
    graph.add_node("prepare_context", prepare_context_node)
    graph.add_node("llm_generate",    llm_generate_node)
    graph.set_entry_point("prepare_context")
    graph.add_edge("prepare_context", "llm_generate")
    graph.add_edge("llm_generate",    END)
    return graph.compile()


# ── Convenience runner ──────────────────────────────────────────────────────────

def run_custom_agent(
    from_stop:    str,
    to_stop:      str,
    lat:          float,
    lon:          float,
    nm_remaining: float,
    language:     str = "fr",
) -> dict:
    """
    Invoke the Custom agent and return a serialisable AgentResponse dict.
    """
    agent = build_custom_agent()
    state = agent.invoke({
        "from_stop":    from_stop,
        "to_stop":      to_stop,
        "lat":          lat,
        "lon":          lon,
        "nm_remaining": nm_remaining,
        "language":     language,
        "prompt":       "",
        "messages":     [],
        "content":      "",
        "data_sources": [],
        "data_freshness": "training_only",
        "error":        None,
    })
    return {
        "agent":         "custom",
        "content":       state["content"],
        "data_sources":  state["data_sources"],
        "generated_at":  datetime.now(timezone.utc).isoformat(),
        "data_freshness": state["data_freshness"],
    }


# ── Streaming helper ──────────────────────────────────────────────────────────

def get_streaming_prompt(
    from_stop:    str,
    to_stop:      str,
    lat:          float,
    lon:          float,
    nm_remaining: float,
    language:     str = "fr",
    extra_context: dict = None,
) -> str:
    """
    Build and return the LLM prompt for the Custom agent without calling the LLM.
    Used by the /agents/custom SSE endpoint to enable true token-by-token streaming:
    the endpoint fetches this prompt synchronously (in a threadpool), then streams
    tokens via deploy_ai.stream_llm().
    """
    state = prepare_context_node({
        "from_stop":    from_stop,
        "to_stop":      to_stop,
        "lat":          lat,
        "lon":          lon,
        "nm_remaining": nm_remaining,
        "language":     language,
        "prompt":       "",
        "messages":     [],
        "content":      "",
        "data_sources": [],
        "data_freshness": "training_only",
        "error":        None,
    })
    base_prompt = state.get("prompt", "")
    # TASK-017/018: Append enriched simulation context when available
    return base_prompt + build_extra_context_block(extra_context)
