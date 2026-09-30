from fastapi import FastAPI

from app.api.routes import admin, assistant, auth, favorites, google, fees, forecasts, health, me, orders, portfolio, rankings, screener, securities, security_detail, seo, settings, status


def create_app() -> FastAPI:
    app = FastAPI(title="PEA Radar API")
    for module in (health, auth, google, me, admin, securities, security_detail, status, screener, rankings, fees, favorites, settings, orders, portfolio, assistant, forecasts, seo):
        app.include_router(module.router, prefix="/api")
    return app


app = create_app()
