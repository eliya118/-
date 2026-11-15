"""Reminder instants. Notifier delivers at this time and does not reinterpret it."""

import datetime as dt
from zoneinfo import ZoneInfo

JERUSALEM = ZoneInfo("Asia/Jerusalem")
DEFAULT_OFFSET_MINUTES = 60


def compute_remind_at(
    starts_at: dt.datetime,
    all_day: bool,
    now: dt.datetime,
    offset_minutes: int | None = None,
) -> dt.datetime | None:
    if starts_at.tzinfo is None or now.tzinfo is None:
        raise ValueError("times must be timezone-aware")
    if all_day:
        local = starts_at.astimezone(JERUSALEM)
        morning = local.replace(hour=8, minute=0, second=0, microsecond=0)
        shift = 0 if offset_minutes is None else offset_minutes
        remind = morning - dt.timedelta(minutes=shift)
    else:
        minutes = DEFAULT_OFFSET_MINUTES if offset_minutes is None else offset_minutes
        remind = starts_at - dt.timedelta(minutes=minutes)
    if remind <= now:
        return None
    return remind
