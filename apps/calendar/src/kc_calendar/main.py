"""Calendar process: HTTP API plus the outbox relay."""

from __future__ import annotations

import logging
import uuid
from contextlib import asynccontextmanager

import redis.asyncio as redis_async
from contracts.errors import ErrorCode, error_payload
from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.openapi.utils import get_openapi
from fastapi.responses import JSONResponse
from sqlalchemy import text

from kc_calendar.api import ApiError, router
from kc_calendar.bootstrap import bootstrap
from kc_calendar.db.session import make_engine, make_session_factory
from kc_calendar.google_api import router as google_router
from kc_calendar.logging import configure_logging, request_id_var
from kc_calendar.relay import purge_loop, relay_loop
from kc_calendar.settings import Settings

log = logging.getLogger("calendar")
MAX_BODY = 32 * 1024


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or Settings()  # type: ignore[call-arg]
    configure_logging(settings.log_level)
    engine = make_engine(settings)
    session_factory = make_session_factory(engine)
    redis_client = redis_async.from_url(settings.redis_url, decode_responses=True)

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        import asyncio

        app.state.stop = asyncio.Event()
        await bootstrap(session_factory, settings)
        app.state.relay = asyncio.create_task(relay_loop(session_factory, redis_client, app.state.stop))
        app.state.purge = asyncio.create_task(purge_loop(session_factory, app.state.stop))
        yield
        app.state.stop.set()
        app.state.relay.cancel()
        app.state.purge.cancel()
        await redis_client.aclose()
        await engine.dispose()

    app = FastAPI(title="calendar", lifespan=lifespan)
    app.state.settings = settings
    app.state.engine = engine
    app.state.session_factory = session_factory
    app.state.redis = redis_client
    app.include_router(router)
    app.include_router(google_router)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[settings.web_origin],
        allow_credentials=True,
        allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
        allow_headers=["*"],
    )

    @app.middleware("http")
    async def request_context(request: Request, call_next):  # type: ignore[no-untyped-def]
        incoming = request.headers.get("x-request-id") or str(uuid.uuid4())
        token = request_id_var.set(incoming)
        try:
            body = await request.body()
            request.state.raw_body = body
            if request.method in {"POST", "PUT", "PATCH", "DELETE"} and len(body) > MAX_BODY:
                return JSONResponse(
                    status_code=400,
                    content=error_payload(ErrorCode.validation_error, "Request is too large.", incoming),
                )
            if (
                request.method in {"POST", "PUT", "PATCH", "DELETE"}
                and request.url.path.startswith("/api")
                and request.headers.get("x-kc-request") != "1"
            ):
                return JSONResponse(
                    status_code=400,
                    content=error_payload(
                        ErrorCode.validation_error, "Missing X-KC-Request header.", incoming
                    ),
                )
            async with session_factory() as session:
                request.state.db = session
                try:
                    response = await call_next(request)
                except Exception:
                    await session.rollback()
                    raise
            response.headers["X-Request-ID"] = incoming
            return response
        finally:
            request_id_var.reset(token)

    @app.exception_handler(ApiError)
    async def on_api_error(_request: Request, exc: ApiError) -> JSONResponse:
        return JSONResponse(
            status_code=exc.status,
            content=error_payload(exc.code, exc.message, request_id_var.get()),
        )

    @app.exception_handler(RequestValidationError)
    async def on_validation(_request: Request, _exc: RequestValidationError) -> JSONResponse:
        return JSONResponse(
            status_code=400,
            content=error_payload(
                ErrorCode.validation_error, "Check the form and try again.", request_id_var.get()
            ),
        )

    @app.get("/health")
    async def health() -> dict[str, str]:
        return {"status": "ok"}

    @app.get("/ready")
    async def ready() -> JSONResponse:
        try:
            async with engine.connect() as connection:
                await connection.execute(text("SELECT 1"))
            pong = await redis_client.ping()
            if pong is not True:
                raise RuntimeError("redis ping failed")
        except Exception:
            log.exception("ready check failed")
            return JSONResponse({"status": "not_ready"}, status_code=503)
        return JSONResponse({"status": "ok"})

    def openapi() -> dict:  # type: ignore[type-arg]
        if app.openapi_schema:
            return app.openapi_schema
        schema = get_openapi(title="calendar", version="1.0.0", routes=app.routes)
        schema["paths"] = {path: item for path, item in schema["paths"].items() if path.startswith("/api")}
        app.openapi_schema = schema
        return schema

    app.openapi = openapi  # type: ignore[method-assign]
    return app


app = create_app()
