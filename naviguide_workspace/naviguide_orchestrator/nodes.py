from __future__ import annotations
import logging
log = logging.getLogger("orchestrator")
"""
NAVIGUIDE Orchestrator — LangGraph Node Functions

Orchestration flow:
  validate_expedition_request
           │ error ──────────────────────────────────────► END
           ▼
  run_route_intelligence          ← invokes Agent 1 graph directly
           │ agent1_failed ───────────────────────────────► END
           ▼
  run_risk_assessment             ← invokes Agent 3 graph (with Agent 1 route)
           ▼
  llm_expedition_briefing         ← Groq/qwen3.6-27b unified skipper executive summary
           ▼
  generate_expedition_plan        ← merge Agent 1 + Agent 3 → digital twin
           ▼
          END
"""

import sys
import os
import logging
from datetime import datetime
from pathlib import Path
import json
import httpx
from langchain_core.messages import HumanMessage, AIMessage

def _call_openrouter(prompt: str, max_tokens: int = 1200, language: str = "fr"):
    """
    Call OpenRouter with language-aware system prompt.
    language: 'fr' (default) or 'en' — controls system message AND briefing language.
    Returns the LLM content string, or None on total failure.
    """
    import os
    import json
    import urllib.request
    from pathlib import Path
    from dotenv import load_dotenv

    root_dir = Path(__file__).resolve().parents[2]
    env_file = root_dir / "naviguide-api" / ".env"
    load_dotenv(env_file)

    key = os.getenv("OPENROUTER_API_KEY", "").replace('"', '').replace("'", "").strip()
    if not key:
        print("❌ ORCHESTRATEUR: OPENROUTER_API_KEY introuvable dans naviguide-api/.env")
        return None

    models_to_try = [
        "meta-llama/llama-3.1-8b-instruct:free",
        "google/gemma-2-9b-it:free",
        "qwen/qwen-2.5-72b-instruct:free",
        "mistralai/mistral-7b-instruct:free",
    ]

    try:
        req_m = urllib.request.Request("https://openrouter.ai/api/v1/models")
        with urllib.request.urlopen(req_m, timeout=5) as resp_m:
            data = json.loads(resp_m.read().decode("utf-8"))
            for m in data.get("data", []):
                m_id = m.get("id", "")
                if m_id.endswith(":free") and m_id not in models_to_try:
                    models_to_try.insert(0, m_id)
    except Exception as e:
        print(f"⚠️ ORCHESTRATEUR: Impossible de lister les modèles: {e}")

    # ── Language-aware system prompt ───────────────────────────────────────────
    if language == "en":
        system_content = (
            "You are the NAVIGUIDE Expedition Director, expert in offshore circumnavigations. "
            "Write a complete, ultra-professional skipper briefing in English. "
            "Do NOT show any internal reasoning or text in French."
        )
    else:
        system_content = (
            "Tu es le Directeur d'Expédition NAVIGUIDE, expert en circumnavigations hauturières. "
            "Rédige un briefing skipper complet, ultra-professionnel en français. "
            "Ne montre AUCUNE réflexion interne ni texte en anglais."
        )

    messages = [
        {"role": "system", "content": system_content},
        {"role": "user",   "content": prompt},
    ]

    for model in models_to_try[:6]:
        try:
            print(f"🔄 ORCHESTRATEUR: Tentative via {model} (lang={language})...")
            req = urllib.request.Request(
                "https://openrouter.ai/api/v1/chat/completions",
                data=json.dumps({
                    "model":    model,
                    "messages": messages,
                    "max_tokens": max_tokens,
                    "provider": {"data_collection": "allow"},
                }).encode("utf-8"),
                headers={
                    "Authorization": f"Bearer {key}",
                    "Content-Type":  "application/json",
                    "HTTP-Referer":  "http://localhost:5173",
                    "X-Title":       "NAVIGUIDE",
                },
            )
            with urllib.request.urlopen(req, timeout=45) as resp:
                res = json.loads(resp.read().decode("utf-8"))
                if "choices" in res and len(res["choices"]) > 0:
                    content = res["choices"][0]["message"].get("content") or ""
                    # Strip internal reasoning lines (some models leak them)
                    lines_clean = [
                        l for l in content.splitlines()
                        if "thinking process" not in l.lower()
                        and "<think>" not in l.lower()
                    ]
                    content = "\n".join(lines_clean).strip()
                    if content:
                        print(f"✅ ORCHESTRATEUR: Briefing généré via {model} (lang={language}) !")
                        return content
        except Exception as e:
            err_msg = e.read().decode("utf-8") if hasattr(e, "read") else str(e)
            print(f"❌ ORCHESTRATEUR: Échec sur {model} -> {err_msg[:120]}")
            continue

    print("❌ ORCHESTRATEUR: Tous les modèles OpenRouter ont échoué. Passage au fallback.")
    return None

