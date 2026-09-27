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
    quotes_t1_minutes: int = 1
    quotes_t2_minutes: int = 5
    quotes_t3_minutes: int = 5

    min_turnover_eur: float = 500_000
    top_size: int = 10
    min_history_days: int = 200
    min_available_ratio: float = 0.6

    app_secret: str = ""
    anthropic_api_key: str = ""
    assistant_model: str = "claude-opus-5"
    assistant_max_tokens: int = 16000
    assistant_max_rounds: int = 8

    public_base_url: str = "http://localhost:8095"
    seo_indexing: bool = False


@lru_cache
def get_settings() -> Settings:
    return Settings()
