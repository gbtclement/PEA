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

    # Comptes : ADMIN_EMAIL désigne le compte administrateur (reprend les données de « Moi »)
    admin_email: str = ""
    cookie_secure: bool = True  # false seulement en local sans HTTPS
    session_days: int = 30
    session_short_hours: int = 12

    # Envoi des mails (SMTP) ; SMTP_HOST vide = les mails restent en file d'attente
    smtp_host: str = ""
    smtp_port: int = 587
    smtp_user: str = ""
    smtp_password: str = ""
    smtp_tls: str = "starttls"  # starttls | ssl | none
    mail_from: str = "PEA Radar <no-reply@localhost>"

    # Connexion Google (OpenID Connect) ; vide = bouton masqué
    google_client_id: str = ""
    google_client_secret: str = ""
    # Cloudflare Turnstile ; clé secrète vide = captcha désactivé (local, tests)
    turnstile_site_key: str = ""
    turnstile_secret_key: str = ""
    # Refus des mots de passe connus dans les fuites (Have I Been Pwned, k-anonymat)
    hibp_enabled: bool = True
    # Origines acceptées en plus de PUBLIC_BASE_URL (serveur Vite de développement), séparées par des virgules
    dev_origins: str = "http://localhost:5180"


@lru_cache
def get_settings() -> Settings:
    return Settings()