def _get_agent1():
    try:
        from naviguide_agent1.graph import build_route_intelligence_agent
        return build_route_intelligence_agent()
    except Exception:
        return None


def _get_agent3():
    try:
        from naviguide_agent3.graph import build_risk_assessment_agent
        return build_risk_assessment_agent()
    except Exception as e:
        log.error(f"[orchestrator] Failed to load Agent 3: {e}")
        return None
# ──────────────────────────────────────────────────────────────────────────────
# NODE 1 — validate_expedition_request
# ──────────────────────────────────────────────────────────────────────────────

def validate_expedition_request_node(state: OrchestratorState) -> OrchestratorState:
    """Validate input waypoints and initialise orchestrator state."""
    waypoints = state.get("waypoints", [])
    errors    = []

    if len(waypoints) < 2:
        errors.append("At least 2 waypoints are required for expedition planning.")
        msg = HumanMessage(content=f"[validate] ❌ Validation failed: {errors}")
        return {**state, "status": "error", "errors": errors, "messages": [msg]}

    for i, wp in enumerate(waypoints):
        lat = wp.get("lat", 0)
        lon = wp.get("lon", 0)
        if not (-90  <= lat <= 90):
            errors.append(f"Waypoint {i} '{wp.get('name')}': latitude {lat} out of range")
        if not (-180 <= lon <= 180):
            errors.append(f"Waypoint {i} '{wp.get('name')}': longitude {lon} out of range")

    if errors:
        msg = HumanMessage(content=f"[validate] ❌ Validation failed: {errors}")
        return {**state, "status": "error", "errors": errors, "messages": [msg]}

    msg = HumanMessage(
        content=(
            f"[validate] ✅ {len(waypoints)} waypoints validated. "
            f"Expedition: {waypoints[0].get('name')} → {waypoints[-1].get('name')}"
        )
    )
    return {
        **state,
        "status":          "running_a1",
        "errors":          [],
        "agent1_status":   "pending",
        "agent3_status":   "pending",
        "messages":        [msg],
    }


# ──────────────────────────────────────────────────────────────────────────────
# NODE 2 — run_route_intelligence
# ──────────────────────────────────────────────────────────────────────────────

