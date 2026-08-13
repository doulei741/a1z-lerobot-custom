from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api.routes import router, ws_router
from app.core.config import Settings
from app.core.database import TaskRepository
from app.core.errors import ApiError
from app.services.calibration import PairingProfiles
from app.services.event_bus import EventBus
from app.services.hardware_manager import HardwareResourceManager
from app.services.task_manager import TaskManager
from app.services.workflows import (
    CommandBuilder,
    DatasetCompatibilityService,
    HealthService,
    PolicyService,
    Services,
)


def create_app() -> FastAPI:
    settings = Settings()
    settings.prepare()
    hardware = HardwareResourceManager()
    events = EventBus()
    assert settings.database_path is not None
    repository = TaskRepository(settings.database_path)
    repository.recover_interrupted()
    tasks = TaskManager(settings, hardware, events, repository)
    service_container = Services(
        settings=settings,
        hardware=hardware,
        events=events,
        tasks=tasks,
        commands=CommandBuilder(settings),
        policy=PolicyService(settings),
        health=HealthService(settings),
        datasets=DatasetCompatibilityService(settings),
        profiles=PairingProfiles(settings.project_root / "a1z_web" / "config" / "profiles"),
    )

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        app.state.services = service_container
        yield
        await tasks.shutdown()

    app = FastAPI(title="A1Z LeRobot Web API", version="0.1.0", lifespan=lifespan)
    app.state.services = service_container
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[item.strip() for item in settings.cors_origins.split(",") if item.strip()],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.exception_handler(ApiError)
    async def api_error_handler(_request: Request, exc: ApiError) -> JSONResponse:
        return JSONResponse(status_code=exc.status_code, content=exc.payload())

    app.include_router(router, prefix="/api")
    app.include_router(ws_router)
    return app


app = create_app()
