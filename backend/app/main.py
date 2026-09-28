from fastapi import FastAPI

from app.api.routes import assistant, favorites, fees, forecasts, health, me, orders, portfolio, rankings, screener, securities, security_detail, seo, settings, status


def create_app() -> FastAPI:
    app = FastAPI(title="PEA Radar API")
    for module in (health, me, securities, security_detail, status, screener, rankings, fees, favorites, settings, orders, portfolio, assistant, forecasts, seo):
        app.include_router(module.router, prefix="/api")
    return app


app = create_app()
