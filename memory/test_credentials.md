# NAVIGUIDE — Test credentials

**Pas d'authentification — endpoints publics. Pas de user à seed.**

- Preview URL : https://7c600998-da71-4e9e-b004-d4f0dfcbd51f.preview.emergentagent.com
- API base : https://7c600998-da71-4e9e-b004-d4f0dfcbd51f.preview.emergentagent.com/api
- OpenAPI : https://7c600998-da71-4e9e-b004-d4f0dfcbd51f.preview.emergentagent.com/api/openapi.json

Endpoints principaux (tous publics, pas de header d'auth) :
- `GET  /api/backend/health`          — health du wrapper
- `GET  /api/route?start_lat=..&start_lon=..&end_lat=..&end_lon=..` — route maritime searoute
- `POST /api/wind|/wave|/current`     — données Copernicus, body `{"latitude": .., "longitude": ..}`
- `POST /api/orchestrator/api/v1/expedition/plan/berry-mappemonde` — briefing IA (langue FR/EN)
- `POST /api/polar/api/v1/polar/upload`    — upload polaire CSV/PDF/XLSX (multipart)
- `POST /api/polar/api/v1/polar/chat`      — chat VMG polaire

Aucune vérification CSRF, cookie, JWT ou Basic-auth n'est en place. CORS `*` sur tous les endpoints.
