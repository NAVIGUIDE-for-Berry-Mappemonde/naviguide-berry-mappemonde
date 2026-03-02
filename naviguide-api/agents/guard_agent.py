"""
NAVIGUIDE Simulation Agent — Guard (Maritime Security)

LangGraph StateGraph — Pipeline:
  prepare_context → fetch_piracy_data → llm_generate → format_response → END

Domain: Security alerts, piracy zones, GMDSS/distress channels,
        heavy traffic separation schemes, COLREG specifics.
Sources: IMB Live Piracy Map (public), LLM training data.
Degrades gracefully: LLM only when IMB feed is unavailable.
"""

from __future__ import annotations

import httpx
from datetime import datetime, timezone
from typing import List, Optional

from langgraph.graph import StateGraph, END
from langchain_core.messages import HumanMessage, AIMessage
from typing_extensions import TypedDict

from .deploy_ai import call_llm
from .context_block import build_extra_context_block

# IMB Live Piracy & Armed Robbery Report (public JSON feed)
_IMB_FEED_URL = "https://www.icc-ccs.org/index.php/piracy-reporting-centre/live-piracy-map/details/json"
_IMB_TIMEOUT  = 8.0  # seconds


# ── State ──────────────────────────────────────────────────────────────────────

class GuardAgentState(TypedDict):
    from_stop:     str
    to_stop:       str
    lat:           float
    lon:           float
    nm_remaining:  float
    language:      str
    # Internal
    piracy_alerts: List[dict]
    prompt:        str
    messages:      List
    # Outputs
    content:       str
    data_sources:  List[str]
    data_freshness: str
    error:         Optional[str]


# ── Node 1: prepare_context ────────────────────────────────────────────────────

def prepare_context_node(state: GuardAgentState) -> GuardAgentState:
    msg = HumanMessage(
        content=f"[guard_agent] Preparing security brief for {state['from_stop']} → {state['to_stop']}"
    )
    return {**state, "piracy_alerts": [], "messages": [msg], "error": None}


# ── Node 2: fetch_piracy_data ──────────────────────────────────────────────────

def fetch_piracy_data_node(state: GuardAgentState) -> GuardAgentState:
    """
    Attempt to fetch recent piracy incidents from the IMB live feed.
    Filters incidents within a wide bounding box around the active leg.
    Falls back silently if the feed is unavailable.
    """
    alerts: List[dict] = []
    freshness = "training_only"

    try:
        with httpx.Client(timeout=_IMB_TIMEOUT) as client:
            resp = client.get(_IMB_FEED_URL)
            if resp.status_code == 200:
                data = resp.json()
                incidents = data if isinstance(data, list) else data.get("incidents", [])
                # Rough filter: ±15° bounding box around current position
                for inc in incidents[:50]:  # cap to avoid huge payloads
                    inc_lat = float(inc.get("lat", inc.get("latitude", 0)) or 0)
                    inc_lon = float(inc.get("lon", inc.get("longitude", 0)) or 0)
                    if abs(inc_lat - state["lat"]) < 15 and abs(inc_lon - state["lon"]) < 15:
                        alerts.append({
                            "date":    inc.get("date", ""),
                            "type":    inc.get("type", inc.get("incidentType", "Unknown")),
                            "vessel":  inc.get("vessel", ""),
                            "details": inc.get("details", inc.get("description", ""))[:200],
                        })
                freshness = "live" if alerts else "training_only"
    except Exception:
        pass  # graceful degradation — LLM will use training data

    msg = AIMessage(
        content=f"[guard_agent] IMB fetch: {len(alerts)} nearby incidents found "
                f"(freshness={freshness})"
    )
    return {**state, "piracy_alerts": alerts, "data_freshness": freshness, "messages": [msg]}


# ── Prompt builder (shared by llm_generate_node and get_streaming_prompt) ─────────

def _build_guard_prompt(state: GuardAgentState) -> str:
    """
    Build the LLM prompt from guard agent state.
    Requires prepare_context_node + fetch_piracy_data_node to have run first.
    """
    lang_full = "French" if state["language"] == "fr" else "English"
    alerts    = state["piracy_alerts"]

    if alerts:
        lines = [
            f"  • {a['date']} — {a['type']}: {a['details'][:120]}"
            for a in alerts[:5]
        ]
        alert_block = "RECENT IMB INCIDENTS (live feed):\n" + "\n".join(lines) + "\n\n"
    else:
        alert_block = "IMB live feed: no recent incidents retrieved near this position.\n\n"

    return (
        f"You are NAVIGUIDE's maritime security advisor for the Berry-Mappemonde "
        f"circumnavigation expedition (French offshore catamaran).\n\n"
        f"NAVIGATION CONTEXT:\n"
        f"• Active leg     : {state['from_stop']} → {state['to_stop']}\n"
        f"• Position       : {state['lat']:.4f}° lat / {state['lon']:.4f}° lon\n"
        f"• NM to next stop: {state['nm_remaining']:.0f} nm\n"
        f"• Response lang  : {lang_full}\n\n"
        f"{alert_block}"
        f"Provide a security briefing for this leg covering:\n"
        f"1. **Piracy risk level** — current threat assessment for this area (Low/Medium/High)\n"
        f"2. **Known risk zones** — specific zones or chokepoints to monitor on this leg\n"
        f"3. **GMDSS & distress** — primary distress channel, coastal radio stations, "
        f"rescue coordination centre (MRCC) contact\n"
        f"4. **Traffic density** — shipping lanes, TSS zones, AIS recommendations\n"
        f"5. **Security measures** — recommended watch schedule, check-in procedures, "
        f"SSAS activation guidance\n\n"
        f"Format in **Markdown**, fact-dense, max 350 words. "
        f"Mark any IMB-sourced data with [IMB Live]."
    )


