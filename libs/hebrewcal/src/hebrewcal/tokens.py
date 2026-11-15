"""Relative dates. The model extracts a token; this module is the clock."""

from __future__ import annotations

import datetime as dt

from hdate import HebrewDate, Zmanim

from hebrewcal.calendar import (
    CANDLE_LIGHTING_MINUTES,
    JERUSALEM_TZ,
    LOCATION,
    festival_blocks,
)


def _require_aware(now: dt.datetime) -> dt.datetime:
    if now.tzinfo is None:
        raise ValueError("clock must be timezone-aware")
    return now.astimezone(JERUSALEM_TZ)


def next_weekday(now: dt.datetime, python_weekday: int) -> dt.date:
    """Next date with that weekday whose local midnight is still strictly ahead of `now`.

    Sunday is 6 and Saturday is 5, matching `date.weekday()`. On that weekday itself
    the midnight has already passed, so the result is seven days out. Earlier in the
    week the result is the upcoming one.
    """
    local = _require_aware(now)
    today = local.date()
    delta = (python_weekday - today.weekday()) % 7
    candidate = today + dt.timedelta(days=delta)
    start = dt.datetime.combine(candidate, dt.time.min, tzinfo=JERUSALEM_TZ)
    if start <= local:
        candidate += dt.timedelta(days=7)
    return candidate


def _blocks_around(now: dt.datetime) -> list[tuple[str, dt.date, dt.date]]:
    local_date = _require_aware(now).date()
    hebrew_year = HebrewDate.from_gdate(local_date).year
    found: list[tuple[str, dt.date, dt.date]] = []
    for year in (hebrew_year - 1, hebrew_year, hebrew_year + 1):
        found.extend(festival_blocks(year))
    found.sort(key=lambda block: block[1])
    return found


def _candle_lighting(eve: dt.date) -> dt.datetime | None:
    zmanim = Zmanim(eve, LOCATION, candle_lighting_offset=CANDLE_LIGHTING_MINUTES)
    lighting = zmanim.candle_lighting
    if lighting is None:
        return None
    return lighting.astimezone(JERUSALEM_TZ)


def erev_chag(now: dt.datetime) -> dt.date:
    """Eve of the next festival whose candle-lighting is still ahead of `now`."""
    local = _require_aware(now)
    best_eve: dt.date | None = None
    best_at: dt.datetime | None = None
    for _key, start, _end in _blocks_around(local):
        eve = start - dt.timedelta(days=1)
        lighting = _candle_lighting(eve)
        if lighting is None or lighting <= local:
            continue
        if best_at is None or lighting < best_at:
            best_eve = eve
            best_at = lighting
    if best_eve is None:
        raise LookupError("no upcoming festival")
    return best_eve


def after_chag(now: dt.datetime) -> dt.date:
    """First civil date after the current block, or after the next one if outside."""
    local = _require_aware(now)
    today = local.date()
    blocks = _blocks_around(local)
    for _key, start, end in blocks:
        if start <= today <= end:
            return end + dt.timedelta(days=1)
    for _key, _start, end in blocks:
        if end >= today:
            return end + dt.timedelta(days=1)
    raise LookupError("no festival block")


def resolve_relative(token: str, now: dt.datetime) -> dt.date:
    key = token.strip().lower()
    if key in {"tomorrow", "מחר"}:
        return _require_aware(now).date() + dt.timedelta(days=1)
    if key in {"sunday", "יום ראשון"}:
        return next_weekday(now, 6)
    if key in {"shabbat", "שבת"}:
        return next_weekday(now, 5)
    if key in {"erev_shabbat", "ערב שבת"}:
        return next_weekday(now, 5) - dt.timedelta(days=1)
    if key in {"erev_chag", "ערב חג"}:
        return erev_chag(now)
    if key in {"after_chag", "אחרי החג"}:
        return after_chag(now)
    raise ValueError(f"unknown date token: {token}")