def run_route_intelligence_node(state: OrchestratorState) -> OrchestratorState:
    """
    Invoke Agent 1 (Route Intelligence) as a direct subgraph call.
    Translates orchestrator state → agent1 state → back to orchestrator state.
    """
    log.info("[orchestrator] Running Agent 1 — Route Intelligence")

    # Resolve vessel profile — lazy import avoids hard dependency at module load
    try:
        from naviguide_agent1.router import BerryMappemondeRouter as _Router
        _vessel_profile = _Router.VESSEL_PROFILE
    except Exception:
        _vessel_profile = {"avg_speed_knots": 10.0, "coastal_buffer_nm": 2}

    initial_a1 = {
        "waypoints":            state["waypoints"],
        "vessel_specs":         state.get("vessel_specs") or _vessel_profile,
        "constraints":          state.get("constraints", {}),
        "raw_segments":         [],
        "anti_shipping_scores": [],
        "safety_validations":   [],
        "route_plan":           {},
        "messages":             [],
        "errors":               [],
        "status":               "init",
        "chat_id":              None,
        "access_token":         None,
        "route_advisor_notes":  "",
    }

    try:
        result = _get_agent1().invoke(initial_a1)
        scores = result.get("anti_shipping_scores", [])
        avg    = round(sum(scores) / len(scores), 4) if scores else 0.0

        msg = AIMessage(
            content=(
                f"[agent1] ✅ Route computed: "
                f"{len(result.get('raw_segments', []))} segments | "
                f"anti-shipping avg={avg} | "
                f"status={result.get('status')}"
            )
        )
        log.info(f"[orchestrator] Agent 1 complete: status={result.get('status')}")
        return {
            **state,
            "agent1_status":  result.get("status", "complete"),
            "agent1_errors":  result.get("errors", []),
            "route_plan":     result.get("route_plan", {}),
            "anti_shipping_avg": avg,
            "status":         "running_a3",
            "messages":       [msg],
        }

    except Exception as exc:
        log.error(f"[orchestrator] Agent 1 failed: {exc}")
        msg = AIMessage(content=f"[agent1] ❌ Failed: {exc}")
        return {
            **state,
            "agent1_status": "failed",
            "agent1_errors": [str(exc)],
            "status":        "agent1_failed",
            "messages":      [msg],
        }


# ──────────────────────────────────────────────────────────────────────────────
# NODE 2b — agent1_fallback (injected when Agent 1 completely fails)
# ──────────────────────────────────────────────────────────────────────────────

# Official Berry-Mappemonde 18-waypoint reference (36 484 nm)
_BERRY_FALLBACK_WAYPOINTS = [
    {"name": "La Rochelle",                             "lat":  46.1591, "lon":  -1.1520, "mandatory": True},
    {"name": "Ajaccio (Corse)",                         "lat":  41.9192, "lon":   8.7386, "mandatory": True},
    {"name": "Îles Canaries",                           "lat":  28.5521, "lon": -16.1529, "mandatory": True},
    {"name": "Fort-de-France (Martinique)",             "lat":  14.6037, "lon": -61.0731, "mandatory": True},
    {"name": "Pointe-à-Pitre (Guadeloupe)",             "lat":  16.2415, "lon": -61.5331, "mandatory": True},
    {"name": "Gustavia (Saint-Barthélemy)",             "lat":  17.8962, "lon": -62.8498, "mandatory": True},
    {"name": "Marigot (Saint-Martin)",                  "lat":  18.0679, "lon": -63.0822, "mandatory": True},
    {"name": "Halifax (Nouvelle-Écosse)",               "lat":  44.6488, "lon": -63.5752, "mandatory": True},
    {"name": "Saint-Pierre (Saint-Pierre-et-Miquelon)", "lat":  46.7811, "lon": -56.1778, "mandatory": True},
    {"name": "Cayenne (Guyane française)",              "lat":   4.9333, "lon": -52.3333, "mandatory": True},
    {"name": "Papeete (Polynésie française)",           "lat": -17.5516, "lon":-149.5585, "mandatory": True},
    {"name": "Mata-Utu (Wallis-et-Futuna)",             "lat": -13.2825, "lon":-176.1736, "mandatory": True},
    {"name": "Nouméa (Nouvelle-Calédonie)",             "lat": -22.2758, "lon": 166.4572, "mandatory": True},
    {"name": "Dzaoudzi (Mayotte)",                      "lat": -12.7871, "lon":  45.2750, "mandatory": True},
    {"name": "Tromelin (TAAF)",                         "lat": -15.8900, "lon":  54.5200, "mandatory": True},
    {"name": "Saint-Gilles (La Réunion)",               "lat": -21.0594, "lon":  55.2242, "mandatory": True},
    {"name": "Europa (TAAF)",                           "lat": -22.3635, "lon":  40.3476, "mandatory": True},
    {"name": "La Rochelle (retour)",                    "lat":  46.1591, "lon":  -1.1520, "mandatory": True},
]


