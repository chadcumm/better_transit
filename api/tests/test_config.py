from better_transit.config import Settings


def test_settings_defaults():
    settings = Settings()
    assert "better_transit" in settings.database_url
    assert "google_transit.zip" in settings.gtfs_static_url


def test_settings_from_env(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "postgresql+asyncpg://test:test@localhost/test")
    monkeypatch.setenv("GTFS_STATIC_URL", "http://example.com/feed.zip")
    settings = Settings()
    assert settings.database_url == "postgresql+asyncpg://test:test@localhost/test"
    assert settings.gtfs_static_url == "http://example.com/feed.zip"
