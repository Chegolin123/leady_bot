from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    BOT_TOKEN: str = ""
    API_BASE_URL: str = "http://localhost:8000"
    SERVICE_API_TOKEN: str = ""
    REDIS_URL: str = "redis://localhost:6379"
    DATABASE_URL: str = ""
    AES_ENCRYPTION_KEY: str = ""
    YOOKASSA_SHOP_ID: str = ""
    YOOKASSA_SECRET: str = ""
    PROXY_LIST: str = ""
    HEARTBEAT_INTERVAL_SEC: int = 900
    LICENSE_CACHE_TTL: int = 900
    ADMIN_TELEGRAM_IDS: str = ""
    USER_CACHE_TTL: int = 300
    METRICS_PORT: int = 9091

    @property
    def admin_ids(self) -> set[int]:
        if not self.ADMIN_TELEGRAM_IDS:
            return set()
        return {int(x.strip()) for x in self.ADMIN_TELEGRAM_IDS.split(",") if x.strip()}

    @property
    def proxy_urls(self) -> list[str]:
        if not self.PROXY_LIST:
            return []
        return [u.strip() for u in self.PROXY_LIST.split(",") if u.strip()]

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}


settings = Settings()
