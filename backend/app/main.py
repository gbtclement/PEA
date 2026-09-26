from fastapi import FastAPI

from app.api.routes import health


def create_app() -> FastAPI:
    app = FastAPI(title="PEA Radar API")
    app.include_router(health.router, prefix="/api")
    return app


app = create_app()
