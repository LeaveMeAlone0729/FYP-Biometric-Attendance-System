"""Application composition; feature logic lives in routers and services."""

from contextlib import asynccontextmanager

from api import API_VERSION
from api.accounts import router as accounts_router
from api.attendance import router as attendance_router
from api.context import AppContext
from api.errors import register_error_handlers
from api.system import router as system_router
from modules.devices.router import router as devices_router
from biometrics import Biometrics
from config import Settings, local_now
from database import make_engine
from fastapi import FastAPI
from modules.biometrics.router import router as biometrics_router


def create_app(settings=None, engine=None, biometrics=None, clock=None):
    settings = settings or Settings()
    engine = engine or make_engine(settings)
    context = AppContext(
        settings,
        engine,
        biometrics or Biometrics(),
        clock or (lambda: local_now(settings)),
    )

    @asynccontextmanager
    async def lifespan(app):
        if not settings.biometric_key:
            raise RuntimeError("BIOMETRIC_KEY is missing. Run python setup.py first.")
        try:
            yield
        finally:
            context.bio.close()
            engine.dispose()

    app = FastAPI(
        title="Mobile Biometric Attendance",
        version=API_VERSION,
        description="Facial recognition and liveness module by Chew Zhexuan, with supporting demo accounts and attendance.",
        lifespan=lifespan,
    )
    app.state.context = context
    app.state.sessions = context.sessions
    app.state.settings = settings
    register_error_handlers(app)
    for router in (
        system_router,
        accounts_router,
        attendance_router,
        biometrics_router,
        devices_router,
    ):
        app.include_router(router)
    return app


app = create_app()
