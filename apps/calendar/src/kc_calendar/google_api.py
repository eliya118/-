"""Connect the signed-in parent to Google Calendar."""

import logging

from contracts.errors import ErrorCode
from fastapi import APIRouter, Request
from fastapi.responses import RedirectResponse, Response
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from kc_calendar.api import ApiError, _family_id
from kc_calendar.db.models import Family
from kc_calendar.google_sync import (
    GoogleSyncError,
    authorization_url,
    configured,
    exchange_code,
    read_state,
    sign_state,
)
from kc_calendar.settings import Settings

log = logging.getLogger("calendar.google")
router = APIRouter()


def _settings(request: Request) -> Settings:
    return request.app.state.settings


@router.get("/api/google/status")
async def google_status(request: Request) -> dict[str, bool]:
    db: AsyncSession = request.state.db
    _session, family_id = await _family_id(request, db)
    family = await db.get(Family, family_id)
    settings = _settings(request)
    return {
        "configured": configured(settings),
        "connected": bool(family and family.google_refresh_token),
    }


@router.get("/api/google/start")
async def google_start(request: Request) -> RedirectResponse:
    db: AsyncSession = request.state.db
    _session, family_id = await _family_id(request, db)
    settings = _settings(request)
    if not configured(settings):
        raise ApiError(404, ErrorCode.not_found, "Google Calendar is not configured.")
    state = sign_state(family_id, settings.internal_api_token)
    return RedirectResponse(authorization_url(settings, state), status_code=302)


@router.get("/api/google/callback")
async def google_callback(request: Request, code: str = "", state: str = "") -> RedirectResponse:
    settings = _settings(request)
    home = settings.web_origin.rstrip("/") + "/"
    if not code or not state or not configured(settings):
        return RedirectResponse(home + "?google=error", status_code=302)
    db: AsyncSession = request.state.db
    try:
        _session, family_id = await _family_id(request, db)
        claimed = read_state(state, settings.internal_api_token)
        if claimed != family_id:
            raise GoogleSyncError("state")
        refresh = await exchange_code(settings, code)
    except (ApiError, GoogleSyncError):
        log.warning("google connect failed")
        return RedirectResponse(home + "?google=error", status_code=302)
    family = await db.scalar(select(Family).where(Family.id == family_id))
    if family is None:
        return RedirectResponse(home + "?google=error", status_code=302)
    family.google_refresh_token = refresh
    await db.commit()
    log.info("google connected", extra={"family_id": str(family_id)})
    return RedirectResponse(home + "?google=connected", status_code=302)


@router.delete("/api/google", status_code=204)
async def google_disconnect(request: Request) -> Response:
    db: AsyncSession = request.state.db
    _session, family_id = await _family_id(request, db)
    family = await db.get(Family, family_id)
    if family is not None:
        family.google_refresh_token = None
        await db.commit()
    log.info("google disconnected", extra={"family_id": str(family_id)})
    return Response(status_code=204)
