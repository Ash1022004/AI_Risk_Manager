from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    groq_api_key: str = ""
    groq_model: str = "openai/gpt-oss-20b"

    supabase_url: str = ""
    supabase_key: str = ""
    supabase_secret_key: str = ""

    redis_host: str = ""
    redis_port: int = 6379
    redis_username: str = "default"
    redis_password: str = ""
    redis_ssl: bool = False
    redis_queue_key: str = "risk:review_queue"

    kaggle_api_token: str = ""

    cors_origins: str = "http://localhost:3000,http://127.0.0.1:3000"

    @property
    def supabase_server_key(self) -> str:
        return self.supabase_secret_key or self.supabase_key

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]

    def missing(self) -> list[str]:
        required = {
            "GROQ_API_KEY": self.groq_api_key,
            "SUPABASE_URL": self.supabase_url,
            "SUPABASE_SECRET_KEY": self.supabase_secret_key,
            "REDIS_HOST": self.redis_host,
            "REDIS_PASSWORD": self.redis_password,
        }
        return [name for name, value in required.items() if not value]


@lru_cache
def get_settings() -> Settings:
    return Settings()
