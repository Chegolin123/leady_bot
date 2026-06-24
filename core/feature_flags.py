from functools import wraps
from typing import Callable

TARIFF_FEATURES = {
    "base": {
        "deals": True,
        "clients": True,
        "export_pd": True,
        "max_managers": 1,
        "max_leads_per_month": 30,
        "price": 999,
        "trial_days": 7,
    },
    "pro": {
        "deals": True,
        "clients": True,
        "export_pd": True,
        "custom_statuses": True,
        "yookassa": True,
        "analytics": True,
        "tasks": True,
        "max_managers": 10,
        "price": 2999,
        "discount_first_month": 20,
    },
}


def require_feature(feature: str) -> Callable:
    """
    Декоратор для проверки доступности фичи по тарифу.
    Используется как FastAPI Dependency.
    """

    def decorator(func: Callable) -> Callable:
        @wraps(func)
        async def wrapper(*args, **kwargs):
            tariff: str = kwargs.get("tariff", "base")
            available = TARIFF_FEATURES.get(tariff, {})
            if not available.get(feature):
                from fastapi import HTTPException

                raise HTTPException(
                    status_code=403,
                    detail=f"Feature '{feature}' is not available on tariff '{tariff}'",
                )
            return await func(*args, **kwargs)

        return wrapper

    return decorator


def get_tariff_features(tariff: str) -> dict:
    return TARIFF_FEATURES.get(tariff, {})
