import os
import logging
from uuid import uuid4
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.core.config import settings
from app.core.database import Base, engine, check_database_connection
from app.core.logging import (
    configure_logging,
    request_id_var,
    request_method_var,
    request_path_var,
)
from app.api.router import api_router

# Importa modelos para que SQLAlchemy conozca las tablas
from app.models.part import Part
from app.models.asset import Asset
from app.models.intervention import Intervention, InterventionAsset, Evidence
from app.models.user import User

configure_logging()
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    os.makedirs(settings.media_dir, exist_ok=True)

    if settings.using_default_auth_secret and not settings.is_default_local_database:
        raise RuntimeError(
            "AUTH_SECRET_KEY debe configurarse con un valor seguro antes de iniciar la aplicación."
        )

    # Only allow direct table creation when explicitly enabled for local/dev use.
    if settings.auto_create_tables:
        Base.metadata.create_all(bind=engine)

    yield


app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def request_context_middleware(request: Request, call_next):
    request_id = str(uuid4())
    request.state.request_id = request_id

    token_id = request_id_var.set(request_id)
    token_method = request_method_var.set(request.method)
    token_path = request_path_var.set(request.url.path)

    try:
        response = await call_next(request)
        response.headers["X-Request-ID"] = request_id
        logger.info("Request completed", extra={"status_code": response.status_code})
        return response
    finally:
        request_id_var.reset(token_id)
        request_method_var.reset(token_method)
        request_path_var.reset(token_path)


app.include_router(api_router)


@app.get("/health", tags=["Health"])
def health_check():
    if check_database_connection():
        logger.info("Health check OK", extra={"database": "ok"})
        return {"status": "ok", "database": "ok"}

    logger.error("Health check failed", extra={"database": "error"})
    return JSONResponse(
        status_code=503,
        content={"status": "error", "database": "error"},
        headers={"X-Request-ID": request_id_var.get()},
    )


@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    request_id_var.set(getattr(request.state, "request_id", request_id_var.get()))
    request_method_var.set(request.method)
    request_path_var.set(request.url.path)
    logger.warning(
        "HTTP exception",
        extra={"status_code": exc.status_code, "detail": exc.detail},
    )
    headers = dict(getattr(exc, "headers", {}) or {})
    headers["X-Request-ID"] = getattr(request.state, "request_id", request_id_var.get())
    return JSONResponse(
        status_code=exc.status_code,
        content={"detail": exc.detail},
        headers=headers,
    )


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception):
    request_id_var.set(getattr(request.state, "request_id", request_id_var.get()))
    request_method_var.set(request.method)
    request_path_var.set(request.url.path)
    logger.exception(
        "Unhandled exception",
    )
    return JSONResponse(
        status_code=500,
        content={"detail": "Error interno del servidor."},
        headers={"X-Request-ID": getattr(request.state, "request_id", request_id_var.get())},
    )
