# NAVIGUIDE — Berry-Mappemonde (PRD synthétique)

## Vue d'ensemble
NAVIGUIDE est une application web de préparation et suivi de l'expédition
**Berry-Mappemonde 2026-2027** : un tour du monde à la voile d'environ **36 484 nm** en catamaran,
touchant les 15+ territoires français d'outre-mer (Corse, Antilles, Guyane, SPM, Polynésie,
Wallis, Nouvelle-Calédonie, Mayotte, TAAF, La Réunion…) au départ et à l'arrivée à
**La Rochelle**. L'application combine un moteur de routage maritime (searoute + graphe
anti-shipping-lanes), un système multi-agent LangGraph (route intelligence + risk assessment +
briefing IA), une couche cartographique MapLibre riche (ZEE, ports WPI, balisage OpenSeaMap,
Aires Marines Protégées via ProtectedSeas PMTiles) et un moteur de polaires voiliers
(upload PDF/CSV/XLSX + interpolation 181×61 TWA×TWS + chat VMG).

L'utilisateur cible est un **skipper hauturier ou l'équipe préparation** de l'expédition :
il ouvre la carte, examine la route Berry-Mappemonde pré-configurée (18 escales
obligatoires), clique sur n'importe quel point pour obtenir vent/vagues/courants
Copernicus, dessine ou importe une route custom, active la vue Simulation pour faire
progresser un catamaran draggable, télécharge ses polaires pour raffiner les ETA,
et lit le briefing IA multilangue (FR/EN) généré à la volée par OpenRouter.

## Stack

- **Frontend** : React 19 + Vite 7 + MapLibre GL 5.11 (+ react-map-gl 8) + PMTiles 3.2 +
  Tailwind v4 + lucide-react. Build statique servi sur port 3000.
- **Backend** : FastAPI 0.115 (Python 3.11), plusieurs services :
  - `naviguide-api` (port **8001**, exposé via `/api/*`) — routage searoute, avoid-land
    Natural Earth 1:10m (dépendant de shapefiles à installer), Copernicus wind/wave/current,
    4 agents SSE (météo, piraterie, port/douanes, community).
  - `naviguide-orchestrator` (port **3008**, interne) — pipeline LangGraph
    validate → agent1 route → (fallback if fail) → agent3 risk → briefing OpenRouter → plan.
  - `polar_api` (port **8004**, interne) — upload polaire + chat VMG.
- **Reverse-proxy** : `naviguide-api` inclut deux catch-all `/orchestrator/{path}` et
  `/polar/{path}` (via `mount()` sur `/api`) qui forwardent en interne vers `127.0.0.1:3008`
  et `127.0.0.1:8004`.
- **LLM** : OpenRouter (modèles free — llama-3.1-8b, gemma-2-9b, qwen-2.5-72b, mistral-7b,
  nemotron, etc.) via clé `OPENROUTER_API_KEY`.
- **Data marine** : Copernicus Marine Service (satellite wind L4, wave analysis, physics
  currents) — nécessite compte gratuit CMEMS.
- **Cartes** : demotiles.maplibre.org (base), VLIZ WMS (ZEE), NGA/MSI WPI (ports),
  OpenSeaMap seamark tiles, ProtectedSeas S3 PMTiles (AMP).
- **Persistance** : aucun SGBD. Uploads polaires JSON sur disque
  (`naviguide_workspace/polar_data/`). Caches en mémoire 24h pour ZEE et WPI.
- **Auth** : aucune (endpoints publics).

## Endpoints principaux (base = `/api`)

Routage & données marines
- `GET  /api/route?start_lat&start_lon&end_lat&end_lon` — route maritime searoute
- `POST /api/wind`  `{ latitude, longitude }` — vent Copernicus (fallback simulation)
- `POST /api/wave`  — vagues
- `POST /api/current` — courant
- `GET  /api/proxy/zee` / `/api/proxy/zee/wms` — Zones Économiques Exclusives (VLIZ)
- `GET  /api/proxy/ports` — ports WPI (NGA)
- `GET  /api/proxy/seamark/{z}/{x}/{y}.png` — balisage OpenSeaMap

Agents SSE (streaming — 1 chunk final)
- `POST /api/agents/meteo`   — briefing météo par leg
- `POST /api/agents/pirate`  — retours community Noonsite
- `POST /api/agents/guard`   — piraterie IMB
- `POST /api/agents/custom`  — port & douanes

Orchestrator (proxifié)
- `POST /api/orchestrator/api/v1/expedition/plan/berry-mappemonde` — briefing complet FR/EN
- `POST /api/orchestrator/api/v1/expedition/plan`                  — briefing sur waypoints custom
- `GET  /api/orchestrator/api/v1/expedition/status`                — disponibilité agents

Polar (proxifié)
- `POST /api/polar/api/v1/polar/upload`                — upload PDF/CSV/XLSX (multipart)
- `GET  /api/polar/api/v1/polar/{expedition_id}`       — grille 181×61 complète
- `GET  /api/polar/api/v1/polar/{expedition_id}/summary` — VMG summary léger
- `POST /api/polar/api/v1/polar/chat`                  — chat VMG (Groq → OpenRouter fallback)

## Preview
https://7c600998-da71-4e9e-b004-d4f0dfcbd51f.preview.emergentagent.com
