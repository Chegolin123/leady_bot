import time
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from prometheus_client import generate_latest, CONTENT_TYPE_LATEST

from api.middleware.service_auth import ServiceAuthMiddleware
from api.middleware.tenant import TenantMiddleware
from api.routers import companies, deals, clients, bots
from api.routers import billing, auth, activate, export, analytics, tasks
from api.routers.license_router import router as license_router_module
from api.routers import actor, tickets as tickets_router, legal as legal_router
from api.routers.onboarding import router as onboarding_module
from api.admin import router as admin_router
from core.config import settings
from core.logging_config import setup_logging


@asynccontextmanager
async def lifespan(app: FastAPI):
    setup_logging()
    yield


app = FastAPI(
    title="SaaS Telegram CRM",
    version="1.0.0",
    lifespan=lifespan,
)

# ── CORS (для админки) ──
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Внутренние middleware ──
app.add_middleware(ServiceAuthMiddleware)
app.add_middleware(TenantMiddleware)



# ── Health ──
@app.get("/health")
async def health():
    return {"status": "ok", "timestamp": time.time()}


# ── Metrics (Prometheus) ──
@app.get("/metrics")
async def metrics():
    return JSONResponse(
        content=generate_latest().decode("utf-8"),
        media_type=CONTENT_TYPE_LATEST,
    )


# ── Роутеры ──
app.include_router(companies.router, prefix="/api/companies", tags=["Companies"])
app.include_router(deals.router, prefix="/api/deals", tags=["Deals"])
app.include_router(clients.router, prefix="/api/clients", tags=["Clients"])
app.include_router(bots.router, prefix="/api/bots", tags=["Bots"])
app.include_router(billing.router, prefix="/api/billing", tags=["Billing"])
app.include_router(license_router_module, prefix="/api/license", tags=["License"])
app.include_router(auth.router, prefix="/api/auth", tags=["Auth"])
app.include_router(export.router, prefix="/api/export", tags=["Export"])
app.include_router(analytics.router, prefix="/api/analytics", tags=["Analytics"])
app.include_router(tasks.router, prefix="/api/tasks", tags=["Tasks"])
app.include_router(admin_router, prefix="/admin", tags=["Admin"])

app.include_router(actor.router, tags=["Actor"])
app.include_router(tickets_router.router, tags=["Tickets"])
app.include_router(legal_router.router, tags=["Legal"])
app.include_router(onboarding_module, tags=["Onboarding"])

# ── Активация бота (публичный эндпоинт) ──
app.include_router(activate.router, tags=["Activate"])
