from fastapi import FastAPI

from app.api import admin, auth, cases, health, metrics, track


def create_app() -> FastAPI:
    app = FastAPI(title="ClaimPilot", version="0.1.0")
    app.include_router(health.router)
    app.include_router(auth.router)
    app.include_router(cases.router)
    app.include_router(admin.router)
    app.include_router(metrics.router)
    app.include_router(track.router)
    return app


app = create_app()
