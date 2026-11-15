"""Public HTTP API. The browser is the only caller."""

from __future__ import annotations

import datetime as dt
import hashlib
import hmac
import json
import logging
from typing import Any
from uuid import UUID
from zoneinfo import ZoneInfo

import httpx
from contracts.drafts import ChildRef, ParseRequest
from contracts.errors import ErrorCode
from contracts.events import ContactRemoved, EventCancelled, EventUpserted
from fastapi import APIRouter, Header, Request, Response
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from hebrewcal import day_context, day_label, describe_day, describe_week
from kc_calendar.db.models import Child, Event, EventChild, Family, Idempotency, Outbox, ParentAccount, SessionRow
from kc_calendar.domain.age import age_band, age_years
from kc_calendar.domain.names import tokenize
from kc_calendar.domain.remind import compute_remind_at
from kc_calendar.domain.timeutil import civil_date, jerusalem_today, now_jerusalem
from kc_calendar.domain.week import NotSundayError, require_sunday
from kc_calendar.google_sync import GoogleSyncError, delete_google_event, upsert_google_event
from kc_calendar.ids import new_id
from kc_calendar.logging import request_id_var
from kc_calendar.security import hash_token, new_session_token, verify_password

log = logging.getLogger("calendar.api")
JERUSALEM = ZoneInfo("Asia/Jerusalem")
SESSION_COOKIE = "kc_session"
SESSION_DAYS = 14
router = APIRouter()


class ApiError(Exception):
    def __init__(self, status: int, code: ErrorCode, message: str) -> None:
        self.status = status
        self.code = code
        self.message = message


class LoginIn(BaseModel):
    email: str
    password: str


class ChildIn(BaseModel):
    id: UUID | None = None
    display_name: str = Field(min_length=1, max_length=80)
    birth_year: int = Field(ge=1990, le=2100)
    birth_month: int = Field(ge=1, le=12)


class ChildrenIn(BaseModel):
    children: list[ChildIn]


