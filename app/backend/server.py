import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy import text

from app.backend.api import api_router
from app.backend.middleware import install_middleware
from app.backend.schemas import HealthRead
from app.core.config import cfg
from app.core.logging import configure_logging, current_request_id
from app.database.engine import engine
from app.domain.errors.ai import LlmUnavailableError
from app.domain.errors.domain import DomainError
from app.integrations.kitten import get_voice_backend
from app.integrations.search import close_client as close_search_client
from app.services.llm import get_llm_service
from app.services.scheduler import get_digest_scheduler
from app.services.telegram_bot import get_telegram_runner

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(_: FastAPI):
    runner = get_telegram_runner()
    runner.start()
    scheduler = get_digest_scheduler()
    scheduler.start()
    try:
        yield
    finally:
        await scheduler.stop()
        await runner.stop()
        await get_llm_service().close()
        await get_voice_backend().close()
        await close_search_client()
        await engine.dispose()


def create_app() -> FastAPI:
    app_cfg = cfg.application

    configure_logging(json_logs=app_cfg.log_json)

    app = FastAPI(
        title=app_cfg.name,
        version=app_cfg.version,
        debug=app_cfg.debug,
        docs_url=app_cfg.docs,
        redoc_url=app_cfg.redoc,
        lifespan=lifespan,
    )

    # Starlette wraps the *last* added middleware outermost, so CORS and the
    # Host allow-list go on last: otherwise 401/429 produced by the guards
    # below would ship without `Access-Control-Allow-Origin` and browsers
    # would mask the real error behind a CORS failure.
    install_middleware(app)

    if app_cfg.allowed_hosts:
        app.add_middleware(
            TrustedHostMiddleware,
            allowed_hosts=app_cfg.allowed_hosts,
        )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=app_cfg.allowed_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=[
            "Accept",
            "Authorization",
            "Content-Type",
            "X-API-Key",
            "X-Request-ID",
        ],
        expose_headers=["X-Request-ID", "Retry-After"],
    )

    @app.exception_handler(LlmUnavailableError)
    async def _llm_unavailable(_: Request, exc: LlmUnavailableError) -> JSONResponse:
        return JSONResponse(status_code=502, content={"detail": str(exc)})

    @app.exception_handler(DomainError)
    async def _domain_error(_: Request, exc: DomainError) -> JSONResponse:
        return JSONResponse(status_code=404, content={"detail": str(exc)})

    @app.exception_handler(Exception)
    async def _unhandled(request: Request, exc: Exception) -> JSONResponse:
        request_id = getattr(request.state, "request_id", None) or current_request_id() or "-"
        logger.exception("Unhandled error on %s %s", request.method, request.url.path)
        return JSONResponse(
            status_code=500,
            content={"detail": "Внутренняя ошибка сервера.", "request_id": request_id},
            headers={"X-Request-ID": request_id},
        )

    app.include_router(api_router, prefix=app_cfg.api_prefix)

    @app.get("/health", response_model=HealthRead, tags=["system"], include_in_schema=False)
    async def root_health() -> HealthRead:
        async with engine.connect() as connection:
            await connection.execute(text("SELECT 1"))
        return HealthRead(status="ok", version=app_cfg.version)

    return app


app = create_app()
