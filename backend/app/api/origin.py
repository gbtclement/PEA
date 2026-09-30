from urllib.parse import urlsplit

from fastapi import HTTPException, Request

from app.core.config import get_settings


def _origin(url: str) -> str:
    parts = urlsplit(url.strip())
    return f"{parts.scheme}://{parts.netloc}".lower()


def check_origin(request: Request) -> None:
    """Routes publiques de connexion et d'inscription : refuse un en-tête Origin étranger (spec 2.1).

    Un navigateur envoie toujours Origin sur un POST ; son absence (outil en ligne de commande, tests) est acceptée.
    """
    origin = request.headers.get("Origin")
    if origin is None:
        return
    settings = get_settings()
    allowed = {_origin(settings.public_base_url)} | {_origin(o) for o in settings.dev_origins.split(",") if o.strip()}
    if origin.lower().rstrip("/") not in allowed:
        raise HTTPException(403, detail={"code": "bad_origin", "message": "Requête refusée : rechargez la page."})
