import logging
from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware
from sqlalchemy import text

from core.database import async_session

logger = logging.getLogger(__name__)

EXCLUDED_PATHS = {"/health", "/metrics", "/docs", "/openapi.json", "/api/billing/webhook"}


class TenantMiddleware(BaseHTTPMiddleware):
    """
    Извлекает tenant_id из заголовка X-Tenant-ID и устанавливает
    PostgreSQL-переменную app.tenant_id для RLS.
    """

    async def dispatch(self, request: Request, call_next):
        path = request.url.path

        if path in EXCLUDED_PATHS or path.startswith("/admin"):
            return await call_next(request)

        tenant_id = request.headers.get("X-Tenant-ID")

        if tenant_id:
            async with async_session() as session:
                await session.execute(
                    text("SELECT set_config('app.tenant_id', :tenant, FALSE)"),
                    {"tenant": tenant_id},
                )
                await session.commit()

        request.state.tenant_id = tenant_id

        response = await call_next(request)
        return response
