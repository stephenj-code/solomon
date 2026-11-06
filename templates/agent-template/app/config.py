from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    app_name: str = "__APP_NAME__"
    version: str = "0.1.0"
    debug: bool = False

    database_url: str = ""
    litellm_api_key: str = ""
    litellm_base_url: str = "http://litellm.ai.svc.cluster.local:4000"
    litellm_model: str = "smart"  # smart | fast | external — see LiteLLM aliases

    class Config:
        env_file = ".env"


settings = Settings()
