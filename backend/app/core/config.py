from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = "postgresql+psycopg://pea:pea@db:5432/pea_radar"
    test_database_url: str = "postgresql+psycopg://pea:pea@db:5432/pea_radar_test"
    timezone: str = "Europe/Paris"

    euronext_list_url: str = "https://live.euronext.com/en/pd_es/data/stocks/download?mics=dm_all_stock"
    yahoo_chunk_size: int = 50
    yahoo_pause_seconds: float = 1.0
    fundamentals_pause_seconds: float = 0.5
    history_years: int = 5

    tier2_size: int = 150
    quotes_t1_minutes: int = 2
    quotes_t2_minutes: int = 5
    quotes_t3_minutes: int = 30


@lru_cache
def get_settings() -> Settings:
    return Settings()
