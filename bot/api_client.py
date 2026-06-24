import asyncio
import logging
import uuid
from typing import Optional

import httpx
from httpx import Timeout

from core.config import settings

logger = logging.getLogger(__name__)

IDEMPOTENT_METHODS = {"GET", "HEAD", "OPTIONS"}


class APIClient:
    def __init__(self):
        self._base = settings.API_BASE_URL.rstrip("/")
        self._token = settings.SERVICE_API_TOKEN
        self._timeout = Timeout(connect=5.0, read=30.0, write=10.0, pool=5.0)
        self._max_retries = 3

    def _headers(
        self,
        tenant_id: Optional[str] = None,
        telegram_id: Optional[int] = None,
    ) -> dict:
        headers = {
            "X-Service-Token": self._token,
            "Content-Type": "application/json",
        }
        if tenant_id:
            headers["X-Tenant-ID"] = tenant_id
        if telegram_id is not None:
            headers["X-Telegram-ID"] = str(telegram_id)
        return headers

    async def _request(
        self,
        method: str,
        path: str,
        tenant_id: Optional[str] = None,
        telegram_id: Optional[int] = None,
        json_data: Optional[dict] = None,
    ) -> dict:
        url = f"{self._base}{path}"
        headers = self._headers(tenant_id, telegram_id)

        last_exc: Exception | None = None
        for attempt in range(self._max_retries):
            try:
                async with httpx.AsyncClient(timeout=self._timeout) as client:
                    resp = await client.request(
                        method=method, url=url, headers=headers, json=json_data,
                    )
                    if resp.status_code < 400:
                        return resp.json() if resp.content else {}
                    if resp.status_code >= 500 and attempt < self._max_retries - 1:
                        wait = 2 ** attempt
                        logger.warning(f"API {resp.status_code} retry {attempt+1}/{self._max_retries}")
                        await asyncio.sleep(wait)
                        continue
                    logger.error(f"API error {resp.status_code}: {resp.text[:500]}")
                    raise httpx.HTTPStatusError(
                        f"{resp.status_code}", request=resp.request, response=resp,
                    )
            except (httpx.ConnectError, httpx.ReadError, httpx.RemoteProtocolError) as e:
                last_exc = e
                if attempt < self._max_retries - 1:
                    await asyncio.sleep(2 ** attempt)
                    continue
                raise
            except httpx.HTTPStatusError:
                raise
        if last_exc:
            raise last_exc
        raise RuntimeError("Max retries exceeded")

    # ── Actor ──
    async def get_or_create_actor(
        self, telegram_id: int, username: str | None = None,
        first_name: str | None = None, last_name: str | None = None,
    ) -> dict:
        return await self._request(
            "GET",
            f"/api/actor/{telegram_id}",
            json_data={
                "username": username, "first_name": first_name, "last_name": last_name,
            } if any([username, first_name, last_name]) else None,
        )

    # ── Companies ──
    async def create_company(self, name: str, tariff: str) -> dict:
        return await self._request(
            "POST", "/api/companies",
            json_data={"name": name, "tariff": tariff},
        )

    async def get_company(self, company_id: str) -> dict:
        return await self._request("GET", f"/api/companies/{company_id}")

    # ── License ──
    async def check_license(self, company_id: str) -> dict:
        return await self._request("GET", f"/api/license/check/{company_id}")

    # ── Billing ──
    async def create_payment(
        self, company_id: str, tariff: str, amount: float, return_url: str,
    ) -> dict:
        return await self._request(
            "POST", "/api/billing/pay",
            json_data={
                "company_id": company_id, "tariff": tariff,
                "amount": amount, "return_url": return_url,
            },
        )

    # ── Tickets ──
    async def create_ticket(
        self, tenant_id: str, telegram_id: int, title: str, text: str,
    ) -> dict:
        return await self._request(
            "POST", "/api/tickets", tenant_id, telegram_id,
            json_data={"title": title, "text": text},
        )

    async def list_my_tickets(self, telegram_id: int) -> list[dict]:
        return await self._request("GET", f"/api/tickets/my?telegram_id={telegram_id}")

    async def list_company_tickets(
        self, tenant_id: str, telegram_id: int,
    ) -> list[dict]:
        return await self._request("GET", "/api/tickets", tenant_id, telegram_id)

    async def reply_ticket(
        self, ticket_id: str, tenant_id: str, telegram_id: int, text: str,
    ) -> dict:
        return await self._request(
            "POST", f"/api/tickets/{ticket_id}/reply",
            tenant_id, telegram_id, json_data={"text": text},
        )

    # ── Analytics ──
    async def analytics_summary(
        self, tenant_id: str, telegram_id: int, days: int = 30,
    ) -> dict:
        return await self._request(
            "GET", f"/api/analytics/analytics/summary?period_days={days}",
            tenant_id, telegram_id,
        )

    # ── Admin ──
    async def admin_list_companies(self, limit: int = 50) -> dict:
        return await self._request("GET", f"/api/companies?limit={limit}")

    async def admin_get_company(self, company_id: str) -> dict:
        return await self._request("GET", f"/api/companies/{company_id}")

    async def admin_license_activate(self, company_id: str) -> dict:
        return await self._request("POST", f"/admin/companies/{company_id}/activate")

    async def admin_license_deactivate(self, company_id: str) -> dict:
        return await self._request("POST", f"/admin/companies/{company_id}/deactivate")

    async def admin_list_bots(self) -> list[dict]:
        return await self._request("GET", "/api/bots")

    async def company_bots(self, company_id: str) -> list[dict]:
        data = await self._request("GET", "/api/bots")
        if isinstance(data, list):
            return [item for item in data if str(item.get("company_id", "")) == company_id]
        return []

    async def admin_add_bot(self, company_id: str, bot_token: str) -> dict:
        return await self._request(
            "POST", "/api/bots",
            json_data={"company_id": company_id, "token": bot_token},
        )

    async def admin_stats(self) -> dict:
        return await self._request("GET", "/admin/companies")

    async def admin_list_users(self) -> list[dict]:
        return await self._request("GET", "/api/actor/users")

    async def admin_get_user(self, user_id: str) -> dict:
        return await self._request("GET", f"/api/actor/users/{user_id}")

    # ── Legal ──
    async def revoke_consent(self, telegram_id: int) -> dict:
        return await self._request("POST", "/api/legal/revoke-consent", telegram_id=telegram_id)

    async def request_account_deletion(self, telegram_id: int) -> dict:
        return await self._request("POST", "/api/legal/delete-account", telegram_id=telegram_id)

    # ── Onboarding ──
    async def get_consent_document(self) -> dict:
        return await self._request("GET", "/api/onboarding/consent")

    async def accept_consent(self, telegram_id: int) -> dict:
        return await self._request(
            "POST",
            "/api/onboarding/accept-consent",
            telegram_id=telegram_id,
            json_data={"telegram_id": telegram_id},
        )


api = APIClient()
