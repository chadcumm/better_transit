from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    database_url: str = (
        "postgresql+asyncpg://better_transit:dev@localhost:5432/better_transit"
    )
    gtfs_static_url: str = "https://www.kc-metro.com/gtf/google_transit.zip"

    # GTFS-RT via Swiftly
    gtfs_rt_api_key: str = ""
    gtfs_rt_trip_updates_url: str = (
        "https://api.goswift.ly/real-time/kcata/gtfs-rt-trip-updates"
    )
    gtfs_rt_vehicle_positions_url: str = (
        "https://api.goswift.ly/real-time/kcata/gtfs-rt-vehicle-positions"
    )
    gtfs_rt_service_alerts_url: str = (
        "https://api.goswift.ly/real-time/kcata/gtfs-rt-service-alerts"
    )

    model_config = {"env_file": ".env", "extra": "ignore"}


settings = Settings()
