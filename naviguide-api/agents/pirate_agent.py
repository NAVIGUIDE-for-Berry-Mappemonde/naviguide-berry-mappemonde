"""
NAVIGUIDE Simulation Agent — Pirate (Community Intelligence)

LangGraph StateGraph — Pipeline:
  prepare_context → fetch_noonsite_rss → llm_generate → END

Domain: Cruiser community reports, Noonsite country briefs, blogger
        accounts, common anchorages, visa/currency tips, social stops.
Sources: Noonsite RSS feed (optional), LLM training data (forums/blogs).
"""

from __future__ import annotations

import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from typing import List, Optional

import httpx
from langgraph.graph import StateGraph, END
from langchain_core.messages import HumanMessage, AIMessage
from typing_extensions import TypedDict

from .deploy_ai import call_llm
from .context_block import build_extra_context_block

_NOONSITE_RSS_URL = "https://www.noonsite.com/feed/"
_NS_TIMEOUT       = 8.0


# ── State ──────────────────────────────────────────────────────────────────────

class PirateAgentState(TypedDict):
    from_stop:    str
    to_stop:      str
    lat:          float
    lon:          float
    nm_remaining: float
    language:     str
    # Internal
    noonsite_items: List[dict]
    prompt:       str
    messages:     List
    # Outputs
    content:      str
    data_sources: List[str]
    data_freshness: str
    error:        Optional[str]


# ── Node 1: prepare_context ────────────────────────────────────────────────────

def prepare_context_node(state: PirateAgentState) -> PirateAgentState:
    msg = HumanMessage(
        content=f"[pirate_agent] Preparing community intel for {state['from_stop']} → {state['to_stop']}"
    )
    return {**state, "noonsite_items": [], "messages": [msg], "error": None}


# ── Node 2: fetch_noonsite_rss ───────────────────────────────────────────────────

def fetch_noonsite_rss_node(state: PirateAgentState) -> PirateAgentState:
    """
    Fetch latest Noonsite RSS items and filter for relevant destination keywords.
    Falls back gracefully if feed is unreachable.
    """
    items: List[dict] = []
    freshness = "training_only"
    to_stop   = state["to_stop"]

    # Keywords to search for in RSS items
    keywords = [
        w.lower() for w in to_stop.replace("-", " ").split()
        if len(w) > 3
    ] + [state["from_stop"].lower()[:6]]

    try:
        with httpx.Client(timeout=_NS_TIMEOUT) as client:
            resp = client.get(_NOONSITE_RSS_URL, follow_redirects=True)
            if resp.status_code == 200:
                root = ET.fromstring(resp.text)
                channel = root.find("channel")
                if channel is not None:
                    for item in channel.findall("item")[:40]:
                        title       = (item.findtext("title") or "").strip()
                        description = (item.findtext("description") or "").strip()
                        link        = (item.findtext("link") or "").strip()
                        pub_date    = (item.findtext("pubDate") or "").strip()

                        combined = (title + " " + description).lower()
                        if any(kw in combined for kw in keywords):
                            items.append({
                                "title":    title,
                                "summary":  description[:300],
                                "link":     link,
                                "pub_date": pub_date,
                            })

                if items:
                    freshness = "live"

    except Exception:
        pass  # silent degradation

    msg = AIMessage(
        content=f"[pirate_agent] Noonsite RSS: {len(items)} relevant items "
                f"for {to_stop} (freshness={freshness})"
    )
    return {**state, "noonsite_items": items, "data_freshness": freshness, "messages": [msg]}


# ── Prompt builder (shared by llm_generate_node and get_streaming_prompt) ─────────

def _build_pirate_prompt(state: PirateAgentState) -> str:
    """
    Build the LLM prompt from pirate agent state.
    Requires prepare_context_node + fetch_noonsite_rss_node to have run first.
    """
    lang_full = "French" if state["language"] == "fr" else "English"
    items     = state["noonsite_items"]
    now_month = datetime.now().strftime("%B")

    if items:
        entries = "\n".join(
            f"  • [{i['pub_date'][:16]}] {i['title']}: {i['summary'][:150]}"
            for i in items[:5]
        )
        noonsite_block = f"NOONSITE RECENT REPORTS:\n{entries}\n\n"
    else:
        noonsite_block = (
            "Noonsite live feed: no recent items retrieved for this destination. "
            "Using cruiser community knowledge from training data.\n\n"
        )

    return (
        f"You are NAVIGUIDE's cruiser community intelligence advisor for the Berry-Mappemonde "
        f"circumnavigation expedition (French crew, offshore catamaran, open ocean passage).\n\n"
        f"NAVIGATION CONTEXT:\n"
        f"• Active leg     : {state['from_stop']} → {state['to_stop']}\n"
        f"• Position       : {state['lat']:.4f}° lat / {state['lon']:.4f}° lon\n"
        f"• NM to next stop: {state['nm_remaining']:.0f} nm\n"
        f"• Current month  : {now_month}\n"
        f"• Response lang  : {lang_full}\n\n"
        f"{noonsite_block}"
        f"Provide a community intelligence brief for **{state['to_stop']}** covering:\n"
        f"1. **Social stop quality** — is this a destination where cruisers typically "
        f"spend extra time? Rating (★★★☆☆) with reason\n"
        f"2. **Cruiser tips** — top 3 practical tips shared by sailors who've been here\n"
        f"3. **Local culture** — key cultural norms, dress code (especially on shore), "
        f"religious/social customs the crew must respect\n"
        f"4. **Provisioning intel** — real-world observations: what's actually available, "
        f"what to stock up on BEFORE arriving\n"
        f"5. **Hidden gems** — one anchorage, restaurant or experience that cruisers "
        f"recommend but isn't in standard guides\n\n"
        f"Base your answer on Noonsite, cruising forums (Cruiser's Forum, Sailing Anarchy), "
        f"and sailing blogs. Format in **Markdown**, conversational tone, max 350 words. "
        f"Mark Noonsite-sourced items with [Noonsite]."
    )


