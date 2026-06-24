from dataclasses import dataclass, field
from typing import Optional


@dataclass
class ActorDTO:
    actor_id: str
    telegram_id: int
    username: str | None = None
    first_name: str | None = None
    last_name: str | None = None
    is_admin: bool = False
    pd_consent: bool = False
    role: str = "guest"
    company_id: str | None = None
    company_name: str = ""
    tariff: str = "base"
    bot_username: str = ""

    @property
    def active_membership(self):
        if not self.company_id:
            return None
        from bot.dto import MembershipDTO
        return MembershipDTO(
            company_id=self.company_id,
            company_name=self.company_name,
            role=self.role,
            tariff=self.tariff,
        )


@dataclass
class MembershipDTO:
    company_id: str
    company_name: str
    role: str
    tariff: str


@dataclass
class SubscriptionDTO:
    tariff: str
    active: bool
    expires_at: str
    auto_renew: bool