def agent1_fallback_node(state: OrchestratorState) -> OrchestratorState:
    """
    Fallback when Agent 1 completely fails.
    Injects the official Berry-Mappemonde 18-waypoint reference route (36 484 nm)
    so the pipeline can continue to Agent 3 and produce a valid briefing.
    No graph polylines are available; Agent 3 works from waypoint coordinates.
    """
    log.warning(
        "[orchestrator] Agent 1 unavailable — "
        "injecting Berry-Mappemonde reference route (36 484 nm). "
        "Continuing to risk assessment."
    )

    fallback_route_plan = {
        "type": "FeatureCollection",
        "metadata": {
            "total_distance_nm":       36484.0,
            "total_segments":          17,
            "anti_shipping_avg_score": 0.0,
            "source":                  "fallback",
            "note": (
                "Agent 1 unavailable — "
                "Berry-Mappemonde reference route injected."
            ),
        },
        "features": [],   # no detailed polylines; Agent 3 works from waypoints
    }

    # Preserve validated waypoints already in state; fall back to canonical 18-stop list
    waypoints = state.get("waypoints") or _BERRY_FALLBACK_WAYPOINTS

    msg = AIMessage(
        content=(
            "[agent1_fallback] ⚠️ Agent 1 unavailable — "
            "Berry-Mappemonde reference route injected (36 484 nm). "
            "Continuing to risk assessment."
        )
    )
    return {
        **state,
        "waypoints":         waypoints,
        "route_plan":        fallback_route_plan,
        "anti_shipping_avg": 0.0,
        "agent1_status":     "fallback",
        "agent1_errors":     state.get("agent1_errors", []),
        "status":            "running_a3",
        "messages":          [msg],
    }


# ──────────────────────────────────────────────────────────────────────────────
# NODE 3 — run_risk_assessment
# ──────────────────────────────────────────────────────────────────────────────

def run_risk_assessment_node(state: OrchestratorState) -> OrchestratorState:
    """
    Invoke Agent 3 (Risk Assessment) with waypoints + optional Agent 1 segments.
    """
    log.info("[orchestrator] Running Agent 3 — Risk Assessment")

    # Pass Agent 1 route segments as context to Agent 3
    route_plan     = state.get("route_plan", {})
    route_segments = route_plan.get("features", []) if route_plan else []

    initial_a3 = {
        "waypoints":            state["waypoints"],
        "route_segments":       route_segments,
        "weather_assessments":  [],
        "piracy_assessments":   [],
        "medical_assessments":  [],
        "cyclone_assessments":  [],
        "risk_scores":          [],
        "risk_report":          {},
        "messages":             [],
        "errors":               [],
        "status":               "init",
        "chat_id":              None,
        "access_token":         None,
        "llm_risk_summary":     "",
        "constraints":          state.get("constraints", {}),
    }

    try:
        result = _get_agent3().invoke(initial_a3)
        report = result.get("risk_report", {})
        level  = report.get("metadata", {}).get("expedition_risk_level", "UNKNOWN")

        msg = AIMessage(
            content=(
                f"[agent3] ✅ Risk assessed: "
                f"{len(result.get('risk_scores', []))} waypoints | "
                f"expedition risk={level} | "
                f"status={result.get('status')}"
            )
        )
        log.info(f"[orchestrator] Agent 3 complete: risk={level}")
        return {
            **state,
            "agent3_status":         result.get("status", "complete"),
            "agent3_errors":         result.get("errors", []),
            "risk_report":           report,
            "expedition_risk_level": level,
            "status":                "briefing",
            "messages":              [msg],
        }

    except Exception as exc:
        log.error(f"[orchestrator] Agent 3 failed: {exc}")
        msg = AIMessage(content=f"[agent3] ❌ Failed: {exc}")
        return {
            **state,
            "agent3_status":         "failed",
            "agent3_errors":         [str(exc)],
            "expedition_risk_level": "UNKNOWN",
            "status":                "briefing",   # continue to generate plan even if A3 fails
            "messages":              [msg],
        }


# ──────────────────────────────────────────────────────────────────────────────
# NODE 4 — llm_expedition_briefing
# ──────────────────────────────────────────────────────────────────────────────

