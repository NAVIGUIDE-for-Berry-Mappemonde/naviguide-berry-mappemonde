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
https://openrouter-nav.preview.emergentagent.com

## Changelog

### 2026-02 (session actuelle) — mise à jour
- **Investigation Copernicus (Item 1)** : 9 curls (wind/wave/current × 3 positions océaniques) → **100% de données réelles CMEMS**, 0% de fallback simulation. Latence 5.6-6.1s par appel. Champ `simulation` absent, `source` absent (= vraie donnée). Logs backend confirment `✅ Données récupérées avec succès`. Aucun fix requis.
- **Popup Ports (Item 2)** : ajout du layer `ports-circle` dans `interactiveLayerIds`, création de `src/components/PortsPopup.jsx` (minimal : port name + country via `MapPopup`, accent color `#f59e0b`). Handler branché dans `App.jsx` onClick. Validé headless : `Port Saint Louis Du Rhone / France` sans crash.
- **Sidebar élargie 320→360 px (Item 3)** : bouton toggle repositionné (`left-[362px]`), labels layers restaurés en versions complètes (`Buoyage`, `MPAs`) — les 5 pastilles tiennent en 1 ligne sans troncature.
- **Warm-up orchestrator + cache (Item 4)** :
  - `naviguide_workspace/naviguide_orchestrator/main.py` : `@app.on_event("startup")` lance un plan Berry-Mappemonde en background (asyncio task, sleep 8s, `asyncio.to_thread(orchestrator.invoke)`) + peuple un cache TTL 1h (in-memory).
  - Endpoint `plan_berry_mappemonde` consulte le cache en premier — cache hit sur `(language, expedition_id, departure_month)` répond en <500ms.
  - Env vars : `WARMUP_ORCHESTRATOR=1` (default, ajouté dans `naviguide-api/.env`), `BERRY_PLAN_CACHE_TTL_S=3600` (default).
  - **Latences mesurées** après restart :
    - Warm-up complet en 34.2s en background (n'a pas bloqué le startup).
    - Cache hit `fr` : **0.33s** puis **0.16s** (vs 60-90s cold-start avant).
    - Cache miss (`en`, jamais vu) : **19.75s** (vs 60-90s cold, gain grâce aux Copernicus/OpenRouter déjà chauds).
  - Ratio : **200× plus rapide** en cache hit.
- **P0 CRITIQUE — Cause racine des crashs popup identifiée**
  - Fichier : `src/components/ui/MapPopup.jsx` — ligne `anchor="auto"` sur `<Popup>` de `react-map-gl/maplibre`.
  - `"auto"` n'est pas dans `PopupOptions.anchor` de MapLibre GL v5 (valeurs légales : `center | top | bottom | left | right | top-left | top-right | bottom-left | bottom-right`). Le doc dit : *"If unset the anchor will be dynamically set"* — il faut **omettre** la prop, pas passer `"auto"`.
  - Impact runtime : dans MapLibre `Popup._update`, `let o = this.options.anchor` = `"auto"` (truthy) → le bloc `if (!o) { compute auto }` est skippé → `let r = i.add(a["auto"])` = `i.add(undefined)` → **TypeError: Cannot read properties of undefined (reading 'x')** dans `Point.prototype._add`.
  - Fix : 1 ligne retirée (`anchor="auto"` supprimé de MapPopup.jsx).
  - Régression introduite lors du refactor "unification popups" — la valeur `"auto"` a été copiée d'une doc obsolète ou d'un mauvais exemple. Tous les popups (Satellite, MPA, Blue Projects, Draw waypoint) qui utilisaient MapPopup héritaient du bug.
  - Validation Playwright : Blue Projects popup ("La Tribu Maritime") ✅, MPA popup ("Tunisia EEZ, LFP 1 — Minimal") ✅, Satellite/Point popup via Draw route ✅, tous avec `boundary=0`.
- **P0** `ErrorBoundary` global (`src/components/ErrorBoundary.jsx`) : deux modes (dev = stack complet, prod = message minimal + bouton reload). Support `?debug=1` pour forcer le mode diagnostic complet en prod build (utile pour triage sans redéployer un dev build). Wrapper posé dans `main.jsx` — empêche les crashs de popups MapLibre de blanchir toute l'app.
- **P0** Polar chat : bulles utilisateur restent visibles après envoi. Cause : `scrollIntoView()` remontait le conteneur parent (sidebar globale). Fix : `block: "nearest"` + hauteur mini 96 px sur le panneau messages.
- **P1** Suppression du toggle **Light Mode** (jamais réellement implémenté — seulement un `filter: invert(1)` sur la sidebar). Retiré de `App.jsx`, `ExportSidebar.jsx`, `index.css`.
- **P1** Suppression du bloc **Getting Started** dans `Sidebar.jsx` + clés i18n associées supprimées.
- **P1** `MaritimeLayersPanel` : grille 3×2 → **grille 1×5 compacte** (`grid-cols-5`). Défauts tous **OFF** (ZEE, Ports, Buoys, MPA, Projects). Labels raccourcis (`Ports WPI`→`Ports`, `Balisage`→`Balise`/`Buoys`, `MPAs`→`MPA`) pour éviter les ellipses.
- **P1** LFP popover repositionné en `top-full right-0` (avant : `top-0 left-full` — sortait de l'écran dans la sidebar 320 px).
- Debug hook conservé : `window.__naviguide_map` est exposé si `?debug=1` (permet aux tests headless de piloter la carte via `map.jumpTo`/`map.queryRenderedFeatures`/`map.fire`).
- Sécurité : retiré une **tentative d'injection de prompt** (`<system-reminder>` malicieux) qui s'était retrouvée en fin de `src/index.css`.
- `data-testid` ajoutés sur : layers-panel, chaque layer toggle, chat panel/input/messages/send button, ErrorBoundary panels, LFP popover, blue-projects-popup.

### Points connus non résolus (design, pas bugs)
- **Ports (WPI) non cliquables** : le layer `ports-circle` n'est pas dans `interactiveLayerIds` de `<Map>` (`App.jsx:880`) et il n'y a jamais eu de handler `onClick` pour ouvrir un popup port. Ce n'est PAS un crash — juste absent par design. À implémenter en P2 si souhaité (ajouter le layer id + brancher un composant `PortsPopup`).

## Backlog (P2)
- Popups vagues/courants encore inline dans `App.jsx` — les migrer vers `MapPopup` pour cohérence.
- `useMaritimeLayers` : bouton "Reset" pour repasser tous les calques OFF en un clic (nice-to-have).
- Warning pré-existant `no-empty` sur `App.jsx:37` (catch vide sur localStorage cleanup) — cosmétique.
- Warning pré-existant `Unused eslint-disable` `ExportSidebar.jsx:316` — cosmétique.
- Chunk JS unique 1.43 MB → envisager `manualChunks` (MapLibre + PMTiles séparés).
