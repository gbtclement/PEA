from fastapi import FastAPI

from app.api.routes import health, rankings, screener, securities, status


def create_app() -> FastAPI:
    app = FastAPI(title="PEA Radar API")
    for module in (health, securities, status, screener, rankings):
        app.include_router(module.router, prefix="/api")
    return app


app = create_app()