# ── Node 3: llm_generate ──────────────────────────────────────────────────

def llm_generate_node(state: PirateAgentState) -> PirateAgentState:
    items     = state["noonsite_items"]
    freshness = state.get("data_freshness", "training_only")
    prompt    = _build_pirate_prompt(state)

    content, llm_freshness = call_llm(prompt)

    if not content:
        content = (
            f"## Communauté — {state['to_stop']}\n\n"
            f"⚠️ **Service intelligence communautaire indisponible.**\n\n"
            f"**Ressources communautaires :**\n"
            f"- 🌐 [Noonsite — {state['to_stop']}](https://www.noonsite.com)\n"
            f"- 💬 [Cruisers Forum](https://www.cruisersforum.com)\n"
            f"- 📘 Relevant pilot book for this region\n\n"
            f"Distance restante : **{state['nm_remaining']:.0f} nm**."
        )
        freshness = "training_only"

    final_freshness = "live" if items else llm_freshness or "training_only"
    sources = ["deploy_ai_llm", "cruisers_forum_training", "sailing_blogs_training"]
    if items:
        sources.insert(0, "noonsite_rss_live")

    msg = AIMessage(
        content=f"[pirate_agent] ✅ Community brief generated "
                f"({len(items)} Noonsite items, freshness={final_freshness})"
    )
    return {
        **state,
        "content":        content,
        "data_sources":   sources,
        "data_freshness": final_freshness,
        "messages":       [msg],
    }


# ── Graph factory ──────────────────────────────────────────────────────────

def build_pirate_agent():
    """Compile and return the Pirate (Community Intelligence) LangGraph."""
    graph = StateGraph(PirateAgentState)
    graph.add_node("prepare_context",    prepare_context_node)
    graph.add_node("fetch_noonsite_rss",  fetch_noonsite_rss_node)
    graph.add_node("llm_generate",        llm_generate_node)
    graph.set_entry_point("prepare_context")
    graph.add_edge("prepare_context",     "fetch_noonsite_rss")
    graph.add_edge("fetch_noonsite_rss",  "llm_generate")
    graph.add_edge("llm_generate",        END)
    return graph.compile()


# ── Convenience runner ──────────────────────────────────────────────────────────

def run_pirate_agent(
    from_stop:    str,
    to_stop:      str,
    lat:          float,
    lon:          float,
    nm_remaining: float,
    language:     str = "fr",
) -> dict:
    """Invoke the Pirate agent and return a serialisable AgentResponse dict."""
    agent = build_pirate_agent()
    state = agent.invoke({
        "from_stop":      from_stop,
        "to_stop":        to_stop,
        "lat":            lat,
        "lon":            lon,
        "nm_remaining":   nm_remaining,
        "language":       language,
        "noonsite_items": [],
        "prompt":         "",
        "messages":       [],
        "content":        "",
        "data_sources":   [],
        "data_freshness": "training_only",
        "error":          None,
    })
    return {
        "agent":          "pirate",
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
    Used by the /agents/pirate SSE endpoint: Noonsite RSS fetch runs synchronously in a
    threadpool, then the prompt is streamed token-by-token via deploy_ai.stream_llm().
    """
    initial = {
        "from_stop":      from_stop,
        "to_stop":        to_stop,
        "lat":            lat,
        "lon":            lon,
        "nm_remaining":   nm_remaining,
        "language":       language,
        "noonsite_items": [],
        "prompt":         "",
        "messages":       [],
        "content":        "",
        "data_sources":   [],
        "data_freshness": "training_only",
        "error":          None,
    }
    state = prepare_context_node(initial)
    state = fetch_noonsite_rss_node(state)
    base_prompt = _build_pirate_prompt(state)
    # TASK-017/018: Append enriched simulation context when available
    return base_prompt + build_extra_context_block(extra_context)
