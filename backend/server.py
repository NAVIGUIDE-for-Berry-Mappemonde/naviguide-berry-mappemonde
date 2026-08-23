"""
NAVIGUIDE — Backend Wrapper
============================
Serves as the FastAPI entrypoint for supervisor (backend program).

Architecture:
  - Parent app on port 8001 (external via Kubernetes ingress `/api/*`)
  - Sub-app `naviguide-api` mounted on `/api` (all its routes prefixed with /api)
  - Internal reverse-proxies:
      /api/orchestrator/{path}  →  http://127.0.0.1:3008/{path}
      /api/polar/{path}         →  http://127.0.0.1:8004/{path}

The mount() approach avoids invasive refactor of naviguide-api/main.py:
all existing `/route`, `/wind`, `/wave`, `/current`, `/proxy/*`, `/agents/*`,
`/simulation/*` become `/api/route`, `/api/wind`, etc. automatically.

Env vars are loaded from /app/naviguide-api/.env BEFORE importing main so
that copernicusmarine and OpenRouter clients pick up credentials at module
load time.
"""
import os
import sys
from pathlib import Path

# ── 1. Charge .env avant TOUT import ─────────────────────────────────────────
from dotenv import load_dotenv
NAVIGUIDE_API_DIR = Path("/app/naviguide-api")
load_dotenv(NAVIGUIDE_API_DIR / ".env")

# ── 2. sys.path pour trouver le module naviguide-api ─────────────────────────
sys.path.insert(0, str(NAVIGUIDE_API_DIR))

# ── 3. Import naviguide-api FastAPI app ──────────────────────────────────────
# main.py has `if __name__ == "__main__"` guard, safe to import.
from main import app as naviguide_api_app  # noqa: E402

# ── 4. Reverse-proxies (defined on the SUB-APP so `/orchestrator/*` and
#      `/polar/*` become `/api/orchestrator/*` and `/api/polar/*` through mount)
import httpx  # noqa: E402
from fastapi import Request  # noqa: E402
from fastapi.responses import Response, JSONResponse  # noqa: E402

ORCHESTRATOR_URL = "http://127.0.0.1:3008"
POLAR_API_URL    = "http://127.0.0.1:8004"

_HOP_BY_HOP = {
    "host", "content-length", "connection", "keep-alive",
    "proxy-authenticate", "proxy-authorization", "te", "trailer",
    "transfer-encoding", "upgrade",
}


async def _proxy(request: Request, base_url: str, path: str) -> Response:
    """Generic reverse-proxy handler with 120s timeout (LLM briefings can take 60-90s)."""
    url = f"{base_url}/{path}"
    headers = {
        k: v for k, v in request.headers.items()
        if k.lower() not in _HOP_BY_HOP
    }
    body = await request.body()
    params = dict(request.query_params)
    try:
        async with httpx.AsyncClient(timeout=120.0) as client:
            resp = await client.request(
                method=request.method,
                url=url,
                headers=headers,
                content=body,
                params=params,
            )
        return Response(
            content=resp.content,
            status_code=resp.status_code,
            media_type=resp.headers.get("content-type", "application/json"),
        )
    except httpx.ConnectError:
        return JSONResponse(
            {"error": "Backend service unavailable", "url": url},
            status_code=503,
        )
    except httpx.TimeoutException:
        return JSONResponse(
            {"error": "Backend service timeout", "url": url},
            status_code=504,
        )
    except Exception as exc:
        return JSONResponse({"error": str(exc), "url": url}, status_code=500)


# The catch-all paths accept empty segment: `/orchestrator/` and `/polar/`
# → we register two routes for each so `GET /api/orchestrator` (no trailing
# slash) hits `GET /` on the target and `GET /api/orchestrator/whatever`
# hits `GET /whatever`.

@naviguide_api_app.api_route(
    "/orchestrator",
    methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
)
async def proxy_orch_root(request: Request):
    return await _proxy(request, ORCHESTRATOR_URL, "")


@naviguide_api_app.api_route(
    "/orchestrator/{path:path}",
    methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
)
async def proxy_orch(request: Request, path: str):
    return await _proxy(request, ORCHESTRATOR_URL, path)


@naviguide_api_app.api_route(
    "/polar",
    methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
)
async def proxy_polar_root(request: Request):
    return await _proxy(request, POLAR_API_URL, "")


@naviguide_api_app.api_route(
    "/polar/{path:path}",
    methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
)
async def proxy_polar(request: Request, path: str):
    return await _proxy(request, POLAR_API_URL, path)


# ── 5. Parent app: mounts naviguide-api on /api ──────────────────────────────
from fastapi import FastAPI  # noqa: E402
from fastapi.middleware.cors import CORSMiddleware  # noqa: E402

app = FastAPI(
    title="NAVIGUIDE Backend",
    description=(
        "Entrypoint served on :8001 by supervisor. "
        "Mounts naviguide-api under /api and reverse-proxies orchestrator + "
        "polar_api under /api/orchestrator and /api/polar respectively."
    ),
    docs_url="/api/backend/docs",
    openapi_url="/api/backend/openapi.json",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/api/backend/health")
def health():
    """Liveness probe for the wrapper (does not touch sub-services)."""
    return {"status": "ok", "service": "naviguide-backend-wrapper", "port": 8001}


# ── Startup warmup — precharge searoute maritime graph + shapely trees ───────
# Avoids the 15-40s "cold start" on the first /api/route batch.
# Blocking: measured <5s total, safe for uvicorn startup.
@app.on_event("startup")
async def _warmup_searoute():
    import time as _time
    t = _time.monotonic()
    try:
        import searoute as _sr
        # Two calls: first primes the graph, second confirms it's warm.
        # Use maritime coords (La Rochelle vicinity → Bay of Biscay) so the
        # graph pages we care about are loaded.
        _sr.searoute([-1.5, 46.5], [-2.0, 47.0])
        _sr.searoute([-5.0, 45.0], [-6.0, 46.0])
        print(f"[startup] searoute graph warmed in {_time.monotonic()-t:.2f}s", flush=True)
    except Exception as exc:  # noqa: BLE001
        print(f"[startup] searoute warmup failed (non-fatal): {exc}", flush=True)


@app.on_event("startup")
async def _import_agents_module():
    """Force-import agents.deploy_ai so its log_startup_config runs at boot,
    otherwise the AGENTS cascade config would only appear on the first SSE call.
    """
    try:
        sys.path.insert(0, str(NAVIGUIDE_API_DIR))
        import agents.deploy_ai  # noqa: F401
        print("[startup] agents.deploy_ai eagerly loaded", flush=True)
    except Exception as exc:  # noqa: BLE001
        print(f"[startup] agents.deploy_ai import failed (non-fatal): {exc}", flush=True)


# Mount the naviguide-api FastAPI app on /api
# All its routes /route, /wind, /wave, /current, /proxy/*, /agents/*,
# /simulation/*, plus the two proxies defined above, become /api/*
app.mount("/api", naviguide_api_app)
