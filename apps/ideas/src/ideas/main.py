"""Ideas HTTP process. Seed catalog when no API key is set."""

from __future__ import annotations

import datetime as dt
import hmac
import logging
import uuid
from contextlib import asynccontextmanager
from typing import Any
from zoneinfo import ZoneInfo

from fastapi import FastAPI, Header, Query, Request
from fastapi.responses import JSONResponse
from llm.openai import OpenAILanguageModel
from llm.protocol import CompletionRequest, LanguageModelError
from sqlalchemy import select, text

from ideas.catalog_loader import load_catalog, pick_items
from ideas.db import SuggestionCache, make_engine, make_session_factory
from ideas.ids import new_id
from ideas.logging import configure_logging, request_id_var
from ideas.settings import Settings

log = logging.getLogger("ideas")
JERUSALEM = ZoneInfo("Asia/Jerusalem")
CATALOG = load_catalog()
VERSION = str(CATALOG.get("version", "1"))
CONTEXTS = {"ordinary", "shabbat", "yom_tov", "chol_hamoed"}
BANDS = {"0-2", "3-5", "6-8", "9-12", "13-17", "general"}


def _week_key(now: dt.datetime | None = None) -> str:
    local = (now or dt.datetime.now(JERUSALEM)).astimezone(JERUSALEM)
    year, week, _day = local.date().isocalendar()
    return f"{year}-W{week:02d}"


async def _cached(factory, kind: str, age_band: str, locale: str, slot: str, day_context: str):  # type: ignore[no-untyped-def]
    week = _week_key()
    async with factory() as session:
        row = await session.scalar(
            select(SuggestionCache).where(
                SuggestionCache.kind == kind,
                SuggestionCache.age_band == age_band,
                SuggestionCache.locale == locale,
                SuggestionCache.slot == slot,
                SuggestionCache.iso_week == week,
                SuggestionCache.day_context == day_context,
                SuggestionCache.catalog_version == VERSION,
            )
        )
        if row is None:
            return None
        return row.body


