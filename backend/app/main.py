from fastapi import FastAPI

from app.api.cache import ETagMiddleware
from app.core.brand import APP_NAME
from app.core.db import get_session_factory
from app.repositories.fx import store_loader
from app.services import fx

from app.api.routes import admin, assistant, auth, billing, favorites, google, fees, forecasts, health, me, notifications, orders, unsubscribe, portfolio, rankings, screener, securities, security_detail, seo, settings, status


def create_app() -> FastAPI:
    app = FastAPI(title=f"{APP_NAME} API")
    app.add_middleware(ETagMiddleware)  # réponses publiques : empreinte et 304
    for module in (health, auth, google, me, notifications, billing, unsubscribe, admin, securities, security_detail, status, screener, rankings, fees, favorites, settings, orders, portfolio, assistant, forecasts, seo):
        app.include_router(module.router, prefix="/api")
    return app


fx.use_store(store_loader(get_session_factory()))  # application réelle : cours de change stockés, relus toutes les 10 min
app = create_app()
