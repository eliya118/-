"""Notifier process: health endpoint, stream consumer, ARQ worker, due poll."""

from __future__ import annotations

import asyncio
import logging
from contextlib import asynccontextmanager
from uuid import UUID

import redis.asyncio as redis_async
from arq.connections import RedisSettings, create_pool
from arq.worker import Worker
from fastapi import FastAPI
from fastapi.responses import JSONResponse
from sqlalchemy import text

from notifier.channels.email import build_email_channel
from notifier.db import make_engine, make_session_factory
from notifier.logging import configure_logging
from notifier.runtime import STREAM_KEY, clear_old_titles, consume_forever, perform_send, send_due
from notifier.settings import Settings

log = logging.getLogger("notifier")


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or Settings()  # type: ignore[call-arg]
    configure_logging(settings.log_level)
    engine = make_engine(settings)
    factory = make_session_factory(engine)
    redis_client = redis_async.from_url(settings.redis_url, decode_responses=True)
    enabled = {name.strip() for name in settings.notifier_channels.split(",") if name.strip()}
    channel_map = {}
    if "email" in enabled:
        channel_map["email"] = build_email_channel(
            settings.email_mode, settings.smtp_url, settings.resend_api_key, settings.email_from
        )

    async def send_reminder(ctx: dict[str, object], reminder_id: str) -> None:
        del ctx
        await perform_send(factory, channel_map, UUID(reminder_id))

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        stop = asyncio.Event()
        pool = await create_pool(RedisSettings.from_dsn(settings.redis_url))
        app.state.redis = redis_client

        async def due_loop() -> None:
            while not stop.is_set():
                try:
                    await send_due(factory, channel_map)
                except Exception:
                    log.exception("due poll failed")
                try:
                    await asyncio.wait_for(stop.wait(), timeout=5)
                except TimeoutError:
                    continue

        async def title_loop() -> None:
            while not stop.is_set():
                try:
                    await clear_old_titles(factory)
                except Exception:
                    log.exception("title cleanup failed")
                try:
                    await asyncio.wait_for(stop.wait(), timeout=3600)
                except TimeoutError:
                    continue

        async def arq_loop() -> None:
            worker = Worker(
                functions=[send_reminder],
                redis_settings=RedisSettings.from_dsn(settings.redis_url),
                queue_name="arq:queue",
                max_tries=5,
                job_timeout=120,
                keep_result=0,
                handle_signals=False,
            )
            await worker.async_run()

        tasks = [
            asyncio.create_task(consume_forever(redis_client, factory, enabled, stop, pool)),
            asyncio.create_task(due_loop()),
            asyncio.create_task(title_loop()),
            asyncio.create_task(arq_loop()),
        ]
        yield
        stop.set()
        for task in tasks:
            task.cancel()
        await pool.aclose()
        await redis_client.aclose()
        await engine.dispose()

    app = FastAPI(title="notifier", lifespan=lifespan)

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

    _ = STREAM_KEY
    return app


app = create_app()