async def _store(  # type: ignore[no-untyped-def]
    factory, kind: str, age_band: str, locale: str, slot: str, day_context: str, body: dict[str, Any]
) -> None:
    async with factory() as session:
        session.add(
            SuggestionCache(
                id=new_id(),
                kind=kind,
                age_band=age_band,
                locale=locale,
                slot=slot,
                iso_week=_week_key(),
                day_context=day_context,
                catalog_version=VERSION,
                body=body,
                created_at=dt.datetime.now(JERUSALEM),
            )
        )
        try:
            await session.commit()
        except Exception:
            await session.rollback()


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or Settings()  # type: ignore[call-arg]
    configure_logging(settings.log_level)
    engine = make_engine(settings)
    factory = make_session_factory(engine)

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        yield
        await engine.dispose()

    app = FastAPI(title="ideas", lifespan=lifespan)
    app.state.settings = settings

    def authorized(authorization: str | None) -> bool:
        token = ""
        if authorization and authorization.startswith("Bearer "):
            token = authorization.removeprefix("Bearer ")
        return hmac.compare_digest(token, settings.internal_api_token)

    @app.middleware("http")
    async def request_context(request: Request, call_next):  # type: ignore[no-untyped-def]
        incoming = request.headers.get("x-request-id") or str(uuid.uuid4())
        token = request_id_var.set(incoming)
        try:
            response = await call_next(request)
            response.headers["X-Request-ID"] = incoming
            return response
        finally:
            request_id_var.reset(token)

    async def answer(
        kind: str, age_band: str, locale: str, slot: str, day_context: str, day_label: str
    ) -> dict[str, Any]:
        if age_band not in BANDS or locale not in {"he", "en"} or day_context not in CONTEXTS:
            return {"error": "invalid"}
        cached = await _cached(factory, kind, age_band, locale, slot, day_context)
        if isinstance(cached, dict) and "items" in cached:
            return cached
        use_model = settings.llm_provider == "openai" and bool(settings.llm_api_key)
        if use_model:
            generated = await _generate(settings, kind, age_band, locale, slot, day_context, day_label)
            if generated is not None:
                body = {"items": generated, "source": "generated"}
                await _store(factory, kind, age_band, locale, slot, day_context, body)
                return body
        items = pick_items(CATALOG, kind, age_band, locale, slot, day_context)
        body = {"items": items, "source": "seed"}
        await _store(factory, kind, age_band, locale, slot, day_context, body)
        return body

    @app.get("/health")
    async def health() -> dict[str, str]:
        return {"status": "ok"}

    @app.get("/ready")
    async def ready() -> JSONResponse:
        try:
            async with engine.connect() as connection:
                await connection.execute(text("SELECT 1"))
        except Exception:
            log.exception("ready check failed")
            return JSONResponse({"status": "not_ready"}, status_code=503)
        return JSONResponse({"status": "ok"})

    @app.get("/internal/activities")
    async def activities(
        age_band: str = Query(...),
        locale: str = Query(...),
        day_context: str = Query("ordinary"),
        day_label: str = Query(""),
        authorization: str | None = Header(default=None),
    ) -> JSONResponse:
        if not authorized(authorization):
            return JSONResponse({"error": "unauthorized"}, status_code=401)
        body = await answer("activity", age_band, locale, "activity", day_context, day_label)
        if body.get("error"):
            return JSONResponse({"error": "invalid"}, status_code=400)
        return JSONResponse(body)

    @app.get("/internal/meals")
    async def meals(
        slot: str = Query(...),
        locale: str = Query(...),
        age_band: str = Query("general"),
        day_context: str = Query("ordinary"),
        day_label: str = Query(""),
        authorization: str | None = Header(default=None),
    ) -> JSONResponse:
        if not authorized(authorization):
            return JSONResponse({"error": "unauthorized"}, status_code=401)
        if slot not in {"breakfast", "dinner"}:
            return JSONResponse({"error": "invalid"}, status_code=400)
        body = await answer("meal", age_band, locale, slot, day_context, day_label)
        if body.get("error"):
            return JSONResponse({"error": "invalid"}, status_code=400)
        return JSONResponse(body)

    return app


async def _generate(
    settings: Settings,
    kind: str,
    age_band: str,
    locale: str,
    slot: str,
    day_context: str,
    day_label: str,
) -> list[dict[str, str]] | None:
    model = OpenAILanguageModel(api_key=settings.llm_api_key, model=settings.llm_model)
    language = "Hebrew" if locale == "he" else "English"
    prompt = (
        f"Suggest three short {kind} ideas for children in Israel. "
        f"Age band {age_band}. Slot {slot}. Day context {day_context}. Label {day_label}. "
        f"Language: {language}. Ordinary groceries and kid-scale activities. No medical claims. "
        "Return JSON {\"items\": [{\"id\": string, \"text\": string}]}."
    )
    schema: dict[str, object] = {
        "type": "object",
        "additionalProperties": False,
        "properties": {
            "items": {
                "type": "array",
                "items": {
                    "type": "object",
                    "additionalProperties": False,
                    "properties": {"id": {"type": "string"}, "text": {"type": "string"}},
                    "required": ["id", "text"],
                },
            }
        },
        "required": ["items"],
    }
    try:
        result = await model.complete(
            CompletionRequest(
                purpose="activities" if kind == "activity" else "meals",
                schema_name="suggestions",
                json_schema=schema,
                instructions="You write household copy for a family in Israel.",
                input=prompt,
            )
        )
    except LanguageModelError:
        log.warning("idea generation failed")
        return None
    items = result.json_data.get("items")
    if not isinstance(items, list) or not items:
        return None
    cleaned: list[dict[str, str]] = []
    for item in items:
        if isinstance(item, dict) and isinstance(item.get("text"), str) and isinstance(item.get("id"), str):
            cleaned.append({"id": item["id"][:80], "text": item["text"][:300]})
    return cleaned or None


app = create_app()
