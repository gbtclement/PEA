from fastapi import FastAPI

from app.api.routes import favorites, fees, health, orders, portfolio, rankings, screener, securities, security_detail, settings, status


def create_app() -> FastAPI:
    app = FastAPI(title="PEA Radar API")
    for module in (health, securities, security_detail, status, screener, rankings, fees, favorites, settings, orders, portfolio):
        app.include_router(module.router, prefix="/api")
    return app


app = create_app()
