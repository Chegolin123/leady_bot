import logging
from fastapi import Request
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

from core.config import settings

logger = logging.getLogger(__name__)

EXCLUDED_PATHS = {"/health", "/metrics", "/docs", "/openapi.json", "/admin"}


class ServiceAuthMiddleware(BaseHTTPMiddleware):
    """
    Проверяет X-Service-Token для внутренних запросов (бот → API).
    Пропускает публичные эндпоинты: /health, /metrics, /admin.
    """

    async def dispatch(self, request: Request, call_next):
        path = request.url.path

        if path in EXCLUDED_PATHS or path.startswith("/admin"):
            return await call_next(request)

        service_token = request.headers.get("X-Service-Token")
        if not service_token or service_token != settings.SERVICE_API_TOKEN:
            logger.warning(f"Unauthorized service request: {path}")
            return JSONResponse(status_code=403, content={"detail": "Forbidden: invalid service token"})

        return await call_next(request)
