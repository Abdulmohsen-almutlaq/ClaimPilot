from fastapi import FastAPI

from app.api import auth, cases, health


def create_app() -> FastAPI:
    app = FastAPI(title="ClaimPilot", version="0.1.0")
    app.include_router(health.router)
    app.include_router(auth.router)
    app.include_router(cases.router)
    return app


app = create_app()