# ── Node 3: llm_generate ──────────────────────────────────────────────────

def llm_generate_node(state: GuardAgentState) -> GuardAgentState:
    freshness = state.get("data_freshness", "training_only")
    prompt    = _build_guard_prompt(state)

    content, llm_freshness = call_llm(prompt)

    if not content:
        content = (
            f"## Security Brief — {state['from_stop']} → {state['to_stop']}\n\n"
            f"⚠️ **Security intelligence service unavailable.**\n\n"
            f"**Always monitor:**\n"
            f"- 📡 VHF Ch 16 (international distress & calling)\n"
            f"- 🔒 IMB Piracy Reporting Centre: +60 3 2078 5763\n"
            f"- 🌐 [ICC-IMB Live Map](https://www.icc-ccs.org)\n"
            f"- 🛰️ MRCC for your region\n\n"
            f"Maintain night watches and keep AIS transmitting at all times."
        )
        llm_freshness = "training_only"

    final_freshness = "live" if freshness == "live" else llm_freshness
    sources = ["deploy_ai_llm", "imb_piracy_training_data"]
    if state["piracy_alerts"]:
        sources.insert(0, "imb_live_feed")

    msg = AIMessage(
        content=f"[guard_agent] ✅ Security brief generated "
                f"({len(state['piracy_alerts'])} live incidents, freshness={final_freshness})"
    )
    return {
        **state,
        "content":        content,
        "data_sources":   sources,
        "data_freshness": final_freshness,
        "messages":       [msg],
    }


# ── Graph factory ──────────────────────────────────────────────────────────

def build_guard_agent():
    """Compile and return the Guard (Maritime Security) LangGraph."""
    graph = StateGraph(GuardAgentState)
    graph.add_node("prepare_context",   prepare_context_node)
    graph.add_node("fetch_piracy_data", fetch_piracy_data_node)
    graph.add_node("llm_generate",      llm_generate_node)
    graph.set_entry_point("prepare_context")
    graph.add_edge("prepare_context",   "fetch_piracy_data")
    graph.add_edge("fetch_piracy_data", "llm_generate")
    graph.add_edge("llm_generate",      END)
    return graph.compile()


# ── Convenience runner ──────────────────────────────────────────────────────────

def run_guard_agent(
    from_stop:    str,
    to_stop:      str,
    lat:          float,
    lon:          float,
    nm_remaining: float,
    language:     str = "fr",
) -> dict:
    """Invoke the Guard agent and return a serialisable AgentResponse dict."""
    agent = build_guard_agent()
    state = agent.invoke({
        "from_stop":     from_stop,
        "to_stop":       to_stop,
        "lat":           lat,
        "lon":           lon,
        "nm_remaining":  nm_remaining,
        "language":      language,
        "piracy_alerts": [],
        "prompt":        "",
        "messages":      [],
        "content":       "",
        "data_sources":  [],
        "data_freshness": "training_only",
        "error":         None,
    })
    return {
        "agent":          "guard",
        "content":        state["content"],
        "data_sources":   state["data_sources"],
        "generated_at":   datetime.now(timezone.utc).isoformat(),
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
    Run the data-fetch pipeline and return the built LLM prompt without calling the LLM.
    Used by the /agents/guard SSE endpoint: fetch runs synchronously in a threadpool,
    then the prompt is streamed token-by-token via deploy_ai.stream_llm().
    """
    initial = {
        "from_stop":     from_stop,
        "to_stop":       to_stop,
        "lat":           lat,
        "lon":           lon,
        "nm_remaining":  nm_remaining,
        "language":      language,
        "piracy_alerts": [],
        "prompt":        "",
        "messages":      [],
        "content":       "",
        "data_sources":  [],
        "data_freshness": "training_only",
        "error":         None,
    }
    state = prepare_context_node(initial)
    state = fetch_piracy_data_node(state)
    base_prompt = _build_guard_prompt(state)
    # TASK-017/018: Append enriched simulation context when available
    return base_prompt + build_extra_context_block(extra_context)