class EventIn(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    starts_at: dt.datetime
    ends_at: dt.datetime | None = None
    all_day: bool = False
    locale: str = "he"
    child_ids: list[UUID] = Field(min_length=1)
    remind_offset_minutes: int | None = Field(default=None, ge=0, le=10080)


class EventPatch(BaseModel):
    title: str | None = Field(default=None, max_length=200)
    starts_at: dt.datetime | None = None
    ends_at: dt.datetime | None = None
    all_day: bool | None = None
    locale: str | None = None
    child_ids: list[UUID] | None = None
    remind_offset_minutes: int | None = Field(default=None, ge=0, le=10080)


class PreviewIn(BaseModel):
    text: str = Field(min_length=1, max_length=1000)
    locale: str = "he"


class ConfirmIn(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    child_ids: list[UUID] = Field(min_length=1)
    starts_at: dt.datetime
    ends_at: dt.datetime | None = None
    all_day: bool = False
    remind_at: dt.datetime | None = None
    locale: str = "he"


def _aware(moment: dt.datetime, field: str) -> dt.datetime:
    if moment.tzinfo is None:
        raise ApiError(400, ErrorCode.validation_error, f"{field} needs a timezone offset")
    return moment.astimezone(dt.UTC)


def _locale(value: str) -> str:
    if value not in {"he", "en"}:
        raise ApiError(400, ErrorCode.validation_error, "locale must be he or en")
    return value


def _dump_event(event: Event, child_ids: list[UUID]) -> dict[str, Any]:
    return {
        "id": str(event.id),
        "title": event.title,
        "starts_at": event.starts_at.isoformat(),
        "ends_at": event.ends_at.isoformat() if event.ends_at else None,
        "all_day": event.all_day,
        "remind_at": event.remind_at.isoformat() if event.remind_at else None,
        "generation": event.generation,
        "locale": event.locale,
        "child_ids": [str(child_id) for child_id in child_ids],
        "civil_date": civil_date(event.starts_at).isoformat(),
    }


def _day_payload(info: Any) -> dict[str, Any]:
    return {
        "civil_date": info.civil_date.isoformat(),
        "hebrew": {
            "year": info.hebrew.year,
            "month": info.hebrew.month,
            "day": info.hebrew.day,
            "display_he": info.hebrew.display_he,
            "display_en": info.hebrew.display_en,
        },
        "shabbat": info.shabbat,
        "holidays": [
            {"kind": holiday.kind, "name_he": holiday.name_he, "name_en": holiday.name_en}
            for holiday in info.holidays
        ],
        "candle_lighting": info.candle_lighting.isoformat() if info.candle_lighting else None,
        "havdalah": info.havdalah.isoformat() if info.havdalah else None,
    }


async def _family_id(request: Request, db: AsyncSession) -> tuple[SessionRow, UUID]:
    token = request.cookies.get(SESSION_COOKIE)
    if not token:
        raise ApiError(401, ErrorCode.unauthenticated, "Sign in again.")
    row = await db.scalar(select(SessionRow).where(SessionRow.token_hash == hash_token(token)))
    if row is None or row.expires_at <= now_jerusalem():
        raise ApiError(401, ErrorCode.unauthenticated, "Sign in again.")
    return row, row.family_id


async def _owned_children(db: AsyncSession, family_id: UUID, child_ids: list[UUID]) -> list[Child]:
    rows = (
        await db.scalars(select(Child).where(Child.family_id == family_id, Child.id.in_(child_ids)))
    ).all()
    if len(rows) != len(set(child_ids)):
        raise ApiError(400, ErrorCode.validation_error, "Pick a child from this family.")
    return list(rows)


def _outbox(event_type: str, payload: dict[str, Any]) -> Outbox:
    return Outbox(id=new_id(), type=event_type, payload=payload, created_at=now_jerusalem(), attempts=0)


async def _idempotent(
    db: AsyncSession,
    key: str | None,
    raw_body: bytes,
    produce: Any,
) -> JSONResponse:
    if not key or len(key) > 200:
        raise ApiError(400, ErrorCode.validation_error, "Idempotency-Key is required.")
    digest = hashlib.sha256(raw_body).hexdigest()
    existing = await db.get(Idempotency, key)
    cutoff = now_jerusalem() - dt.timedelta(hours=24)
    if existing is not None and existing.created_at >= cutoff:
        if not hmac.compare_digest(existing.request_hash, digest):
            raise ApiError(409, ErrorCode.validation_error, "That idempotency key was already used.")
        return JSONResponse(status_code=existing.status_code, content=existing.response_json)
    if existing is not None:
        await db.delete(existing)
        await db.flush()
    status, body = await produce()
    db.add(
        Idempotency(
            key=key,
            request_hash=digest,
            status_code=status,
            response_json=body,
            created_at=now_jerusalem(),
        )
    )
    return JSONResponse(status_code=status, content=body)


async def _hit_rate(request: Request, bucket: str, limit: int, fail_closed: bool) -> None:
    redis = request.app.state.redis
    session_row: SessionRow = request.state.session_row
    key = f"rate:{bucket}:{session_row.id}"
    try:
        count = await redis.incr(key)
        if int(count) == 1:
            await redis.expire(key, 3600)
    except Exception as exc:
        log.warning("rate limit counter unavailable", extra={"family_id": str(session_row.family_id)})
        if fail_closed:
            raise ApiError(503, ErrorCode.upstream_unavailable, "Preview is unavailable right now.") from exc
        return
    if int(count) > limit:
        raise ApiError(429, ErrorCode.rate_limited, "Too many of those this hour. Try again later.")


@router.post("/api/session", status_code=204)
async def login(body: LoginIn, request: Request) -> Response:
    db: AsyncSession = request.state.db
    email = body.email.strip().lower()
    account = await db.scalar(select(ParentAccount).where(ParentAccount.email == email))
    if account is None or not verify_password(body.password, account.password_hash):
        raise ApiError(401, ErrorCode.unauthenticated, "The email or password is wrong.")
    token = new_session_token()
    db.add(
        SessionRow(
            id=new_id(),
            token_hash=hash_token(token),
            family_id=account.family_id,
            expires_at=now_jerusalem() + dt.timedelta(days=SESSION_DAYS),
        )
    )
    await db.commit()
    response = Response(status_code=204)
    response.set_cookie(
        key=SESSION_COOKIE,
        value=token,
        httponly=True,
        secure=request.app.state.settings.cookie_secure,
        samesite="lax",
        path="/",
        max_age=SESSION_DAYS * 24 * 3600,
    )
    log.info("session created", extra={"family_id": str(account.family_id)})
    return response


@router.delete("/api/session", status_code=204)
async def logout(request: Request) -> Response:
    db: AsyncSession = request.state.db
    token = request.cookies.get(SESSION_COOKIE)
    if token:
        await db.execute(delete(SessionRow).where(SessionRow.token_hash == hash_token(token)))
        await db.commit()
    response = Response(status_code=204)
    response.delete_cookie(SESSION_COOKIE, path="/")
    return response


@router.get("/api/family")
async def get_family(request: Request) -> dict[str, Any]:
    db: AsyncSession = request.state.db
    _session, family_id = await _family_id(request, db)
    family = await db.get(Family, family_id)
    if family is None:
        raise ApiError(404, ErrorCode.not_found, "Family not found.")
    children = (
        await db.scalars(select(Child).where(Child.family_id == family_id).order_by(Child.display_name))
    ).all()
    today = jerusalem_today()
    return {
        "id": str(family.id),
        "timezone": family.timezone,
        "locale": family.locale,
        "children": [
            {
                "id": str(child.id),
                "display_name": child.display_name,
                "birth_year": child.birth_year,
                "birth_month": child.birth_month,
                "age_years": age_years(child.birth_year, child.birth_month, today),
                "age_band": age_band(child.birth_year, child.birth_month, today),
            }
            for child in children
        ],
    }


@router.put("/api/children")
async def put_children(body: ChildrenIn, request: Request) -> dict[str, Any]:
    db: AsyncSession = request.state.db
    _session, family_id = await _family_id(request, db)
    existing = (await db.scalars(select(Child).where(Child.family_id == family_id))).all()
    by_id = {child.id: child for child in existing}
    seen: set[UUID] = set()
    for item in body.children:
        name = item.display_name.strip()
        if item.id is not None:
            row = by_id.get(item.id)
            if row is None:
                raise ApiError(404, ErrorCode.not_found, "Unknown child.")
            row.display_name = name
            row.birth_year = item.birth_year
            row.birth_month = item.birth_month
            seen.add(item.id)
        else:
            db.add(
                Child(
                    id=new_id(),
                    family_id=family_id,
                    display_name=name,
                    birth_year=item.birth_year,
                    birth_month=item.birth_month,
                )
            )
    for child_id, row in by_id.items():
        if child_id not in seen:
            await db.delete(row)
    await db.commit()
    return await get_family(request)


@router.get("/api/weeks/{sunday}")
async def get_week(sunday: dt.date, request: Request) -> dict[str, Any]:
    db: AsyncSession = request.state.db
    _session, family_id = await _family_id(request, db)
    try:
        require_sunday(sunday)
    except NotSundayError as exc:
        raise ApiError(400, ErrorCode.validation_error, str(exc)) from exc
    start = dt.datetime.combine(sunday, dt.time.min, tzinfo=JERUSALEM)
    end = start + dt.timedelta(days=7)
    events = (
        await db.scalars(
            select(Event)
            .where(
                Event.family_id == family_id,
                Event.deleted_at.is_(None),
                Event.starts_at >= start,
                Event.starts_at < end,
            )
            .options(selectinload(Event.children))
            .order_by(Event.starts_at)
        )
    ).all()
    return {
        "sunday": sunday.isoformat(),
        "days": [_day_payload(day) for day in describe_week(sunday)],
        "events": [_dump_event(event, [child.id for child in event.children]) for event in events],
    }


async def _insert_event(
    db: AsyncSession,
    family_id: UUID,
    title: str,
    starts_at: dt.datetime,
    ends_at: dt.datetime | None,
    all_day: bool,
    locale: str,
    child_ids: list[UUID],
    remind_at: dt.datetime | None,
    request_id: str,
) -> Event:
    await _owned_children(db, family_id, child_ids)
    event = Event(
        id=new_id(),
        family_id=family_id,
        title=title.strip(),
        starts_at=starts_at,
        ends_at=ends_at,
        all_day=all_day,
        remind_at=remind_at,
        generation=1,
        locale=locale,
    )
    db.add(event)
    await db.flush()
    for child_id in child_ids:
        db.add(EventChild(event_id=event.id, child_id=child_id))
    payload = EventUpserted(
        event_id=event.id,
        family_id=family_id,
        generation=event.generation,
        title=event.title,
        starts_at=event.starts_at,
        remind_at=event.remind_at,
        locale=locale,  # type: ignore[arg-type]
        request_id=request_id or None,
    ).model_dump(mode="json")
    db.add(_outbox("calendar.event_upserted", payload))
    return event


async def _mirror_google(request: Request, db: AsyncSession, response: JSONResponse) -> None:
    if response.status_code not in {200, 201}:
        return
    try:
        body = json.loads(bytes(response.body))
    except json.JSONDecodeError:
        return
    raw_id = body.get("id") if isinstance(body, dict) else None
    if not isinstance(raw_id, str):
        return
    event = await db.get(Event, UUID(raw_id))
    if event is None or event.deleted_at is not None:
        return
    family = await db.get(Family, event.family_id)
    if family is None or not family.google_refresh_token:
        return
    try:
        google_id = await upsert_google_event(
            request.app.state.settings,
            family.google_refresh_token,
            event.google_event_id,
            event.title,
            event.starts_at,
            event.ends_at,
            event.all_day,
        )
    except GoogleSyncError:
        log.warning("google sync failed", extra={"event_id": str(event.id)})
        return
    if google_id != event.google_event_id:
        event.google_event_id = google_id
        await db.commit()


@router.post("/api/events", status_code=201)
async def create_event(
    body: EventIn,
    request: Request,
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
) -> JSONResponse:
    db: AsyncSession = request.state.db
    _session, family_id = await _family_id(request, db)
    raw = request.state.raw_body

    async def produce() -> tuple[int, dict[str, Any]]:
        starts = _aware(body.starts_at, "starts_at")
        ends = _aware(body.ends_at, "ends_at") if body.ends_at else None
        locale = _locale(body.locale)
        remind = compute_remind_at(starts, body.all_day, now_jerusalem(), body.remind_offset_minutes)
        event = await _insert_event(
            db,
            family_id,
            body.title,
            starts,
            ends,
            body.all_day,
            locale,
            body.child_ids,
            remind,
            request_id_var.get(),
        )
        await db.flush()
        loaded = await db.scalar(
            select(Event).where(Event.id == event.id).options(selectinload(Event.children))
        )
        assert loaded is not None
        return 201, _dump_event(loaded, [child.id for child in loaded.children])

    response = await _idempotent(db, idempotency_key, raw, produce)
    await db.commit()
    await _mirror_google(request, db, response)
    log.info("event created", extra={"family_id": str(family_id)})
    return response


@router.patch("/api/events/{event_id}")
async def patch_event(
    event_id: UUID,
    body: EventPatch,
    request: Request,
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
) -> JSONResponse:
    db: AsyncSession = request.state.db
    _session, family_id = await _family_id(request, db)
    raw = request.state.raw_body

    async def produce() -> tuple[int, dict[str, Any]]:
        event = await db.scalar(
            select(Event)
            .where(Event.id == event_id, Event.family_id == family_id, Event.deleted_at.is_(None))
            .options(selectinload(Event.children))
        )
        if event is None:
            raise ApiError(404, ErrorCode.not_found, "Event not found.")
        if body.title is not None:
            event.title = body.title.strip()
        if body.starts_at is not None:
            event.starts_at = _aware(body.starts_at, "starts_at")
        if body.ends_at is not None:
            event.ends_at = _aware(body.ends_at, "ends_at")
        if body.all_day is not None:
            event.all_day = body.all_day
        if body.locale is not None:
            event.locale = _locale(body.locale)
        if body.child_ids is not None:
            await _owned_children(db, family_id, body.child_ids)
            await db.execute(delete(EventChild).where(EventChild.event_id == event.id))
            for child_id in body.child_ids:
                db.add(EventChild(event_id=event.id, child_id=child_id))
        event.generation += 1
        event.remind_at = compute_remind_at(
            event.starts_at, event.all_day, now_jerusalem(), body.remind_offset_minutes
        )
        payload = EventUpserted(
            event_id=event.id,
            family_id=family_id,
            generation=event.generation,
            title=event.title,
            starts_at=event.starts_at,
            remind_at=event.remind_at,
            locale=event.locale,  # type: ignore[arg-type]
            request_id=request_id_var.get() or None,
        ).model_dump(mode="json")
        db.add(_outbox("calendar.event_upserted", payload))
        await db.flush()
        await db.refresh(event, attribute_names=["children"])
        return 200, _dump_event(event, [child.id for child in event.children])

    response = await _idempotent(db, idempotency_key, raw, produce)
    await db.commit()
    await _mirror_google(request, db, response)
    log.info("event updated", extra={"event_id": str(event_id), "family_id": str(family_id)})
    return response


@router.delete("/api/events/{event_id}", status_code=204)
async def delete_event(event_id: UUID, request: Request) -> Response:
    db: AsyncSession = request.state.db
    _session, family_id = await _family_id(request, db)
    event = await db.scalar(
        select(Event).where(Event.id == event_id, Event.family_id == family_id, Event.deleted_at.is_(None))
    )
    if event is None:
        raise ApiError(404, ErrorCode.not_found, "Event not found.")
    event.deleted_at = now_jerusalem()
    event.generation += 1
    payload = EventCancelled(
        event_id=event.id,
        family_id=family_id,
        generation=event.generation,
        request_id=request_id_var.get() or None,
    ).model_dump(mode="json")
    db.add(_outbox("calendar.event_cancelled", payload))
    google_event_id = event.google_event_id
    family = await db.get(Family, family_id)
    refresh_token = family.google_refresh_token if family else None
    await db.commit()
    if refresh_token and google_event_id:
        try:
            await delete_google_event(request.app.state.settings, refresh_token, google_event_id)
        except GoogleSyncError:
            log.warning("google delete failed", extra={"event_id": str(event_id)})
    log.info("event cancelled", extra={"event_id": str(event_id), "family_id": str(family_id)})
    return Response(status_code=204)


@router.post("/api/intake/preview")
async def preview(body: PreviewIn, request: Request) -> dict[str, Any]:
    db: AsyncSession = request.state.db
    session_row, family_id = await _family_id(request, db)
    request.state.session_row = session_row
    await _hit_rate(request, "preview", 30, fail_closed=True)
    locale = _locale(body.locale)
    children = (await db.scalars(select(Child).where(Child.family_id == family_id))).all()
    tokenized, _tokens = tokenize(body.text, [(child.id, child.display_name) for child in children])
    ordered = sorted(children, key=lambda item: str(item.id))
    parse_body = ParseRequest(
        text=tokenized,
        locale_hint=locale,  # type: ignore[arg-type]
        now=now_jerusalem(),
        timezone="Asia/Jerusalem",
        children=[ChildRef(id=child.id, token=f"child_{index}") for index, child in enumerate(ordered, start=1)],
    )
    settings = request.app.state.settings
    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            upstream = await client.post(
                f"{settings.intake_url.rstrip('/')}/internal/parse",
                json=parse_body.model_dump(mode="json"),
                headers={
                    "Authorization": f"Bearer {settings.internal_api_token}",
                    "X-Request-ID": request_id_var.get(),
                },
            )
    except httpx.HTTPError as exc:
        raise ApiError(
            503,
            ErrorCode.upstream_unavailable,
            "Parsing is unavailable. You can still add the event by hand.",
        ) from exc
    if upstream.status_code >= 500 or upstream.status_code == 401:
        raise ApiError(
            503,
            ErrorCode.upstream_unavailable,
            "Parsing is unavailable. You can still add the event by hand.",
        )
    if upstream.status_code >= 400:
        raise ApiError(400, ErrorCode.validation_error, "That sentence could not be read.")
    return upstream.json()


@router.post("/api/intake/confirm", status_code=201)
async def confirm(
    body: ConfirmIn,
    request: Request,
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
) -> JSONResponse:
    db: AsyncSession = request.state.db
    _session, family_id = await _family_id(request, db)
    raw = request.state.raw_body

    async def produce() -> tuple[int, dict[str, Any]]:
        starts = _aware(body.starts_at, "starts_at")
        ends = _aware(body.ends_at, "ends_at") if body.ends_at else None
        locale = _locale(body.locale)
        now = now_jerusalem()
        if body.remind_at is not None:
            remind = _aware(body.remind_at, "remind_at")
            if remind <= now:
                remind = None
        else:
            remind = compute_remind_at(starts, body.all_day, now, None)
        event = await _insert_event(
            db, family_id, body.title, starts, ends, body.all_day, locale, body.child_ids, remind, request_id_var.get()
        )
        await db.flush()
        loaded = await db.scalar(select(Event).where(Event.id == event.id).options(selectinload(Event.children)))
        assert loaded is not None
        return 201, _dump_event(loaded, [child.id for child in loaded.children])

    response = await _idempotent(db, idempotency_key, raw, produce)
    await db.commit()
    await _mirror_google(request, db, response)
    return response


def _today_context(locale: str) -> tuple[str, str]:
    info = describe_day(jerusalem_today())
    return day_context(info), day_label(info, locale)


@router.get("/api/ideas/activities")
async def activities(request: Request, child_id: UUID) -> dict[str, Any]:
    return await _ideas(request, kind="activities", child_id=child_id, slot=None)


@router.get("/api/ideas/meals")
async def meals(request: Request, slot: str, child_id: UUID | None = None) -> dict[str, Any]:
    if slot not in {"breakfast", "dinner"}:
        raise ApiError(400, ErrorCode.validation_error, "slot must be breakfast or dinner")
    return await _ideas(request, kind="meals", child_id=child_id, slot=slot)


async def _ideas(
    request: Request, kind: str, child_id: UUID | None, slot: str | None
) -> dict[str, Any]:
    db: AsyncSession = request.state.db
    session_row, family_id = await _family_id(request, db)
    request.state.session_row = session_row
    await _hit_rate(request, "ideas", 60, fail_closed=False)
    family = await db.get(Family, family_id)
    locale = family.locale if family else "he"
    band = "general"
    if child_id is not None:
        child = await db.scalar(select(Child).where(Child.id == child_id, Child.family_id == family_id))
        if child is None:
            raise ApiError(404, ErrorCode.not_found, "Unknown child.")
        band = age_band(child.birth_year, child.birth_month, jerusalem_today())
    context, label = _today_context(locale)
    params: dict[str, str] = {"locale": locale, "age_band": band, "day_context": context}
    if label:
        params["day_label"] = label
    if slot:
        params["slot"] = slot
    path = "/internal/activities" if kind == "activities" else "/internal/meals"
    settings = request.app.state.settings
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            upstream = await client.get(
                f"{settings.ideas_url.rstrip('/')}{path}",
                params=params,
                headers={
                    "Authorization": f"Bearer {settings.internal_api_token}",
                    "X-Request-ID": request_id_var.get(),
                },
            )
        upstream.raise_for_status()
        body = upstream.json()
        body["degraded"] = False
        return body
    except (httpx.HTTPError, json.JSONDecodeError):
        return {"items": [], "source": "seed", "degraded": True}


@router.delete("/api/family", status_code=204)
async def delete_family(request: Request) -> Response:
    db: AsyncSession = request.state.db
    _session, family_id = await _family_id(request, db)
    events = (
        await db.scalars(select(Event).where(Event.family_id == family_id, Event.deleted_at.is_(None)))
    ).all()
    now = now_jerusalem()
    for event in events:
        event.deleted_at = now
        event.generation += 1
        db.add(
            _outbox(
                "calendar.event_cancelled",
                EventCancelled(
                    event_id=event.id,
                    family_id=family_id,
                    generation=event.generation,
                    request_id=request_id_var.get() or None,
                ).model_dump(mode="json"),
            )
        )
    db.add(
        _outbox(
            "family.contact_removed",
            ContactRemoved(family_id=family_id, request_id=request_id_var.get() or None).model_dump(mode="json"),
        )
    )
    await db.execute(delete(SessionRow).where(SessionRow.family_id == family_id))
    await db.execute(delete(Child).where(Child.family_id == family_id))
    await db.commit()
    log.info("family data wiped", extra={"family_id": str(family_id)})
    response = Response(status_code=204)
    response.delete_cookie(SESSION_COOKIE, path="/")
    return response
