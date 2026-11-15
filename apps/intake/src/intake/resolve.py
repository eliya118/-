"""Turn an extraction into a draft. Dates come from hebrewcal and the injected clock."""

from __future__ import annotations

import datetime as dt
from uuid import UUID
from zoneinfo import ZoneInfo

from contracts.drafts import Draft, ParseResponse

from hebrewcal import resolve_relative

JERUSALEM = ZoneInfo("Asia/Jerusalem")

QUESTIONS = {
    "he": {
        "unknown": "לא מצאתי את השם. בחרו ילד מהרשימה.",
        "child": "לאיזה ילד?",
        "time": "באיזו שעה?",
        "date": "באיזה יום?",
        "unsupported": "אני מבין כמה משפטים לדוגמה. נסו ניסוח אחר, או הוסיפו את האירוע ידנית.",
    },
    "en": {
        "unknown": "I don't know that child. Pick one from the list.",
        "child": "Which child is this for?",
        "time": "What time?",
        "date": "Which day?",
        "unsupported": "I only understand a few example sentences. Try another wording, or add the event by hand.",
    },
}


def question(locale: str, reason: str) -> str:
    table = QUESTIONS["he"] if locale == "he" else QUESTIONS["en"]
    return table.get(reason, table["unsupported"])


def default_remind(starts_at: dt.datetime, all_day: bool, now: dt.datetime) -> dt.datetime | None:
    if all_day:
        local = starts_at.astimezone(JERUSALEM)
        remind = local.replace(hour=8, minute=0, second=0, microsecond=0)
    else:
        remind = starts_at - dt.timedelta(minutes=60)
    if remind <= now:
        return None
    return remind


def resolve_extraction(
    extraction: dict[str, object],
    now: dt.datetime,
    locale: str,
    tokens: dict[str, UUID],
) -> ParseResponse:
    if extraction.get("status") == "clarify" or extraction.get("unknown_child") is True:
        reason = str(extraction.get("reason") or ("unknown" if extraction.get("unknown_child") else "date"))
        return ParseResponse(status="needs_clarification", questions=[question(locale, reason)])
    child_tokens = extraction.get("child_tokens")
    if not isinstance(child_tokens, list) or not child_tokens:
        return ParseResponse(status="needs_clarification", questions=[question(locale, "child")])
    child_ids: list[UUID] = []
    for token in child_tokens:
        if not isinstance(token, str) or token not in tokens:
            return ParseResponse(status="needs_clarification", questions=[question(locale, "unknown")])
        child_ids.append(tokens[token])
    date_token = extraction.get("date_token")
    if not isinstance(date_token, str) or not date_token:
        return ParseResponse(status="needs_clarification", questions=[question(locale, "date")])
    try:
        day = resolve_relative(date_token, now)
    except (ValueError, LookupError):
        return ParseResponse(status="needs_clarification", questions=[question(locale, "date")])
    all_day = bool(extraction.get("all_day"))
    time_hhmm = extraction.get("time_hhmm")
    if all_day:
        starts = dt.datetime.combine(day, dt.time.min, tzinfo=JERUSALEM)
    elif isinstance(time_hhmm, str) and ":" in time_hhmm:
        hour_text, minute_text = time_hhmm.split(":", 1)
        starts = dt.datetime.combine(
            day, dt.time(int(hour_text), int(minute_text)), tzinfo=JERUSALEM
        )
    else:
        return ParseResponse(status="needs_clarification", questions=[question(locale, "time")])
    title = extraction.get("title")
    if not isinstance(title, str) or not title.strip():
        title = "אירוע" if locale == "he" else "Event"
    title = title.strip()[:200]
    draft = Draft(
        title=title,
        child_ids=child_ids,
        starts_at=starts,
        ends_at=None,
        all_day=all_day,
        remind_at=default_remind(starts, all_day, now),
    )
    return ParseResponse(status="ready", draft=draft, questions=[])
