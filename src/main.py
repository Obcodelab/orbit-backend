import sys
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.exceptions import HTTPException, RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from loguru import logger
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded

from core.config import settings
from core.database import dispose_engine, verify_database_connection
from core.exception_handlers import (
    general_exception_handler,
    http_exception_handler,
    validation_error_handler,
)
from core.rate_limit import limiter
from core.types import Environment
from routers import api_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Starting Orbit application...")

    logger.info("Verifying database connectivity...")
    await verify_database_connection()

    logger.info("Orbit application started successfully")

    yield

    logger.info("Shutting down Orbit application...")
    await dispose_engine()
    logger.info("Shutdown complete")


logger.configure(
    handlers=[
        {
            "sink": sys.stderr,
            "level": "INFO",
            "serialize": True,
        },
    ]
)

_is_local = settings.ENVIRONMENT == Environment.LOCAL

app = FastAPI(
    title="Orbit API",
    description="Orbit backend interface",
    version="0.1.0",
    lifespan=lifespan,
    docs_url="/docs" if _is_local else None,
    redoc_url="/redoc" if _is_local else None,
    openapi_url="/openapi.json" if _is_local else None,
)

app.add_middleware(TrustedHostMiddleware, allowed_hosts=settings.ALLOWED_HOSTS)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.BACKEND_CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.add_middleware(GZipMiddleware, minimum_size=1000)

app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)  # type: ignore
app.add_exception_handler(RequestValidationError, validation_error_handler)  # type: ignore
app.add_exception_handler(HTTPException, http_exception_handler)
app.add_exception_handler(Exception, general_exception_handler)

app.include_router(api_router, prefix="/api/v1")


@app.get("/health")
async def health_check():
    return {
        "status": "healthy",
        "service": "orbit-backend",
        "environment": settings.ENVIRONMENT,
    }


@app.get("/")
async def root():
    return {"message": "Welcome to the Orbit API", "docs": "/docs", "health": "/health"}