def llm_expedition_briefing_node(state: OrchestratorState) -> OrchestratorState:
    """
    Generate unified executive skipper briefing combining Agent 1 + Agent 3 outputs.
    Language follows state["language"] ('fr' | 'en') — injected into both system
    prompt and user prompt so the briefing is always in the correct UI language.

    Data is drawn from the correct state paths:
      - total_nm       : state["route_plan"]["metadata"]["total_distance_nm"]
      - risk_level     : state["expedition_risk_level"]
      - critical_alerts: state["risk_report"]["critical_alerts"]
      - isolated_med   : state["risk_report"]["detail"]["medical_access"]
      - risk_matrix    : state["risk_report"]["risk_matrix"]
    """
    lang            = state.get("language", "fr")
    lang_en         = lang == "en"
    waypoints       = state.get("waypoints", [])

    # ── Extract route data from correct state paths ────────────────────────────
    route_plan  = state.get("route_plan", {})
    route_meta  = route_plan.get("metadata", {}) if isinstance(route_plan, dict) else {}
    total_nm    = route_meta.get("total_distance_nm") or 0.0

    # ── Extract risk data from risk_report (set by run_risk_assessment_node) ───
    risk_report     = state.get("risk_report", {})
    risk_metadata   = risk_report.get("metadata", {})
    critical_alerts = risk_report.get("critical_alerts", [])
    risk_matrix     = risk_report.get("risk_matrix", [])
    detail          = risk_report.get("detail", {})
    medical_list    = detail.get("medical_access", [])

    # risk_level from orchestrator state (set by run_risk_assessment_node)
    risk_level = state.get("expedition_risk_level") or risk_metadata.get("expedition_risk_level", "MODERATE")

    # Guard: if route produced 0 nm (agent failed), use expedition default
    if total_nm == 0:
        total_nm = 36484.0  # Berry-Mappemonde reference distance

    # ── Build concise risk summary for the prompt ──────────────────────────────
    sorted_matrix = sorted(risk_matrix, key=lambda x: x.get("overall", 0), reverse=True)

    alert_lines = "\n".join(
        f"  • {a['waypoint']} [{a['risk_level']}] — risque dominant: {a.get('dominant_risk', 'composite')}"
        for a in critical_alerts[:5]
    ) or ("  • No critical alerts detected." if lang_en else "  • Aucune alerte critique détectée.")

    isolated_med = [
        f"  • {m['name']}: {m.get('medevac_hours', '?')}h medevac"
        for m in medical_list if m.get("medevac_hours", 0) >= 48
    ]
    med_lines = "\n".join(isolated_med[:4]) or (
        "  • Medical access acceptable on full route." if lang_en
        else "  • Accès médical acceptable sur l'ensemble du tracé."
    )

    crit_count = risk_metadata.get("critical_stops_count", len([a for a in critical_alerts if a.get("risk_level") == "CRITICAL"]))
    high_count = risk_metadata.get("high_risk_stops_count", len([a for a in critical_alerts if a.get("risk_level") == "HIGH"]))

    # ── Build language-appropriate prompt ─────────────────────────────────────
    if lang_en:
        prompt = f"""BERRY-MAPPEMONDE EXPEDITION — FULL RISK PROFILE
═══════════════════════════════════════════════════════
Stops: {len(waypoints)} | Distance: {total_nm:,.0f} nm | Overall risk: {risk_level}
CRITICAL stops: {crit_count} | HIGH stops: {high_count}

CRITICAL/HIGH ALERTS:
{alert_lines}

CRITICAL MEDICAL ACCESS (medevac ≥48h):
{med_lines}

Write a skipper briefing with EXACTLY these 4 sections:
1. EXECUTIVE SUMMARY (2-3 sentences)
2. TOP CRITICAL RISKS (max 4 bullets, each with one concrete mitigation)
3. WEATHER WINDOWS BY BASIN (1 sentence per ocean basin)
4. NON-NEGOTIABLE SAFETY REQUIREMENTS (3 bullets)

Professional offshore tone, concise. Max 280 words. Write entirely in English."""
    else:
        prompt = f"""EXPÉDITION BERRY-MAPPEMONDE — PROFIL DE RISQUE COMPLET
═══════════════════════════════════════════════════════
Escales: {len(waypoints)} | Distance: {total_nm:,.0f} nm | Risque global: {risk_level}
Escales CRITICAL: {crit_count} | Escales HIGH: {high_count}

ALERTES CRITIQUES/HIGH:
{alert_lines}

ACCÈS MÉDICAL CRITIQUE (medevac ≥48h):
{med_lines}

Rédige un briefing skipper avec EXACTEMENT ces 4 sections:
1. RÉSUMÉ EXÉCUTIF (2-3 phrases)
2. TOP RISQUES CRITIQUES (max 4 puces, chacune avec une mitigation concrète)
3. FENÊTRES MÉTÉO PAR BASSIN (1 phrase par bassin océanique)
4. EXIGENCES NON NÉGOCIABLES (3 puces)

Ton professionnel hauturier, concis. Max 280 mots. Rédige entièrement en français."""

    briefing = _call_openrouter(prompt, max_tokens=800, language=lang)

    if not briefing:
        log.warning("[orchestrator] OpenRouter unavailable — using fallback briefing")
        briefing = _build_fallback_briefing(
            risk_level=risk_level,
            critical_alerts=critical_alerts,
            total_nm=total_nm,
            waypoint_count=len(waypoints),
            sorted_matrix=sorted_matrix,
            isolated_medical=isolated_med,
            language=lang,
        )

    msg = AIMessage(content=f"[llm_briefing] ✅ Briefing generated ({len(briefing)} chars, lang={lang})")
    return {
        **state,
        "executive_briefing": briefing,
        "status":             "generating_plan",
        "messages":           [msg],
    }
