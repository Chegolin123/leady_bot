"""Access policy for @LEADYCRM_bot.

Roles: guest, client, manager, admin.

- guest: onboarding only, no menu
- client: purchased, mini-menu
- manager: platform support (tickets, companies, stats)
- admin: everything
"""

from bot.dto import ActorDTO, MembershipDTO

ActionKey = str

TARIFF_RULES: dict[ActionKey, set[str]] = {
    "stats.view": {"pro"},
}

ROLE_RULES: dict[ActionKey, set[str]] = {
    "admin.companies.list": {"admin"},
    "admin.companies.view": {"admin"},
    "admin.license.update": {"admin"},
    "admin.bots.list": {"admin"},
    "admin.bots.manage": {"admin"},
    "admin.tickets.list": {"admin"},
    "admin.tickets.view": {"admin"},
    "admin.stats.view": {"admin"},
    "admin.users.list": {"admin"},
    "admin.users.view": {"admin"},
    "admin.payments.list": {"admin"},
    "admin.logs.view": {"admin"},
    "manager.tickets.list": {"manager", "admin"},
    "manager.tickets.reply": {"manager", "admin"},
    "manager.companies.list": {"manager", "admin"},
    "manager.stats.view": {"manager", "admin"},
    "client.subscription.view": {"client", "admin"},
    "legal.revoke_consent": {"guest", "client", "manager", "admin"},
    "legal.delete_account": {"guest", "client", "admin"},
}


def check_access(
    action: ActionKey,
    is_admin: bool,
    role: str,
    membership: MembershipDTO | None,
) -> bool:
    if is_admin:
        return True

    allowed_roles = ROLE_RULES.get(action)
    if allowed_roles is None:
        return False
    if role not in allowed_roles:
        return False

    allowed_tariffs = TARIFF_RULES.get(action)
    if allowed_tariffs and membership and membership.tariff not in allowed_tariffs:
        return False

    return True
