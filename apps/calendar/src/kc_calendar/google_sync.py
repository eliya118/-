"""Push one family's events to their primary Google calendar.

The refresh token stays in the calendar database. This module does not log
titles, emails, or tokens.
"""

import datetime as dt
import hashlib
import hmac
import time
from urllib.parse import urlencode
from uuid import UUID
from zoneinfo import ZoneInfo

import httpx

from kc_calendar.settings import Settings

JERUSALEM = ZoneInfo("Asia/Jerusalem")
TOKEN_URL = "https://oauth2.googleapis.com/token"
AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
EVENTS_URL = "https://www.googleapis.com/calendar/v3/calendars/primary/events"
SCOPE = "https://www.googleapis.com/auth/calendar.events"
STATE_TTL_SECONDS = 15 * 60


class GoogleSyncError(Exception):
    """Google rejected the call or the network failed. The local event still stands."""


def configured(settings: Settings) -> bool:
    return bool(settings.google_client_id and settings.google_client_secret)


def event_payload(
    title: str,
    starts_at: dt.datetime,
    ends_at: dt.datetime | None,
    all_day: bool,
) -> dict[str, object]:
    if all_day:
        start_day = starts_at.astimezone(JERUSALEM).date()
        end_day = ends_at.astimezone(JERUSALEM).date() if ends_at else start_day + dt.timedelta(days=1)
        if end_day <= start_day:
            end_day = start_day + dt.timedelta(days=1)
        return {
            "summary": title,
            "start": {"date": start_day.isoformat()},
            "end": {"date": end_day.isoformat()},
        }
    end = ends_at if ends_at and ends_at > starts_at else starts_at + dt.timedelta(hours=1)
    return {
        "summary": title,
        "start": {"dateTime": starts_at.isoformat(), "timeZone": "Asia/Jerusalem"},
        "end": {"dateTime": end.isoformat(), "timeZone": "Asia/Jerusalem"},
    }


def sign_state(family_id: UUID, secret: str, now: float | None = None) -> str:
    issued = int(now if now is not None else time.time())
    message = f"{family_id}.{issued}"
    signature = hmac.new(secret.encode(), message.encode(), hashlib.sha256).hexdigest()
    return f"{message}.{signature}"


def read_state(state: str, secret: str, now: float | None = None) -> UUID:
    family_text, issued_text, signature = _split_state(state)
    message = f"{family_text}.{issued_text}"
    expected = hmac.new(secret.encode(), message.encode(), hashlib.sha256).hexdigest()
    if not hmac.compare_digest(signature, expected):
        raise GoogleSyncError("state")
    issued = int(issued_text)
    current = int(now if now is not None else time.time())
    if current - issued > STATE_TTL_SECONDS or issued > current + 60:
        raise GoogleSyncError("state")
    return UUID(family_text)


def authorization_url(settings: Settings, state: str) -> str:
    query = urlencode(
        {
            "client_id": settings.google_client_id,
            "redirect_uri": settings.google_redirect_uri,
            "response_type": "code",
            "scope": SCOPE,
            "access_type": "offline",
            "prompt": "consent",
            "state": state,
        }
    )
    return f"{AUTH_URL}?{query}"


async def exchange_code(settings: Settings, code: str) -> str:
    payload = await _token_request(
        settings,
        {
            "code": code,
            "grant_type": "authorization_code",
            "redirect_uri": settings.google_redirect_uri,
        },
    )
    refresh = payload.get("refresh_token")
    if not isinstance(refresh, str) or not refresh:
        raise GoogleSyncError("token")
    return refresh


async def upsert_google_event(
    settings: Settings,
    refresh_token: str,
    google_event_id: str | None,
    title: str,
    starts_at: dt.datetime,
    ends_at: dt.datetime | None,
    all_day: bool,
) -> str:
    access = await _access_token(settings, refresh_token)
    body = event_payload(title, starts_at, ends_at, all_day)
    headers = {"Authorization": f"Bearer {access}"}
    async with httpx.AsyncClient(timeout=10) as client:
        if google_event_id:
            updated = await client.patch(f"{EVENTS_URL}/{google_event_id}", json=body, headers=headers)
            if updated.status_code == 404:
                google_event_id = None
            elif updated.status_code < 400:
                return str(updated.json()["id"])
            else:
                raise GoogleSyncError("upsert")
        created = await client.post(EVENTS_URL, json=body, headers=headers)
    if created.status_code >= 400:
        raise GoogleSyncError("upsert")
    return str(created.json()["id"])


async def delete_google_event(settings: Settings, refresh_token: str, google_event_id: str) -> None:
    access = await _access_token(settings, refresh_token)
    async with httpx.AsyncClient(timeout=10) as client:
        response = await client.delete(
            f"{EVENTS_URL}/{google_event_id}",
            headers={"Authorization": f"Bearer {access}"},
        )
    if response.status_code in {200, 204, 404, 410}:
        return
    raise GoogleSyncError("delete")


async def _access_token(settings: Settings, refresh_token: str) -> str:
    payload = await _token_request(
        settings,
        {"refresh_token": refresh_token, "grant_type": "refresh_token"},
    )
    access = payload.get("access_token")
    if not isinstance(access, str) or not access:
        raise GoogleSyncError("token")
    return access


async def _token_request(settings: Settings, fields: dict[str, str]) -> dict[str, object]:
    data = {
        "client_id": settings.google_client_id,
        "client_secret": settings.google_client_secret,
        **fields,
    }
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            response = await client.post(TOKEN_URL, data=data)
    except httpx.HTTPError as exc:
        raise GoogleSyncError("token") from exc
    if response.status_code >= 400:
        raise GoogleSyncError("token")
    body = response.json()
    if not isinstance(body, dict):
        raise GoogleSyncError("token")
    return body


def _split_state(state: str) -> tuple[str, str, str]:
    parts = state.split(".")
    if len(parts) != 3:
        raise GoogleSyncError("state")
    return parts[0], parts[1], parts[2]