def _build_fallback_briefing(
    risk_level: str,
    critical_alerts: list,
    total_nm: float,
    waypoint_count: int,
    sorted_matrix: list = None,
    isolated_medical: list = None,
    language: str = "en",
) -> str:
    """Structured fallback when LLM is unavailable. Output in language."""
    sorted_matrix    = sorted_matrix    or []
    isolated_medical = isolated_medical or []
    lang_en          = language == "en"

    # Use critical_alerts; if empty, pull top-risk entries from matrix
    def _dominant(c):
        comp = c.get("components") or {}
        return max(comp, key=comp.get) if comp else "N/A"

    top_alerts = critical_alerts[:4] if critical_alerts else [
        {"waypoint": s["name"], "risk_level": s["level"], "dominant_risk": _dominant(s)}
        for s in sorted_matrix[:4] if s.get("level") in ("CRITICAL", "HIGH", "MODERATE")
    ]
    alerts_text = "\n".join(
        f"• {a['waypoint']} [{a['risk_level']}] — {a.get('dominant_risk', 'composite risk' if lang_en else 'risque composite')}"
        for a in top_alerts
    ) or ("• No critical alerts on the route." if lang_en else "• Aucune alerte critique sur le tracé.")

    medical_text = "\n".join(isolated_medical[:3]) or (
        "• Medical access acceptable on the full route." if lang_en
        else "• Accès médical acceptable sur l'ensemble du tracé."
    )

    if lang_en:
        return (
            f"BERRY-MAPPEMONDE EXPEDITION BRIEFING — FRENCH TERRITORIES WORLD TOUR\n\n"
            f"1. EXECUTIVE SUMMARY\n"
            f"The Berry-Mappemonde expedition covers {total_nm:,.0f} nautical miles across "
            f"{waypoint_count} stops in French overseas territories. "
            f"The assessed overall risk level is {risk_level}. "
            f"Thorough preparation and a schedule respecting seasonal weather windows "
            f"are imperative.\n\n"
            f"2. CRITICAL ALERTS\n"
            f"{alerts_text}\n\n"
            f"3. MEDICAL ISOLATION\n"
            f"{medical_text}\n\n"
            f"4. RECOMMENDED WEATHER WINDOWS\n"
            f"• North Atlantic (La Rochelle → Canaries): May–June (trade winds established)\n"
            f"• Tropical Atlantic (Canaries → Caribbean): November–January\n"
            f"• South Pacific (Cayenne → Papeete): April–June (outside cyclone season)\n"
            f"• South Indian Ocean (Nouméa → Réunion): May–September\n\n"
            f"5. NON-NEGOTIABLE SAFETY REQUIREMENTS\n"
            f"• Certified 406 MHz EPIRB beacon + permanent active Class B AIS\n"
            f"• Complete offshore medical kit + sea first aid training\n"
            f"• Avoid cyclone zones during active season (see alerts above)\n\n"
            f"Fair winds, Captain. NAVIGUIDE monitors your expedition."
        )
    else:
        return (
            f"BRIEFING EXPÉDITION BERRY-MAPPEMONDE — TOUR DU MONDE DES TERRITOIRES FRANÇAIS\n\n"
            f"1. RÉSUMÉ EXÉCUTIF\n"
            f"L'expédition Berry-Mappemonde couvre {total_nm:,.0f} milles nautiques à travers "
            f"{waypoint_count} escales dans les territoires français d'outre-mer. "
            f"Le niveau de risque global évalué est {risk_level}. "
            f"Une préparation approfondie et un calendrier respectant les fenêtres météo "
            f"saisonnières sont impératifs.\n\n"
            f"2. ALERTES CRITIQUES\n"
            f"{alerts_text}\n\n"
            f"3. ISOLEMENT MÉDICAL\n"
            f"{medical_text}\n\n"
            f"4. FENÊTRES MÉTÉO RECOMMANDÉES\n"
            f"• Atlantique N (La Rochelle → Canaries) : mai–juin (alizés établis)\n"
            f"• Atlantique tropical (Canaries → Caraïbes) : novembre–janvier\n"
            f"• Pacifique S (Cayenne → Papeete) : avril–juin (hors cyclone)\n"
            f"• Océan Indien S (Nouméa → Réunion) : mai–septembre\n\n"
            f"5. EXIGENCES DE SÉCURITÉ NON NÉGOCIABLES\n"
            f"• Balise EPIRB 406 MHz homologuée + AIS classe B actif permanent\n"
            f"• Trousse médicale hauturière complète + formation premiers secours en mer\n"
            f"• Éviter les zones cycloniques en saison active (voir alertes ci-dessus)\n\n"
            f"Bonne route, Commandant. NAVIGUIDE surveille votre expédition."
        )


