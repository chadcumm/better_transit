from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    database_url: str = (
        "postgresql+asyncpg://better_transit:dev@localhost:5432/better_transit"
    )
    gtfs_static_url: str = "http://www.kc-metro.com/gtf/google_transit.zip"

    model_config = {"env_file": ".env", "extra": "ignore"}


settings = Settings()
