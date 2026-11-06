"""
config.py — config.

All environment variables in one place.
pydantic-settings reads from env vars and an optional .env file.
"""
from pydantic import SecretStr
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    job_name: str = "__APP_NAME__"

    # Injected by Kubernetes via sealed secret — SecretStr prevents accidental logging
    database_url: SecretStr = SecretStr("")
    litellm_api_key: SecretStr = SecretStr("")
    litellm_base_url: str = "http://litellm.ai.svc.cluster.local:4000"
    litellm_model: str = "smart"

    class Config:
        env_file = ".env"


settings = Settings()