# ──────────────────────────────────────────────────────────────────────────────
# NODE 5 — generate_expedition_plan
# ──────────────────────────────────────────────────────────────────────────────

def generate_expedition_plan_node(state: OrchestratorState) -> OrchestratorState:
    """
    Merge Agent 1 + Agent 3 outputs into the unified expedition digital twin.
    """
    route_plan      = state.get("route_plan", {})
    risk_report     = state.get("risk_report", {})
    risk_metadata   = risk_report.get("metadata", {})
    critical_alerts = risk_report.get("critical_alerts", [])
    waypoints       = state.get("waypoints", [])

    # Compute voyage statistics
    route_meta   = route_plan.get("metadata", {}) if isinstance(route_plan, dict) else {}
    total_nm     = route_meta.get("total_distance_nm", 0)
    # Guard: never 0 or None — always ≥ Berry-Mappemonde reference distance
    total_nm     = total_nm or 36484.0
    total_segs   = route_meta.get("total_segments", max(0, len(waypoints) - 1))
    anti_avg     = state.get("anti_shipping_avg", route_meta.get("anti_shipping_avg_score", 0))
    risk_level   = state.get("expedition_risk_level", "UNKNOWN")
    overall_risk = risk_metadata.get("overall_expedition_risk", 0.0)
    high_count   = risk_metadata.get("high_risk_stops_count", 0)
    crit_count   = risk_metadata.get("critical_stops_count", 0)

    # ── Build unified GeoJSON — Route features + Risk overlays ────────────────
    route_features = []
    if isinstance(route_plan, dict) and "features" in route_plan:
        route_features = route_plan["features"]

    # Add risk marker points for CRITICAL and HIGH waypoints
    risk_features = []
    for alert in critical_alerts:
        # Find the waypoint coordinates
        wp_coords = next(
            ({"lat": wp["lat"], "lon": wp["lon"]}
             for wp in waypoints
             if alert["waypoint"].lower() in wp.get("name", "").lower()
             or wp.get("name", "").lower() in alert["waypoint"].lower()),
            None
        )
        if wp_coords:
            risk_features.append({
                "type": "Feature",
                "geometry": {
                    "type":        "Point",
                    "coordinates": [wp_coords["lon"], wp_coords["lat"]],
                },
                "properties": {
                    "type":           "risk_alert",
                    "waypoint":       alert["waypoint"],
                    "risk_level":     alert["risk_level"],
                    "dominant_risk":  alert.get("dominant_risk", ""),
                    "score":          alert.get("score", 0.0),
                    "agent":          "Agent3-RiskAssessment",
                },
            })

    unified_geojson = {
        "type": "FeatureCollection",
        "metadata": {
            "expedition_name":         "Berry-Mappemonde",
            "source":                  "NAVIGUIDE Multi-Agent Orchestrator",
            "framework":               "LangGraph",
            "generated_at":            datetime.utcnow().isoformat() + "Z",
            "total_distance_nm":       total_nm,
            "expedition_risk_level":   risk_level,
            "overall_expedition_risk": overall_risk,
        },
        "features": route_features + risk_features,
    }

    # ── Format critical_alerts for the Sidebar ────────────────────────────────
    sidebar_alerts = []
    for alert in critical_alerts:
        components = {}
        # Try to get component scores from risk_matrix
        for scored_wp in risk_report.get("risk_matrix", []):
            if (scored_wp.get("name", "").lower() in alert["waypoint"].lower() or
                    alert["waypoint"].lower() in scored_wp.get("name", "").lower()):
                components = scored_wp.get("components", {})
                break
        sidebar_alerts.append({
            "waypoint":      alert["waypoint"],
            "risk_level":    alert["risk_level"],
            "dominant_risk": alert.get("dominant_risk", ""),
            "scores": {
                "weather_score": components.get("weather_score", 0.0),
                "cyclone_score": components.get("cyclone_score", 0.0),
                "piracy_score":  components.get("piracy_score",  0.0),
                "medical_score": components.get("medical_score", 0.0),
            },
        })

    expedition_plan = {
        # ── Top-level fields expected by the frontend ──────────────────────────
        "executive_briefing": state.get("executive_briefing", ""),
        "total_nm":           total_nm,           # always a float, never None/0 after briefing node
        "risk_level":         risk_level,          # always a string (CRITICAL/HIGH/MODERATE/LOW)
        "waypoints":          waypoints,           # full list for map rendering
        # ── Nested statistics ──────────────────────────────────────────────────
        "voyage_statistics": {
            "total_distance_nm":       total_nm,
            "total_segments":          total_segs,
            "expedition_risk_level":   risk_level,
            "overall_expedition_risk": overall_risk,
            "anti_shipping_avg":       anti_avg,
            "high_risk_count":         high_count,
            "critical_count":          crit_count,
        },
        "critical_alerts": sidebar_alerts,
        "unified_geojson":  unified_geojson,
        "full_route_intelligence": {
            "status":   state.get("agent1_status", "unknown"),
            "metadata": route_meta,
        },
        "full_risk_assessment": {
            "status":   state.get("agent3_status", "unknown"),
            "metadata": risk_metadata,
        },
    }

    msg = AIMessage(
        content=(
            f"[generate_plan] ✅ Expedition plan complete — "
            f"{total_nm:,.0f} nm | risk={risk_level} | "
            f"{len(sidebar_alerts)} alerts | "
            f"{len(unified_geojson['features'])} GeoJSON features"
        )
    )
    log.info(f"[orchestrator] Expedition plan generated: {total_nm} nm, risk={risk_level}")

    return {
        **state,
        "expedition_plan": expedition_plan,
        "status":          "complete",
        "messages":        [msg],
    }
