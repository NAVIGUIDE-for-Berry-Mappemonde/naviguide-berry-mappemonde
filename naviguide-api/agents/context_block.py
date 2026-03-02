"""
NAVIGUIDE — SimulationContextPayload → LLM prompt block (TASK-017/018)

Shared helper that converts the enriched simulation context sent by the
frontend into a structured text section appended to every agent prompt.

Usage:
    from .context_block import build_extra_context_block
    extra = build_extra_context_block(extra_context)  # extra_context may be None
    full_prompt = base_prompt + extra
"""

from __future__ import annotations
from typing import Optional


def build_extra_context_block(ctx: Optional[dict]) -> str:
    """
    Format a SimulationContextPayload dict into a readable LLM context section.

    Returns an empty string when ctx is None or empty (backward-compat).
    Each data source is labelled so the LLM can cite it appropriately.
    """
    if not ctx:
        return ""

    lines: list[str] = [
        "\n\n── LIVE SIMULATION CONTEXT (from onboard sensors & expedition plan) ───",
    ]

    # ── Navigation leg ────────────────────────────────────────────────────────
    leg = ctx.get("leg") or {}
    if leg:
        parts = []
        if leg.get("bearing")     is not None: parts.append(f"cap {leg['bearing']}°")
        if leg.get("nm_covered")  is not None: parts.append(f"{leg['nm_covered']:.0f} nm couverts")
        if leg.get("eta_hours")   is not None: parts.append(f"ETA {leg['eta_hours']:.1f} h")
        if leg.get("speed_knots") is not None: parts.append(f"vitesse {leg['speed_knots']:.1f} kts")
        if parts:
            lines.append("NAV LIVE : " + " | ".join(parts))

    # ── Copernicus live weather ───────────────────────────────────────────────
    weather = ctx.get("weather") or {}
    if weather:
        lines.append("COPERNICUS [Live] :")
        wind    = weather.get("wind")    or {}
        wave    = weather.get("wave")    or {}
        current = weather.get("current") or {}
        if wind:
            spd = wind.get("speed") or wind.get("speed_kts") or "N/A"
            drn = wind.get("direction") or wind.get("dir_deg") or "N/A"
            lines.append(f"  • Vent    : {spd} kts / {drn}°")
        if wave:
            h = wave.get("height") or wave.get("height_m") or "N/A"
            p = wave.get("period") or wave.get("period_s") or "N/A"
            lines.append(f"  • Mer     : {h} m / période {p} s")
        if current:
            spd = current.get("speed") or current.get("speed_kts") or "N/A"
            drn = current.get("direction") or current.get("dir_deg") or "N/A"
            lines.append(f"  • Courant : {spd} kts @ {drn}°")

    # ── Polar performance ─────────────────────────────────────────────────────
    polar = ctx.get("polar") or {}
    if polar and polar.get("has_polar"):
        polar_parts = []
        if polar.get("vmg_upwind")   is not None: polar_parts.append(f"VMG ↑ {polar['vmg_upwind']:.1f} kts")
        if polar.get("vmg_downwind") is not None: polar_parts.append(f"VMG ↓ {polar['vmg_downwind']:.1f} kts")
        if polar.get("optimal_twa")  is not None: polar_parts.append(f"TWA optimal {polar['optimal_twa']:.0f}°")
        if polar_parts:
            lines.append("POLAIRE [Polar] : " + " | ".join(polar_parts))

    # ── Segment risk indicators ───────────────────────────────────────────────
    seg = ctx.get("segment_alerts") or {}
    if seg:
        w = seg.get("wind_points", 0) or 0
        v = seg.get("wave_points", 0) or 0
        c = seg.get("current_points", 0) or 0
        if (w + v + c) > 0:
            lines.append(
                f"ALERTES SEGMENT : vent {w} pts · mer {v} pts · courant {c} pts"
            )

    # ── Expedition plan ───────────────────────────────────────────────────────
    exp = ctx.get("expedition") or {}
    if exp:
        briefing = (exp.get("executive_briefing") or "").strip()
        if briefing:
            # Truncate to 400 chars to stay within token budget
            lines.append(f"PLAN EXPÉDITION [Plan] : {briefing[:400]}")

        alerts = exp.get("critical_alerts") or []
        if alerts:
            lines.append(f"ALERTES CRITIQUES ({len(alerts)}) :")
            for a in alerts[:3]:
                lines.append(f"  ⚠️  {str(a)[:140]}")

        stats = exp.get("voyage_statistics") or {}
        total_nm = (
            stats.get("total_nm")
            or stats.get("total_distance_nm")
            or stats.get("totalNm")
        )
        if total_nm:
            lines.append(f"VOYAGE TOTAL : {float(total_nm):.0f} nm")

    # ── User-drawn waypoints ──────────────────────────────────────────────────
    waypoints = ctx.get("drawn_waypoints") or []
    if waypoints:
        lines.append(f"WAYPOINTS ÉQUIPAGE ({len(waypoints)}) :")
        for w in waypoints[:5]:
            name = w.get("name", "?")
            lat  = w.get("lat")
            lon  = w.get("lon")
            coord = f"{lat:.3f}, {lon:.3f}" if lat is not None and lon is not None else "?"
            lines.append(f"  • {name} ({coord})")

    lines.append(
        "─────────────────────────────────────────────────────────────────────\n"
    )
    return "\n".join(lines)
