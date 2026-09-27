from typing import Literal

from app.core.config import get_settings
from app.models import UserSettings
from app.services.secrets import decrypt_secret

KeySource = Literal["settings", "env"]


def resolve_api_key(settings_row: UserSettings) -> tuple[str | None, KeySource | None]:
    """Clé saisie dans les Réglages en priorité, sinon ANTHROPIC_API_KEY."""
    config = get_settings()
    if settings_row.anthropic_key_enc:
        key = decrypt_secret(settings_row.anthropic_key_enc, config.app_secret)
        if key:
            return key, "settings"
    if config.anthropic_api_key:
        return config.anthropic_api_key, "env"
    return None, None
